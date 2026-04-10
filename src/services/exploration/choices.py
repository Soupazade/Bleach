from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from asyncpg import Pool

from src.data.exploration import (
    get_decision_event_definition,
    get_decision_step_definition,
    get_explore_approach,
    get_random_special_offer_template,
)
from src.data.locations import get_location_definition
from src.data.npcs import get_npc_definition
from src.models.combat import ActiveExplorationCombat
from src.models.exploration import PendingExplorationChoice
from src.models.player import PlayerProfile
from src.services.combat_service import (
    CombatAction,
    advance_combat_state,
    fetch_active_combat_record_by_message,
    update_active_exploration_combat,
)
from src.services.effect_service import list_active_player_effects_for_connection
from src.services.exploration.repository import (
    delete_pending_choice,
    fetch_pending_choice_record,
    fetch_pending_choice_record_by_message,
    update_pending_choice,
)
from src.services.exploration.rewards import (
    _format_text,
    apply_location_stamina_cost_modifier,
    create_special_offer,
    finalize_combat_resolution,
    finalize_non_combat_resolution,
    get_combat_lose_profile,
    get_current_player,
    resolve_outcome_xp,
    should_trigger_special_opportunity,
    start_decision_combat,
)
from src.services.exploration.types import (
    ExplorationChoiceAdvanceResult,
    ExplorationDecisionOptionRender,
    ExplorationDecisionPrompt,
    ExplorationResolution,
)
from src.services.npc_service import (
    get_npc_encounter_definition,
    upsert_player_npc_progress,
)
from src.services.player_service import get_or_sync_player_record, update_player_record


def build_decision_prompt(
    session: PendingExplorationChoice,
    player: PlayerProfile | None = None,
) -> ExplorationDecisionPrompt:
    approach = get_explore_approach(session.approach)
    location = get_location_definition(session.location)

    if session.session_kind == "npc_event":
        if session.npc_id is None:
            raise ValueError("NPC event session is missing npc_id.")

        npc = get_npc_definition(session.npc_id)
        encounter = get_npc_encounter_definition(session.npc_id, session.event_key)
        options = tuple(
            ExplorationDecisionOptionRender(
                slot=index,
                label=option.label,
                style=option.style,  # type: ignore[arg-type]
            )
            for index, option in enumerate(encounter.options, start=1)
        )
        return ExplorationDecisionPrompt(
            session=session,
            prompt_kind="npc_event",
            event_title=encounter.title,
            step_title=f"{npc.name} | Stage {encounter.stage_number}",
            description=encounter.description,
            step_number=1,
            total_steps=1,
            options=options,
        )

    if session.session_kind == "special_offer":
        adjusted_cost = 10
        stamina_modifier = 0
        reputation_title = "Unknown"
        if player is not None:
            adjusted_cost, stamina_modifier = apply_location_stamina_cost_modifier(
                player,
                session.location,
                10,
            )
            from src.services.reputation_service import get_location_reputation_title

            reputation_title = get_location_reputation_title(player, session.location)
        special_event = get_decision_event_definition(
            session.location,
            session.special_event_key or session.event_key,
        )
        offer_template = get_random_special_offer_template(session.location)
        cost_line = f"another **{adjusted_cost} stamina**"
        if stamina_modifier != 0:
            cost_line = (
                f"another **{adjusted_cost} stamina** "
                f"({stamina_modifier:+d} from {reputation_title} reputation)"
            )
        description = _format_text(
            offer_template.description,
            approach=approach,
            location_name=location.name,
        )
        description = f"{description}\n\n**{special_event.title}** is there if you are willing to spend {cost_line} and press your luck."
        options = (
            ExplorationDecisionOptionRender(
                slot=1,
                label=f"Engage (-{adjusted_cost} Stamina)",
                style="danger",
            ),
            ExplorationDecisionOptionRender(slot=2, label="Ignore", style="secondary"),
        )
        return ExplorationDecisionPrompt(
            session=session,
            prompt_kind="special_offer",
            event_title="Special Opportunity",
            step_title="The street gives you one more chance",
            description=description,
            step_number=1,
            total_steps=2,
            options=options,
            stamina_cost=adjusted_cost,
            stamina_cost_modifier=stamina_modifier,
            reputation_title=reputation_title,
        )

    event = get_decision_event_definition(session.location, session.event_key)
    step = get_decision_step_definition(event, session.current_step)
    step_number = min(event.step_count, len(session.choice_history) + 1)
    total_steps = event.step_count
    prompt_kind: Literal["decision", "special_offer", "special_event"] = "decision"
    if session.session_kind == "special_event":
        step_number = 2
        total_steps = 2
        prompt_kind = "special_event"

    options = tuple(
        ExplorationDecisionOptionRender(
            slot=index,
            label=option.label,
            style=option.style,
        )
        for index, option in enumerate(step.options, start=1)
    )
    return ExplorationDecisionPrompt(
        session=session,
        prompt_kind=prompt_kind,
        event_title=event.title,
        step_title=step.title,
        description=_format_text(step.description, approach=approach, location_name=location.name),
        step_number=step_number,
        total_steps=total_steps,
        options=options,
    )


async def get_pending_exploration_prompt(
    pool: Pool | None,
    user_id: int,
) -> ExplorationDecisionPrompt | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        session_record = await fetch_pending_choice_record(connection, user_id)
        if session_record is None:
            return None

        session = PendingExplorationChoice.from_record(session_record)
        player_sync = await get_or_sync_player_record(connection, user_id)
        player = None if player_sync is None else PlayerProfile.from_record(player_sync.record)
        return build_decision_prompt(session, player)


async def rebind_pending_exploration_prompt(
    pool: Pool | None,
    *,
    user_id: int,
    message_id: int,
) -> ExplorationDecisionPrompt | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        async with connection.transaction():
            session_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            if session_record is None:
                return None

            session = PendingExplorationChoice.from_record(session_record)
            if session.message_id != message_id:
                session = await update_pending_choice(
                    connection,
                    user_id,
                    {"message_id": message_id},
                )

            player_sync = await get_or_sync_player_record(connection, user_id)
            player = None if player_sync is None else PlayerProfile.from_record(player_sync.record)
            return build_decision_prompt(session, player)


async def advance_exploration_choice(
    pool: Pool | None,
    *,
    message_id: int,
    user_id: int,
    option_slot: int,
) -> ExplorationChoiceAdvanceResult:
    if pool is None:
        return ExplorationChoiceAdvanceResult(status="missing")

    async with pool.acquire() as connection:
        async with connection.transaction():
            session_record = await fetch_pending_choice_record_by_message(connection, message_id, for_update=True)
            if session_record is None:
                return ExplorationChoiceAdvanceResult(status="missing")

            session = PendingExplorationChoice.from_record(session_record)
            if session.user_id != user_id:
                return ExplorationChoiceAdvanceResult(status="missing")

            if session.session_kind == "npc_event":
                if session.npc_id is None:
                    return ExplorationChoiceAdvanceResult(status="missing")

                encounter = get_npc_encounter_definition(session.npc_id, session.event_key)
                if option_slot < 1 or option_slot > len(encounter.options):
                    return ExplorationChoiceAdvanceResult(status="missing")

                selected_option = encounter.options[option_slot - 1]
                outcome = selected_option.outcome
                current_player = await get_current_player(connection, user_id)
                if outcome.event_type == "combat":
                    combat = await start_decision_combat(
                        connection,
                        session=session,
                        player=current_player,
                        event_title=encounter.title,
                        step_description=encounter.description,
                        selected_label=selected_option.label,
                        resolution_title=outcome.title,
                        resolution_description=outcome.description,
                        reward_xp_win=outcome.xp_reward,
                        reward_xp_lose=max(5, outcome.xp_reward // 2),
                        reputation_change=outcome.reputation_change,
                        message_id=session.message_id,
                    )
                    await upsert_player_npc_progress(
                        connection,
                        user_id=user_id,
                        npc_id=session.npc_id,
                        state=outcome.next_state,
                        stage=outcome.next_stage,
                        last_encounter_at=datetime.now(timezone.utc),
                    )
                    await delete_pending_choice(connection, user_id)
                    return ExplorationChoiceAdvanceResult(status="combat", combat=combat)

                resolution = await finalize_non_combat_resolution(
                    connection,
                    user_id=user_id,
                    exploration=session.to_active_exploration(),
                    event_type=outcome.event_type,  # type: ignore[arg-type]
                    title=outcome.title,
                    description=outcome.description,
                    base_xp=outcome.xp_reward,
                    reputation_change=outcome.reputation_change,
                    combat_outcome=outcome.combat_outcome,
                )
                await upsert_player_npc_progress(
                    connection,
                    user_id=user_id,
                    npc_id=session.npc_id,
                    state=outcome.next_state,
                    stage=outcome.next_stage,
                    last_encounter_at=datetime.now(timezone.utc),
                )
                await delete_pending_choice(connection, user_id)
                return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)

            if session.session_kind == "special_offer":
                player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
                if player_sync is None:
                    return ExplorationChoiceAdvanceResult(status="missing")

                player = PlayerProfile.from_record(player_sync.record)
                if option_slot == 2:
                    if session.base_xp is None:
                        return ExplorationChoiceAdvanceResult(status="missing")

                    resolution = await finalize_non_combat_resolution(
                        connection,
                        user_id=user_id,
                        exploration=session.to_active_exploration(),
                        event_type=session.base_event_type or "reward",  # type: ignore[arg-type]
                        title=session.base_title or "Street Result",
                        description=session.base_description or "The district gives you the original outcome and lets the rest pass.",
                        base_xp=session.base_xp,
                        reputation_change=session.base_rep_change or 0,
                        combat_outcome=session.base_combat_outcome,
                    )
                    await delete_pending_choice(connection, user_id)
                    return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)

                if option_slot != 1:
                    return ExplorationChoiceAdvanceResult(status="missing")

                extra_stamina_cost, _ = apply_location_stamina_cost_modifier(
                    player,
                    session.location,
                    10,
                )
                if player.stamina_current < extra_stamina_cost:
                    return ExplorationChoiceAdvanceResult(
                        status="insufficient_stamina",
                        prompt=build_decision_prompt(session, player),
                        required_stamina=extra_stamina_cost,
                    )

                special_event_key = session.special_event_key
                if special_event_key is None:
                    return ExplorationChoiceAdvanceResult(status="missing")

                special_event = get_decision_event_definition(session.location, special_event_key)
                now = datetime.now(timezone.utc)
                persisted_player_record = await update_player_record(
                    connection,
                    user_id,
                    {
                        "stamina_current": player.stamina_current - extra_stamina_cost,
                        "stamina_updated_at": now,
                    },
                )
                updated_session = await update_pending_choice(
                    connection,
                    user_id,
                    {
                        "session_kind": "special_event",
                        "event_key": special_event.key,
                        "event_flow": special_event.flow_type,
                        "current_step": special_event.initial_step_id,
                        "choice_history": ["engage"],
                    },
                )
                return ExplorationChoiceAdvanceResult(
                    status="advanced",
                    prompt=build_decision_prompt(
                        updated_session,
                        PlayerProfile.from_record(persisted_player_record),
                    ),
                )

            current_player = await get_current_player(connection, user_id)
            active_effects = await list_active_player_effects_for_connection(connection, user_id)
            event = get_decision_event_definition(session.location, session.event_key)
            step = get_decision_step_definition(event, session.current_step)
            if option_slot < 1 or option_slot > len(step.options):
                return ExplorationChoiceAdvanceResult(status="missing")

            selected_option = step.options[option_slot - 1]
            choice_history = [*session.choice_history, selected_option.key]

            if selected_option.next_step_id is not None:
                updated_session = await update_pending_choice(
                    connection,
                    user_id,
                    {
                        "current_step": selected_option.next_step_id,
                        "choice_history": choice_history,
                    },
                )
                return ExplorationChoiceAdvanceResult(
                    status="advanced",
                    prompt=build_decision_prompt(updated_session, current_player),
                )

            if selected_option.outcome is None:
                return ExplorationChoiceAdvanceResult(status="missing")

            approach = get_explore_approach(session.approach)
            outcome = selected_option.outcome
            base_xp = resolve_outcome_xp(approach, outcome.xp_profile)

            formatted_step_description = _format_text(
                step.description,
                approach=approach,
                location_name=get_location_definition(session.location).name,
            )
            formatted_outcome_description = _format_text(
                outcome.description,
                approach=approach,
                location_name=get_location_definition(session.location).name,
            )

            if outcome.event_type == "combat":
                lose_profile = get_combat_lose_profile(outcome.xp_profile)
                combat = await start_decision_combat(
                    connection,
                    session=session,
                    player=current_player,
                    event_title=event.title,
                    step_description=formatted_step_description,
                    selected_label=selected_option.label,
                    resolution_title=outcome.title,
                    resolution_description=formatted_outcome_description,
                    reward_xp_win=base_xp,
                    reward_xp_lose=resolve_outcome_xp(approach, lose_profile),
                    reputation_change=outcome.reputation_change,
                    message_id=session.message_id,
                )
                await delete_pending_choice(connection, user_id)
                return ExplorationChoiceAdvanceResult(status="combat", combat=combat)

            base_resolution = ExplorationResolution(
                exploration=session.to_active_exploration(),
                player=current_player,
                event_type=outcome.event_type,
                title=outcome.title,
                description=formatted_outcome_description,
                xp_gained=base_xp,
                levels_gained=0,
                base_xp=base_xp,
                reputation_xp_modifier_pct=0,
                reputation_change=outcome.reputation_change,
                combat_outcome=outcome.combat_outcome,
            )
            if (
                session.session_kind == "decision"
                and outcome.event_type != "combat"
                and should_trigger_special_opportunity(approach, active_effects)
            ):
                await delete_pending_choice(connection, user_id)
                prompt = await create_special_offer(
                    connection,
                    base_resolution,
                    message_id=session.message_id,
                )
                return ExplorationChoiceAdvanceResult(status="advanced", prompt=prompt)

            resolution = await finalize_non_combat_resolution(
                connection,
                user_id=user_id,
                exploration=session.to_active_exploration(),
                event_type=outcome.event_type,
                title=outcome.title,
                description=formatted_outcome_description,
                base_xp=base_xp,
                reputation_change=outcome.reputation_change,
                combat_outcome=outcome.combat_outcome,
            )
            await delete_pending_choice(connection, user_id)
            return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)


async def advance_exploration_combat(
    pool: Pool | None,
    *,
    message_id: int,
    user_id: int,
    action: CombatAction,
) -> ExplorationChoiceAdvanceResult:
    if pool is None:
        return ExplorationChoiceAdvanceResult(status="missing")

    async with pool.acquire() as connection:
        async with connection.transaction():
            combat_record = await fetch_active_combat_record_by_message(connection, message_id, for_update=True)
            if combat_record is None:
                return ExplorationChoiceAdvanceResult(status="missing")

            combat = ActiveExplorationCombat.from_record(combat_record)
            if combat.user_id != user_id:
                return ExplorationChoiceAdvanceResult(status="missing")

            combat_step = advance_combat_state(combat, action)
            if combat_step.status == "updated" and combat_step.combat is not None:
                updated_combat = await update_active_exploration_combat(
                    connection,
                    user_id,
                    {
                        "enemy_hp_current": combat_step.combat.enemy_hp_current,
                        "player_hp_current": combat_step.combat.player_hp_current,
                        "player_mana_current": combat_step.combat.player_mana_current,
                        "round_number": combat_step.combat.round_number,
                        "focus_bonus": combat_step.combat.focus_bonus,
                        "guard_active": combat_step.combat.guard_active,
                        "last_round_summary": combat_step.combat.last_round_summary,
                    },
                )
                return ExplorationChoiceAdvanceResult(status="updated", combat=updated_combat)

            if combat_step.outcome is None:
                return ExplorationChoiceAdvanceResult(status="missing")

            outcome = combat_step.outcome
            base_xp = outcome.xp_reward
            resolved_combat = await update_active_exploration_combat(
                connection,
                user_id,
                {
                    "enemy_hp_current": outcome.combat.enemy_hp_current,
                    "player_hp_current": outcome.player_hp_current,
                    "player_mana_current": outcome.player_mana_current,
                    "round_number": outcome.combat.round_number,
                    "focus_bonus": outcome.combat.focus_bonus,
                    "guard_active": outcome.combat.guard_active,
                    "last_round_summary": outcome.combat.last_round_summary,
                },
            )
            resolution = await finalize_combat_resolution(
                connection,
                combat=resolved_combat,
                base_xp=base_xp,
                combat_outcome=outcome.combat_outcome,
                title=outcome.title,
                description=outcome.description,
                reputation_change=outcome.reputation_change,
            )
            return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)
