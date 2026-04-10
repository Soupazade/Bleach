from __future__ import annotations

from datetime import datetime, timezone

from asyncpg import Pool

from src.data.exploration import get_explore_approach, get_random_decision_event
from src.models.exploration import ActiveExploration
from src.services.effect_service import list_active_player_effects_for_connection
from src.services.exploration.choices import build_decision_prompt
from src.services.exploration.repository import (
    close_active_exploration,
    create_pending_exploration_choice,
    fetch_active_exploration_record,
)
from src.services.exploration.rewards import (
    create_special_offer,
    finalize_non_combat_resolution,
    get_current_player,
    get_instant_reputation_change,
    roll_instant_exploration_event,
    roll_resolution_flow,
    should_trigger_special_opportunity,
    start_instant_combat,
)
from src.services.exploration.types import ExplorationPostResult, ExplorationResolution
from src.services.npc_service import get_eligible_npc_encounter


async def resolve_exploration(
    pool: Pool | None,
    user_id: int,
    *,
    force: bool = False,
) -> ExplorationPostResult | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        async with connection.transaction():
            exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if exploration_record is None:
                return None

            exploration = ActiveExploration.from_record(exploration_record)
            if exploration.end_time > datetime.now(timezone.utc) and not force:
                return None

            eligible_npc_encounter = await get_eligible_npc_encounter(
                connection,
                user_id=user_id,
                location_key=exploration.location,
            )
            if eligible_npc_encounter is not None:
                pending_choice = await create_pending_exploration_choice(
                    connection,
                    exploration,
                    message_id=None,
                    event_key=eligible_npc_encounter.encounter.key,
                    event_flow="single_choice",
                    current_step="npc_step",
                    session_kind="npc_event",
                    npc_id=eligible_npc_encounter.npc.id,
                )
                await close_active_exploration(connection, exploration)
                return ExplorationPostResult(
                    status="choice_prompt",
                    prompt=build_decision_prompt(pending_choice),
                )

            approach = get_explore_approach(exploration.approach)
            resolution_flow = roll_resolution_flow(approach)

            if resolution_flow == "instant":
                current_player = await get_current_player(connection, user_id)
                active_effects = await list_active_player_effects_for_connection(connection, user_id)
                event_type, title, description, base_xp, combat_outcome = roll_instant_exploration_event(exploration)

                if event_type == "combat":
                    combat = await start_instant_combat(
                        connection,
                        exploration=exploration,
                        player=current_player,
                    )
                    await close_active_exploration(connection, exploration)
                    return ExplorationPostResult(status="combat_prompt", combat=combat)

                reputation_change = get_instant_reputation_change(event_type, combat_outcome)
                base_resolution = ExplorationResolution(
                    exploration=exploration,
                    player=current_player,
                    event_type=event_type,
                    title=title,
                    description=description,
                    xp_gained=base_xp,
                    levels_gained=0,
                    base_xp=base_xp,
                    reputation_xp_modifier_pct=0,
                    reputation_change=reputation_change,
                    combat_outcome=combat_outcome,
                )
                if should_trigger_special_opportunity(approach, active_effects):
                    await close_active_exploration(connection, exploration)
                    prompt = await create_special_offer(connection, base_resolution, message_id=None)
                    return ExplorationPostResult(status="choice_prompt", prompt=prompt)

                resolution = await finalize_non_combat_resolution(
                    connection,
                    user_id=user_id,
                    exploration=exploration,
                    event_type=event_type,
                    title=title,
                    description=description,
                    base_xp=base_xp,
                    reputation_change=reputation_change,
                    combat_outcome=combat_outcome,
                )
                await close_active_exploration(connection, exploration)
                return ExplorationPostResult(
                    status="instant",
                    resolution=resolution,
                )

            event = get_random_decision_event(exploration.location, resolution_flow)
            pending_choice = await create_pending_exploration_choice(
                connection,
                exploration,
                message_id=None,
                event_key=event.key,
                event_flow=event.flow_type,
                current_step=event.initial_step_id,
            )
            await close_active_exploration(connection, exploration)
            return ExplorationPostResult(
                status="choice_prompt",
                prompt=build_decision_prompt(pending_choice),
            )
