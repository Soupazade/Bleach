from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import random
from typing import TYPE_CHECKING, Any, Literal

import discord
from asyncpg import Connection, Pool, Record

from src.data.combat import get_enemy_for_exploration_combat
from src.data.exploration import (
    ExploreApproachDefinition,
    ExploreEventType,
    ExploreFlowType,
    ExplorationDecisionEventDefinition,
    ExplorationEventTemplate,
    get_decision_event_definition,
    get_decision_step_definition,
    get_explore_approach,
    get_location_event_pool,
    get_random_decision_event,
    get_random_special_offer_template,
    get_random_special_event,
)
from src.data.locations import get_location_definition
from src.data.npcs import get_npc_definition
from src.models.combat import ActiveExplorationCombat
from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.models.player import PlayerProfile
from src.services.combat_service import (
    CombatAction,
    advance_combat_state,
    create_active_exploration_combat,
    delete_active_exploration_combat,
    fetch_active_combat_record,
    fetch_active_combat_record_by_message,
    get_active_exploration_combat,
    update_active_exploration_combat,
)
from src.services.formulas import apply_experience_gain, format_remaining_duration
from src.services.npc_service import (
    get_eligible_npc_encounter,
    get_npc_encounter_definition,
    upsert_player_npc_progress,
)
from src.services.player_service import get_or_sync_player_record, update_player_record
from src.services.reputation_service import (
    apply_rep_stamina_cost,
    apply_rep_xp,
    apply_reputation_change,
    format_reputation_stamina_text,
    format_reputation_change_text,
    format_reputation_xp_text,
    get_location_reputation_field,
    get_location_reputation_title,
    get_location_reputation_value,
    get_reputation_modifiers,
)
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


ACTIVE_EXPLORATION_COLUMNS = """
    user_id,
    channel_id,
    location,
    approach,
    start_time,
    end_time
"""

PENDING_EXPLORATION_CHOICE_COLUMNS = """
    user_id,
    channel_id,
    message_id,
    session_kind,
    npc_id,
    location,
    approach,
    start_time,
    end_time,
    event_key,
    special_event_key,
    event_flow,
    current_step,
    choice_history,
    base_event_type,
    base_title,
    base_description,
    base_xp,
    base_rep_change,
    base_combat_outcome,
    created_at,
    updated_at
"""

ACTIVE_EXPLORATION_COMBAT_COLUMNS = """
    user_id,
    channel_id,
    message_id,
    location,
    approach,
    encounter_title,
    encounter_description,
    resolution_title,
    resolution_description,
    enemy_name,
    enemy_hp_current,
    enemy_hp_max,
    enemy_power,
    enemy_defense,
    enemy_speed,
    reward_xp_win,
    reward_xp_lose,
    reputation_change,
    player_hp_current,
    player_hp_max,
    player_mana_current,
    player_mana_max,
    player_power,
    player_defense,
    player_speed,
    player_reiatsu,
    round_number,
    focus_bonus,
    guard_active,
    last_round_summary,
    created_at,
    updated_at
"""


@dataclass(slots=True)
class StartExplorationResult:
    status: Literal[
        "started",
        "missing_profile",
        "resting",
        "insufficient_stamina",
        "active",
        "finished",
        "pending_choice",
    ]
    player: PlayerProfile | None = None
    exploration: ActiveExploration | None = None
    rest_minutes: int = 0
    rest_recovery: int = 0
    pending_choice: "ExplorationDecisionPrompt | None" = None
    stamina_cost: int = 0
    base_stamina_cost: int = 0


@dataclass(slots=True)
class ExplorationResolution:
    exploration: ActiveExploration
    player: PlayerProfile
    event_type: Literal["reward", "combat", "choice", "flavor"]
    title: str
    description: str
    xp_gained: int
    levels_gained: int
    base_xp: int = 0
    reputation_xp_modifier_pct: int = 0
    reputation_change: int = 0
    combat_outcome: str | None = None


@dataclass(frozen=True, slots=True)
class ExplorationDecisionOptionRender:
    slot: int
    label: str
    style: Literal["primary", "secondary", "success", "danger"]


@dataclass(slots=True)
class ExplorationDecisionPrompt:
    session: PendingExplorationChoice
    prompt_kind: Literal["decision", "special_offer", "special_event", "npc_event"]
    event_title: str
    step_title: str
    description: str
    step_number: int
    total_steps: int
    options: tuple[ExplorationDecisionOptionRender, ...]
    stamina_cost: int = 0
    stamina_cost_modifier: int = 0
    reputation_title: str = "Unknown"


@dataclass(slots=True)
class ExplorationPostResult:
    status: Literal["instant", "choice_prompt", "combat_prompt"]
    resolution: ExplorationResolution | None = None
    prompt: ExplorationDecisionPrompt | None = None
    combat: ActiveExplorationCombat | None = None


@dataclass(slots=True)
class ExplorationChoiceAdvanceResult:
    status: Literal["missing", "advanced", "updated", "resolved", "insufficient_stamina", "combat"]
    prompt: ExplorationDecisionPrompt | None = None
    resolution: ExplorationResolution | None = None
    required_stamina: int = 0
    combat: ActiveExplorationCombat | None = None


async def fetch_active_exploration_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_EXPLORATION_COLUMNS}
        FROM active_explorations
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def fetch_pending_choice_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {PENDING_EXPLORATION_CHOICE_COLUMNS}
        FROM active_exploration_choices
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def fetch_pending_choice_record_by_message(
    connection: Connection,
    message_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {PENDING_EXPLORATION_CHOICE_COLUMNS}
        FROM active_exploration_choices
        WHERE message_id = $1
        {lock_clause}
        """,
        message_id,
    )


async def get_active_exploration(pool: Pool | None, user_id: int) -> ActiveExploration | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_exploration_record(connection, user_id)
        if record is None:
            return None

        return ActiveExploration.from_record(record)


async def get_pending_exploration_choice(pool: Pool | None, user_id: int) -> PendingExplorationChoice | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_pending_choice_record(connection, user_id)
        if record is None:
            return None

        return PendingExplorationChoice.from_record(record)


async def get_pending_exploration_choice_by_message(
    pool: Pool | None,
    message_id: int,
) -> PendingExplorationChoice | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_pending_choice_record_by_message(connection, message_id)
        if record is None:
            return None

        return PendingExplorationChoice.from_record(record)


async def list_active_explorations(pool: Pool | None) -> list[ActiveExploration]:
    if pool is None:
        return []

    async with pool.acquire() as connection:
        records = await connection.fetch(
            f"""
            SELECT {ACTIVE_EXPLORATION_COLUMNS}
            FROM active_explorations
            """
        )

    return [ActiveExploration.from_record(record) for record in records]


async def create_active_exploration(
    connection: Connection,
    user_id: int,
    channel_id: int,
    location: str,
    approach: str,
    start_time: datetime,
    end_time: datetime,
) -> ActiveExploration:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_explorations (
            user_id,
            channel_id,
            location,
            approach,
            start_time,
            end_time
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING {ACTIVE_EXPLORATION_COLUMNS}
        """,
        user_id,
        channel_id,
        location,
        approach,
        start_time,
        end_time,
    )
    return ActiveExploration.from_record(record)


async def create_pending_exploration_choice(
    connection: Connection,
    exploration: ActiveExploration,
    *,
    message_id: int | None = None,
    event_key: str,
    event_flow: str,
    current_step: str,
    session_kind: str = "decision",
    npc_id: str | None = None,
    special_event_key: str | None = None,
    base_resolution: ExplorationResolution | None = None,
) -> PendingExplorationChoice:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_exploration_choices (
            user_id,
            channel_id,
            message_id,
            session_kind,
            npc_id,
            location,
            approach,
            start_time,
            end_time,
            event_key,
            special_event_key,
            event_flow,
            current_step,
            choice_history,
            base_event_type,
            base_title,
            base_description,
            base_xp,
            base_rep_change,
            base_combat_outcome
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
        RETURNING {PENDING_EXPLORATION_CHOICE_COLUMNS}
        """,
        exploration.user_id,
        exploration.channel_id,
        message_id,
        session_kind,
        npc_id,
        exploration.location,
        exploration.approach,
        exploration.start_time,
        exploration.end_time,
        event_key,
        special_event_key,
        event_flow,
        current_step,
        [],
        base_resolution.event_type if base_resolution is not None else None,
        base_resolution.title if base_resolution is not None else None,
        base_resolution.description if base_resolution is not None else None,
        base_resolution.base_xp if base_resolution is not None else None,
        base_resolution.reputation_change if base_resolution is not None else None,
        base_resolution.combat_outcome if base_resolution is not None else None,
    )
    return PendingExplorationChoice.from_record(record)


async def update_pending_choice(
    connection: Connection,
    user_id: int,
    fields: dict[str, Any],
) -> PendingExplorationChoice:
    assignments: list[str] = []
    values: list[Any] = []

    for index, (column_name, value) in enumerate(fields.items(), start=1):
        assignments.append(f"{column_name} = ${index}")
        values.append(value)

    values.append(user_id)
    user_id_placeholder = len(values)

    record = await connection.fetchrow(
        f"""
        UPDATE active_exploration_choices
        SET {", ".join(assignments)}, updated_at = NOW()
        WHERE user_id = ${user_id_placeholder}
        RETURNING {PENDING_EXPLORATION_CHOICE_COLUMNS}
        """,
        *values,
    )
    return PendingExplorationChoice.from_record(record)


async def delete_active_exploration(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_explorations
        WHERE user_id = $1
        """,
        user_id,
    )


async def delete_pending_choice(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_exploration_choices
        WHERE user_id = $1
        """,
        user_id,
    )


def _format_text(
    text: str,
    *,
    approach: ExploreApproachDefinition,
    location_name: str,
) -> str:
    return text.format(
        approach=approach.label,
        location=location_name,
    )


def _weighted_event_type(exploration: ActiveExploration) -> ExploreEventType:
    approach = get_explore_approach(exploration.approach)
    event_types = tuple(approach.event_biases.keys())
    weights = tuple(approach.event_biases.values())
    return random.choices(event_types, weights=weights, k=1)[0]


def _roll_resolution_flow(approach: ExploreApproachDefinition) -> ExploreFlowType:
    weights_by_risk = {
        "low": (45, 40, 15),
        "medium": (38, 42, 20),
        "high": (30, 45, 25),
    }
    instant_weight, single_weight, multi_weight = weights_by_risk.get(
        approach.risk_tier,
        (60, 30, 10),
    )
    return random.choices(
        ("instant", "single_choice", "multi_step"),
        weights=(instant_weight, single_weight, multi_weight),
        k=1,
    )[0]


def _roll_special_trigger(approach: ExploreApproachDefinition) -> bool:
    chance_by_risk = {
        "low": 0.10,
        "medium": 0.12,
        "high": 0.15,
    }
    return random.random() < chance_by_risk.get(approach.risk_tier, 0.12)


def _format_event_description(
    template: ExplorationEventTemplate,
    exploration: ActiveExploration,
) -> str:
    approach = get_explore_approach(exploration.approach)
    location = get_location_definition(exploration.location)
    return _format_text(
        template.description,
        approach=approach,
        location_name=location.name,
    )


def _resolve_reward_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.reward_events)
    xp_gained = random.randint(approach.xp_min, approach.xp_max)
    description = _format_event_description(event, exploration)
    return event.title, description, xp_gained


def _resolve_combat_event(exploration: ActiveExploration) -> tuple[str, str, int, str]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.combat_events)
    description = _format_event_description(event, exploration)
    win_chance_by_risk = {
        "low": 0.75,
        "medium": 0.64,
        "high": 0.55,
    }
    won = random.random() < win_chance_by_risk.get(approach.risk_tier, 0.64)
    victory_followups = (
        "You meet it head-on and come out the other side still breathing.",
        "You answer the rush with your own and force the street to blink first.",
        "It gets ugly fast, but you are the one left standing when the dust settles.",
    )
    setback_followups = (
        "You get out, but not clean. The street makes sure you feel the price of it.",
        "You survive it, bruised and breathing hard, with enough sense to know how close it got.",
        "You stagger clear with your life and a fresh reminder that Rukongai never swings light.",
    )

    if won:
        xp_gained = random.randint(12, 20)
        outcome = "Victory"
        description = f"{description} {random.choice(victory_followups)}"
        title = f"{event.title} Won"
    else:
        xp_gained = 5
        outcome = "Setback"
        description = f"{description} {random.choice(setback_followups)}"
        title = f"{event.title} Lost"

    return title, description, xp_gained, outcome


def _resolve_choice_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.choice_events)
    xp_floor = max(3, approach.xp_min - 1)
    xp_ceiling = max(xp_floor, approach.xp_max - 2)
    xp_gained = random.randint(xp_floor, xp_ceiling)
    description = _format_event_description(event, exploration)
    return event.title, description, xp_gained


def _resolve_flavor_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.flavor_events)
    description = _format_event_description(event, exploration)
    return event.title, description, random.randint(2, 4)


def roll_instant_exploration_event(
    exploration: ActiveExploration,
) -> tuple[Literal["reward", "combat", "choice", "flavor"], str, str, int, str | None]:
    event_type = _weighted_event_type(exploration)

    if event_type == "reward":
        title, description, xp_gained = _resolve_reward_event(exploration)
        return "reward", title, description, xp_gained, None

    if event_type == "combat":
        title, description, xp_gained, outcome = _resolve_combat_event(exploration)
        return "combat", title, description, xp_gained, outcome

    if event_type == "choice":
        title, description, xp_gained = _resolve_choice_event(exploration)
        return "choice", title, description, xp_gained, None

    title, description, xp_gained = _resolve_flavor_event(exploration)
    return "flavor", title, description, xp_gained, None


def _resolve_outcome_xp(
    approach: ExploreApproachDefinition,
    xp_profile: Literal[
        "none",
        "approach_low",
        "approach_base",
        "approach_high",
        "combat_win",
        "combat_lose",
        "special_base",
        "special_high",
        "special_combat_win",
        "special_combat_lose",
    ],
) -> int:
    if xp_profile == "none":
        return 0
    if xp_profile == "combat_win":
        return random.randint(12, 20)
    if xp_profile == "combat_lose":
        return 5
    if xp_profile == "special_combat_win":
        return random.randint(max(20, approach.xp_min * 2), max(30, approach.xp_max * 2 + 4))
    if xp_profile == "special_combat_lose":
        return random.randint(max(4, approach.xp_min - 1), max(8, approach.xp_min + 2))
    if xp_profile == "approach_low":
        xp_floor = max(1, approach.xp_min - 3)
        xp_ceiling = max(xp_floor, approach.xp_min)
        return random.randint(xp_floor, xp_ceiling)
    if xp_profile == "approach_high":
        xp_floor = approach.xp_min + 2
        xp_ceiling = max(xp_floor, approach.xp_max + 4)
        return random.randint(xp_floor, xp_ceiling)
    if xp_profile == "special_high":
        xp_floor = max(approach.xp_min * 2, approach.xp_max + 6)
        xp_ceiling = max(xp_floor, approach.xp_max * 2 + 8)
        return random.randint(xp_floor, xp_ceiling)
    if xp_profile == "special_base":
        xp_floor = max(approach.xp_min * 2 - 2, approach.xp_max + 2)
        xp_ceiling = max(xp_floor, approach.xp_max * 2)
        return random.randint(xp_floor, xp_ceiling)

    return random.randint(approach.xp_min, approach.xp_max)


async def _apply_progression_and_reputation(
    connection: Connection,
    user_id: int,
    *,
    location_key: str,
    xp_gained: int,
    reputation_change: int = 0,
) -> tuple[PlayerProfile, int, int]:
    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        raise ValueError(f"Missing player profile for user {user_id}")

    current_player = PlayerProfile.from_record(player_sync.record)
    new_level, new_xp, levels_gained = apply_experience_gain(
        current_level=current_player.level,
        current_xp=current_player.xp,
        xp_gain=xp_gained,
    )

    updates: dict[str, Any] = {
        "level": new_level,
        "xp": new_xp,
    }

    applied_reputation_change = 0
    if reputation_change != 0:
        reputation_field = get_location_reputation_field(location_key)
        current_reputation = get_location_reputation_value(current_player, location_key)
        updated_reputation = apply_reputation_change(current_reputation, reputation_change)
        applied_reputation_change = updated_reputation - current_reputation
        updates[reputation_field] = updated_reputation

    updated_player_record = await update_player_record(connection, user_id, updates)
    return PlayerProfile.from_record(updated_player_record), levels_gained, applied_reputation_change


async def _get_current_player(
    connection: Connection,
    user_id: int,
) -> PlayerProfile:
    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        raise ValueError(f"Missing player profile for user {user_id}")

    return PlayerProfile.from_record(player_sync.record)


def _apply_location_xp_modifier(
    player: PlayerProfile,
    location_key: str,
    base_xp: int,
) -> tuple[int, int]:
    rep_value = get_location_reputation_value(player, location_key)
    return apply_rep_xp(base_xp, rep_value), int(get_reputation_modifiers(rep_value)["xp_modifier"])


def _apply_location_stamina_cost_modifier(
    player: PlayerProfile,
    location_key: str,
    base_cost: int,
) -> tuple[int, int]:
    rep_value = get_location_reputation_value(player, location_key)
    adjusted_cost = apply_rep_stamina_cost(base_cost, rep_value)
    return adjusted_cost, adjusted_cost - base_cost


def _get_instant_reputation_change(
    event_type: Literal["reward", "combat", "choice", "flavor"],
    combat_outcome: str | None,
) -> int:
    return 0


def _should_trigger_special_opportunity(approach: ExploreApproachDefinition) -> bool:
    return _roll_special_trigger(approach)


async def _create_special_offer(
    connection: Connection,
    base_resolution: ExplorationResolution,
    *,
    message_id: int | None = None,
) -> ExplorationDecisionPrompt:
    special_event = get_random_special_event(base_resolution.exploration.location)
    session = await create_pending_exploration_choice(
        connection,
        base_resolution.exploration,
        message_id=message_id,
        event_key=special_event.key,
        event_flow=special_event.flow_type,
        current_step=special_event.initial_step_id,
        session_kind="special_offer",
        special_event_key=special_event.key,
        base_resolution=base_resolution,
    )
    return _build_decision_prompt(session, base_resolution.player)


def _build_resolution_from_pending_base(
    session: PendingExplorationChoice,
    player: PlayerProfile,
    levels_gained: int,
) -> ExplorationResolution:
    if (
        session.base_event_type is None
        or session.base_title is None
        or session.base_description is None
        or session.base_xp is None
    ):
        raise ValueError("Pending special offer is missing its stored base resolution.")

    adjusted_xp, xp_modifier_pct = _apply_location_xp_modifier(
        player,
        session.location,
        session.base_xp,
    )
    base_rep_change = session.base_rep_change or 0

    return ExplorationResolution(
        exploration=session.to_active_exploration(),
        player=player,
        event_type=session.base_event_type,  # type: ignore[arg-type]
        title=session.base_title,
        description=session.base_description,
        xp_gained=adjusted_xp,
        levels_gained=levels_gained,
        base_xp=session.base_xp,
        reputation_xp_modifier_pct=xp_modifier_pct,
        reputation_change=base_rep_change,
        combat_outcome=session.base_combat_outcome,
    )


def _get_combat_lose_profile(xp_profile: str) -> Literal["combat_lose", "special_combat_lose"]:
    return "special_combat_lose" if xp_profile == "special_combat_win" else "combat_lose"


async def _start_instant_combat(
    connection: Connection,
    *,
    exploration: ActiveExploration,
    player: PlayerProfile,
) -> ActiveExplorationCombat:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.combat_events)
    encounter_description = _format_event_description(event, exploration)
    enemy = get_enemy_for_exploration_combat(
        exploration.location,
        encounter_title=event.title,
        approach_risk=approach.risk_tier,
    )
    return await create_active_exploration_combat(
        connection,
        exploration=exploration,
        player=player,
        encounter_title=event.title,
        encounter_description=encounter_description,
        resolution_title=event.title,
        resolution_description=(
            f"The clash in **{get_location_definition(exploration.location).name}** breaks your way. "
            "You force the threat down and keep moving before the block can close around you."
        ),
        reward_xp_win=enemy.reward_xp_win,
        reward_xp_lose=enemy.reward_xp_lose,
        enemy_template=enemy,
    )


async def _start_decision_combat(
    connection: Connection,
    *,
    session: PendingExplorationChoice,
    player: PlayerProfile,
    event_title: str,
    step_description: str,
    selected_label: str,
    resolution_title: str,
    resolution_description: str,
    reward_xp_win: int,
    reward_xp_lose: int,
    reputation_change: int,
    message_id: int | None,
) -> ActiveExplorationCombat:
    exploration = session.to_active_exploration()
    approach = get_explore_approach(session.approach)
    encounter_title = event_title
    encounter_description = (
        f"{step_description}\n\n"
        f"You commit to **{selected_label}**. The next breath turns into a live fight."
    )
    enemy = get_enemy_for_exploration_combat(
        session.location,
        encounter_title=event_title,
        approach_risk=approach.risk_tier,
    )
    return await create_active_exploration_combat(
        connection,
        exploration=exploration,
        player=player,
        encounter_title=encounter_title,
        encounter_description=encounter_description,
        resolution_title=resolution_title,
        resolution_description=resolution_description,
        reward_xp_win=reward_xp_win,
        reward_xp_lose=reward_xp_lose,
        reputation_change=reputation_change,
        enemy_template=enemy,
        message_id=message_id,
    )


async def _finalize_combat_resolution(
    connection: Connection,
    *,
    combat: ActiveExplorationCombat,
    base_xp: int,
    xp_gained: int,
    reputation_xp_modifier_pct: int,
    combat_outcome: str,
    title: str,
    description: str,
    reputation_change: int,
) -> ExplorationResolution:
    player, levels_gained, applied_reputation_change = await _apply_progression_and_reputation(
        connection,
        combat.user_id,
        location_key=combat.location,
        xp_gained=xp_gained,
        reputation_change=reputation_change,
    )

    player_updates: dict[str, Any] = {
        "hp_current": min(
            combat.player_hp_max,
            max(1 if combat_outcome == "Setback" else 0, combat.player_hp_current),
        ),
        "mana_current": max(0, min(combat.player_mana_current, player.mana_max)),
    }
    if combat_outcome == "Setback":
        # TODO: Let future status-effect systems consume and clear this setback hook.
        player_updates["has_minor_setback"] = True
        player_updates["setback_source"] = combat.encounter_title
        player_updates["setback_at"] = datetime.now(timezone.utc)
    updated_player_record = await update_player_record(connection, combat.user_id, player_updates)
    updated_player = PlayerProfile.from_record(updated_player_record)
    await delete_active_exploration_combat(connection, combat.user_id)
    return ExplorationResolution(
        exploration=combat.to_active_exploration(),
        player=updated_player,
        event_type="combat",
        title=title,
        description=description,
        xp_gained=xp_gained,
        levels_gained=levels_gained,
        base_xp=base_xp,
        reputation_xp_modifier_pct=reputation_xp_modifier_pct,
        reputation_change=applied_reputation_change,
        combat_outcome=combat_outcome,
    )


def _build_decision_prompt(
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
            adjusted_cost, stamina_modifier = _apply_location_stamina_cost_modifier(
                player,
                session.location,
                10,
            )
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
        return _build_decision_prompt(session, player)


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
            return _build_decision_prompt(session, player)


async def start_exploration(
    pool: Pool | None,
    user_id: int,
    channel_id: int,
    approach_key: str,
) -> StartExplorationResult:
    if pool is None:
        return StartExplorationResult(status="missing_profile")

    approach = get_explore_approach(approach_key)
    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return StartExplorationResult(status="missing_profile")

            player = PlayerProfile.from_record(player_sync.record)
            rest_minutes = player_sync.resting_minutes
            rest_recovery = player_sync.rest_stamina_gained

            if player.is_resting:
                return StartExplorationResult(
                    status="resting",
                    player=player,
                    rest_minutes=rest_minutes,
                    rest_recovery=rest_recovery,
                )

            pending_choice_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            if pending_choice_record is not None:
                pending_choice = PendingExplorationChoice.from_record(pending_choice_record)
                return StartExplorationResult(
                    status="pending_choice",
                    player=player,
                    pending_choice=_build_decision_prompt(pending_choice, player),
                )

            existing_exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if existing_exploration_record is not None:
                exploration = ActiveExploration.from_record(existing_exploration_record)
                if exploration.end_time > now:
                    return StartExplorationResult(status="active", player=player, exploration=exploration)

                return StartExplorationResult(status="finished", player=player, exploration=exploration)

            stamina_cost, _ = _apply_location_stamina_cost_modifier(
                player,
                player.location,
                approach.stamina_cost,
            )
            if player.stamina_current < stamina_cost:
                return StartExplorationResult(
                    status="insufficient_stamina",
                    player=player,
                    stamina_cost=stamina_cost,
                    base_stamina_cost=approach.stamina_cost,
                )

            updated_player_record = await update_player_record(
                connection,
                user_id,
                {
                    "stamina_current": player.stamina_current - stamina_cost,
                    "stamina_updated_at": now,
                },
            )
            updated_player = PlayerProfile.from_record(updated_player_record)

            exploration = await create_active_exploration(
                connection=connection,
                user_id=user_id,
                channel_id=channel_id,
                location=updated_player.location,
                approach=approach.key,
                start_time=now,
                end_time=now.replace(microsecond=0) + timedelta(minutes=approach.duration_minutes),
            )
            return StartExplorationResult(
                status="started",
                player=updated_player,
                exploration=exploration,
                stamina_cost=stamina_cost,
                base_stamina_cost=approach.stamina_cost,
            )


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
                await delete_active_exploration(connection, user_id)
                return ExplorationPostResult(
                    status="choice_prompt",
                    prompt=_build_decision_prompt(pending_choice),
                )

            approach = get_explore_approach(exploration.approach)
            resolution_flow = _roll_resolution_flow(approach)

            if resolution_flow == "instant":
                current_player = await _get_current_player(connection, user_id)
                event_type = _weighted_event_type(exploration)

                if event_type == "combat":
                    combat = await _start_instant_combat(
                        connection,
                        exploration=exploration,
                        player=current_player,
                    )
                    await delete_active_exploration(connection, user_id)
                    return ExplorationPostResult(status="combat_prompt", combat=combat)

                if event_type == "reward":
                    title, description, base_xp = _resolve_reward_event(exploration)
                    combat_outcome = None
                elif event_type == "choice":
                    title, description, base_xp = _resolve_choice_event(exploration)
                    combat_outcome = None
                else:
                    title, description, base_xp = _resolve_flavor_event(exploration)
                    combat_outcome = None

                adjusted_xp, xp_modifier_pct = _apply_location_xp_modifier(
                    current_player,
                    exploration.location,
                    base_xp,
                )
                reputation_change = _get_instant_reputation_change(event_type, combat_outcome)
                base_resolution = ExplorationResolution(
                    exploration=exploration,
                    player=current_player,
                    event_type=event_type,
                    title=title,
                    description=description,
                    xp_gained=adjusted_xp,
                    levels_gained=0,
                    base_xp=base_xp,
                    reputation_xp_modifier_pct=xp_modifier_pct,
                    reputation_change=reputation_change,
                    combat_outcome=combat_outcome,
                )
                if _should_trigger_special_opportunity(approach):
                    await delete_active_exploration(connection, user_id)
                    prompt = await _create_special_offer(connection, base_resolution, message_id=None)
                    return ExplorationPostResult(status="choice_prompt", prompt=prompt)

                player, levels_gained, applied_reputation_change = await _apply_progression_and_reputation(
                    connection,
                    user_id,
                    location_key=exploration.location,
                    xp_gained=adjusted_xp,
                    reputation_change=reputation_change,
                )
                await delete_active_exploration(connection, user_id)
                resolution = ExplorationResolution(
                    exploration=exploration,
                    player=player,
                    event_type=event_type,
                    title=title,
                    description=description,
                    xp_gained=adjusted_xp,
                    levels_gained=levels_gained,
                    base_xp=base_xp,
                    reputation_xp_modifier_pct=xp_modifier_pct,
                    reputation_change=applied_reputation_change,
                    combat_outcome=combat_outcome,
                )
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
            await delete_active_exploration(connection, user_id)
            return ExplorationPostResult(
                status="choice_prompt",
                prompt=_build_decision_prompt(pending_choice),
            )


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
                current_player = await _get_current_player(connection, user_id)
                if outcome.event_type == "combat":
                    combat = await _start_decision_combat(
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

                adjusted_xp, xp_modifier_pct = _apply_location_xp_modifier(current_player, session.location, outcome.xp_reward)
                player, levels_gained, applied_reputation_change = await _apply_progression_and_reputation(
                    connection,
                    user_id,
                    location_key=session.location,
                    xp_gained=adjusted_xp,
                    reputation_change=outcome.reputation_change,
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
                resolution = ExplorationResolution(
                    exploration=session.to_active_exploration(),
                    player=player,
                    event_type=outcome.event_type,  # type: ignore[arg-type]
                    title=outcome.title,
                    description=outcome.description,
                    xp_gained=adjusted_xp,
                    levels_gained=levels_gained,
                    base_xp=outcome.xp_reward,
                    reputation_xp_modifier_pct=xp_modifier_pct,
                    reputation_change=applied_reputation_change,
                    combat_outcome=outcome.combat_outcome,
                )
                return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)

            if session.session_kind == "special_offer":
                player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
                if player_sync is None:
                    return ExplorationChoiceAdvanceResult(status="missing")

                player = PlayerProfile.from_record(player_sync.record)
                if option_slot == 2:
                    if session.base_xp is None:
                        return ExplorationChoiceAdvanceResult(status="missing")

                    adjusted_xp, _ = _apply_location_xp_modifier(
                        player,
                        session.location,
                        session.base_xp,
                    )
                    player, levels_gained, _ = await _apply_progression_and_reputation(
                        connection,
                        user_id,
                        location_key=session.location,
                        xp_gained=adjusted_xp,
                        reputation_change=session.base_rep_change or 0,
                    )
                    resolution = _build_resolution_from_pending_base(session, player, levels_gained)
                    await delete_pending_choice(connection, user_id)
                    return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)

                if option_slot != 1:
                    return ExplorationChoiceAdvanceResult(status="missing")

                extra_stamina_cost, _ = _apply_location_stamina_cost_modifier(
                    player,
                    session.location,
                    10,
                )
                if player.stamina_current < extra_stamina_cost:
                    return ExplorationChoiceAdvanceResult(
                        status="insufficient_stamina",
                        prompt=_build_decision_prompt(session, player),
                        required_stamina=extra_stamina_cost,
                    )

                special_event_key = session.special_event_key
                if special_event_key is None:
                    return ExplorationChoiceAdvanceResult(status="missing")

                special_event = get_decision_event_definition(session.location, special_event_key)
                now = datetime.now(timezone.utc)
                updated_player_record = await update_player_record(
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
                    prompt=_build_decision_prompt(
                        updated_session,
                        PlayerProfile.from_record(updated_player_record),
                    ),
                )

            current_player = await _get_current_player(connection, user_id)
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
                    prompt=_build_decision_prompt(updated_session, current_player),
                )

            if selected_option.outcome is None:
                return ExplorationChoiceAdvanceResult(status="missing")

            approach = get_explore_approach(session.approach)
            outcome = selected_option.outcome
            base_xp = _resolve_outcome_xp(approach, outcome.xp_profile)
            adjusted_xp, xp_modifier_pct = _apply_location_xp_modifier(
                current_player,
                session.location,
                base_xp,
            )

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
                lose_profile = _get_combat_lose_profile(outcome.xp_profile)
                combat = await _start_decision_combat(
                    connection,
                    session=session,
                    player=current_player,
                    event_title=event.title,
                    step_description=formatted_step_description,
                    selected_label=selected_option.label,
                    resolution_title=outcome.title,
                    resolution_description=formatted_outcome_description,
                    reward_xp_win=base_xp,
                    reward_xp_lose=_resolve_outcome_xp(approach, lose_profile),
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
                xp_gained=adjusted_xp,
                levels_gained=0,
                base_xp=base_xp,
                reputation_xp_modifier_pct=xp_modifier_pct,
                reputation_change=outcome.reputation_change,
                combat_outcome=outcome.combat_outcome,
            )
            if session.session_kind == "decision" and outcome.event_type != "combat" and _should_trigger_special_opportunity(approach):
                await delete_pending_choice(connection, user_id)
                prompt = await _create_special_offer(
                    connection,
                    base_resolution,
                    message_id=session.message_id,
                )
                return ExplorationChoiceAdvanceResult(status="advanced", prompt=prompt)

            player, levels_gained, applied_reputation_change = await _apply_progression_and_reputation(
                connection,
                user_id,
                location_key=session.location,
                xp_gained=adjusted_xp,
                reputation_change=outcome.reputation_change,
            )
            await delete_pending_choice(connection, user_id)
            resolution = ExplorationResolution(
                exploration=session.to_active_exploration(),
                player=player,
                event_type=outcome.event_type,
                title=outcome.title,
                description=formatted_outcome_description,
                xp_gained=adjusted_xp,
                levels_gained=levels_gained,
                base_xp=base_xp,
                reputation_xp_modifier_pct=xp_modifier_pct,
                reputation_change=applied_reputation_change,
                combat_outcome=outcome.combat_outcome,
            )
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
            current_player = await _get_current_player(connection, user_id)
            adjusted_xp, xp_modifier_pct = _apply_location_xp_modifier(
                current_player,
                combat.location,
                base_xp,
            )
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
            resolution = await _finalize_combat_resolution(
                connection,
                combat=resolved_combat,
                base_xp=base_xp,
                xp_gained=adjusted_xp,
                reputation_xp_modifier_pct=xp_modifier_pct,
                combat_outcome=outcome.combat_outcome,
                title=outcome.title,
                description=outcome.description,
                reputation_change=outcome.reputation_change,
            )
            return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)


def build_exploration_result_embed(resolution: ExplorationResolution) -> discord.Embed:
    location = get_location_definition(resolution.exploration.location)
    approach = get_explore_approach(resolution.exploration.approach)
    reputation_title = get_location_reputation_title(
        resolution.player,
        resolution.exploration.location,
    )
    xp_modifier_text = format_reputation_xp_text(
        resolution.reputation_xp_modifier_pct,
        reputation_title,
    )
    color_map = {
        "reward": get_explore_color("reward"),
        "choice": get_explore_color("choice"),
        "combat": get_explore_color("combat"),
        "flavor": get_explore_color("flavor"),
    }
    title_prefix = {
        "reward": "🟩",
        "choice": "🟨",
        "combat": "⚔️",
        "flavor": "⚪",
    }
    embed_title = f"{title_prefix[resolution.event_type]} {resolution.title}"
    if resolution.event_type == "combat" and resolution.combat_outcome is not None:
        embed_title = f"⚔️ {resolution.combat_outcome} — {resolution.title}"

    embed = discord.Embed(
        title=embed_title,
        description=resolution.description,
        color=color_map[resolution.event_type],
    )
    embed.add_field(
        name="This Run",
        value=build_explore_info_lines(
            f"📍 Location: {location.name}",
            f"🧭 Approach: {approach.label}",
            f"⏱ Duration: {approach.duration_minutes} minutes",
            f"🎭 Reputation: {reputation_title}",
        ),
        inline=True,
    )
    embed.add_field(
        name="What Came Of It",
        value=build_explore_info_lines(
            "🎯 XP Gained: **"
            + str(resolution.xp_gained)
            + "**"
            + (f" {xp_modifier_text}" if xp_modifier_text is not None else ""),
            f"📈 Level: **{resolution.player.level}**",
            f"📈 XP Progress: **{resolution.player.xp}**",
            f"🎭 Shift This Run: {format_reputation_change_text(resolution.reputation_change)}",
        ),
        inline=False,
    )

    if resolution.combat_outcome is not None:
        embed.add_field(
            name="Combat Result",
            value=build_explore_info_lines(
                f"⚔ Combat Result: **{resolution.combat_outcome}**",
                f"🎭 Reputation: {reputation_title}",
            ),
            inline=False,
        )
        embed.add_field(
            name="Resources",
            value=build_explore_info_lines(
                f"❤️ HP Remaining: **{resolution.player.hp_current}/{resolution.player.hp_max}**",
                f"🔷 Mana Remaining: **{resolution.player.mana_current}/{resolution.player.mana_max}**",
                f"⚡ Stamina Used This Run: **{approach.stamina_cost}**",
            ),
            inline=False,
        )

    if resolution.combat_outcome == "Setback" and resolution.player.has_minor_setback:
        embed.add_field(
            name="Status Effect",
            value="✨ Minor Setback — a rough outcome is being carried forward for later systems.",
            inline=False,
        )

    if resolution.levels_gained > 0:
        embed.add_field(
            name="Level Up",
            value=f"📈 Your spiritual pressure rises. You climbed **{resolution.levels_gained}** level(s).",
            inline=False,
        )

    add_explore_divider(embed)
    embed.set_footer(text="The streets remember what kind of soul you are.")
    return embed


async def post_exploration_result(bot: "BleachBot", resolution: ExplorationResolution) -> None:
    channel = bot.get_channel(resolution.exploration.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(resolution.exploration.channel_id)
        except discord.HTTPException:
            logging.exception(
                "Could not fetch channel %s for exploration result.",
                resolution.exploration.channel_id,
            )
            return

    if not hasattr(channel, "send"):
        logging.warning("Channel %s is not messageable for exploration result.", resolution.exploration.channel_id)
        return

    embed = build_exploration_result_embed(resolution)
    try:
        await channel.send(content=f"<@{resolution.exploration.user_id}>", embed=embed)
    except discord.HTTPException:
        logging.exception("Failed to send exploration result for user %s.", resolution.exploration.user_id)


async def post_exploration_choice_prompt(
    bot: "BleachBot",
    prompt: ExplorationDecisionPrompt,
) -> None:
    from src.ui.exploration_choice_view import ExplorationChoiceView, build_exploration_choice_embed

    async def _clear_pending_choice() -> None:
        if bot.db_pool is None:
            return

        async with bot.db_pool.acquire() as connection:
            async with connection.transaction():
                await delete_pending_choice(connection, prompt.session.user_id)

    channel = bot.get_channel(prompt.session.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(prompt.session.channel_id)
        except discord.HTTPException:
            logging.exception(
                "Could not fetch channel %s for exploration choice.",
                prompt.session.channel_id,
            )
            await _clear_pending_choice()
            return

    if not hasattr(channel, "send"):
        logging.warning("Channel %s is not messageable for exploration choice.", prompt.session.channel_id)
        await _clear_pending_choice()
        return

    view = ExplorationChoiceView(bot, prompt)
    embed = build_exploration_choice_embed(prompt)
    try:
        message = await channel.send(
            content=f"<@{prompt.session.user_id}>",
            embed=embed,
            view=view,
        )
    except discord.HTTPException:
        logging.exception("Failed to send exploration choice prompt for user %s.", prompt.session.user_id)
        await _clear_pending_choice()
        return

    if bot.db_pool is None:
        return

    async with bot.db_pool.acquire() as connection:
        async with connection.transaction():
            session_record = await fetch_pending_choice_record(connection, prompt.session.user_id, for_update=True)
            if session_record is None:
                return

            await update_pending_choice(
                connection,
                prompt.session.user_id,
                {"message_id": message.id},
            )


async def post_exploration_combat_prompt(
    bot: "BleachBot",
    combat: ActiveExplorationCombat,
) -> None:
    from src.ui.exploration_combat_view import ExplorationCombatView, build_exploration_combat_embed

    async def _clear_active_combat() -> None:
        if bot.db_pool is None:
            return

        async with bot.db_pool.acquire() as connection:
            async with connection.transaction():
                await delete_active_exploration_combat(connection, combat.user_id)

    channel = bot.get_channel(combat.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(combat.channel_id)
        except discord.HTTPException:
            logging.exception(
                "Could not fetch channel %s for exploration combat.",
                combat.channel_id,
            )
            await _clear_active_combat()
            return

    if not hasattr(channel, "send"):
        logging.warning("Channel %s is not messageable for exploration combat.", combat.channel_id)
        await _clear_active_combat()
        return

    view = ExplorationCombatView(bot)
    embed = build_exploration_combat_embed(combat)
    try:
        message = await channel.send(
            content=f"<@{combat.user_id}>",
            embed=embed,
            view=view,
        )
    except discord.HTTPException:
        logging.exception("Failed to send exploration combat prompt for user %s.", combat.user_id)
        await _clear_active_combat()
        return

    if bot.db_pool is None:
        return

    async with bot.db_pool.acquire() as connection:
        async with connection.transaction():
            combat_record = await fetch_active_combat_record(connection, combat.user_id, for_update=True)
            if combat_record is None:
                return

            await update_active_exploration_combat(
                connection,
                combat.user_id,
                {"message_id": message.id},
            )


async def resolve_and_post_exploration(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
) -> ExplorationPostResult | None:
    post_result = await resolve_exploration(bot.db_pool, user_id, force=force)
    if post_result is None:
        return None

    if post_result.status == "instant" and post_result.resolution is not None:
        await post_exploration_result(bot, post_result.resolution)
    elif post_result.status == "choice_prompt" and post_result.prompt is not None:
        await post_exploration_choice_prompt(bot, post_result.prompt)
    elif post_result.status == "combat_prompt" and post_result.combat is not None:
        await post_exploration_combat_prompt(bot, post_result.combat)

    return post_result


async def _run_exploration_task(bot: "BleachBot", exploration: ActiveExploration) -> None:
    try:
        while True:
            delay_seconds = (
                exploration.end_time.astimezone(timezone.utc) - datetime.now(timezone.utc)
            ).total_seconds()
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds + 0.25)

            post_result = await resolve_and_post_exploration(bot, exploration.user_id)
            if post_result is not None:
                break

            refreshed_exploration = await get_active_exploration(bot.db_pool, exploration.user_id)
            if refreshed_exploration is None:
                break

            exploration = refreshed_exploration
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Unexpected error while resolving exploration for user %s.", exploration.user_id)
    finally:
        bot.exploration_tasks.pop(exploration.user_id, None)


def schedule_exploration_task(bot: "BleachBot", exploration: ActiveExploration) -> None:
    existing_task = bot.exploration_tasks.get(exploration.user_id)
    if existing_task is not None:
        existing_task.cancel()

    bot.exploration_tasks[exploration.user_id] = asyncio.create_task(_run_exploration_task(bot, exploration))


async def restore_exploration_tasks(bot: "BleachBot") -> None:
    active_explorations = await list_active_explorations(bot.db_pool)
    for exploration in active_explorations:
        schedule_exploration_task(bot, exploration)


def get_exploration_remaining_time(exploration: ActiveExploration) -> str:
    return format_remaining_duration(exploration.end_time)
