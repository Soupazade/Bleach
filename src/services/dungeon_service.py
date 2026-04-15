from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Literal

from asyncpg import Connection, Pool, Record

from src.data.dungeons import (
    DungeonChoiceOptionDefinition,
    DungeonCombatDefinition,
    DungeonDefinition,
    DungeonItemRewardDefinition,
    DungeonRoomDefinition,
    get_dungeon_definition,
    get_first_dungeon_definition,
)
from src.models.dungeon import ActiveDungeonRun, DungeonLootEntry, DungeonProgressState
from src.models.player import PlayerProfile
from src.services.combat.repository import fetch_active_combat_record
from src.services.combat.types import CombatResolutionType, CombatSession
from src.services.combat_service import create_active_dungeon_combat
from src.services.exploration.repository import fetch_active_exploration_record, fetch_pending_choice_record
from src.services.formulas import apply_experience_gain
from src.services.inventory_service import grant_inventory_item_for_connection
from src.services.player_service import get_or_sync_player_record, update_player_record
from src.services.reputation_service import (
    apply_rep_xp,
    apply_reputation_change,
    get_location_reputation_field,
    get_location_reputation_value,
)
from src.services.training_service import fetch_active_training_record
from src.services.travel_service import fetch_active_travel_record


ACTIVE_DUNGEON_COLUMNS = """
    user_id,
    channel_id,
    message_id,
    dungeon_key,
    location,
    current_room_index,
    progress_state,
    created_at,
    updated_at
"""


@dataclass(slots=True)
class StartDungeonResult:
    status: Literal[
        "started",
        "missing_profile",
        "wrong_location",
        "resting",
        "insufficient_stamina",
        "busy",
        "active",
        "active_combat",
    ]
    player: PlayerProfile | None = None
    run: ActiveDungeonRun | None = None
    reason: str | None = None
    stamina_cost: int = 0


@dataclass(slots=True)
class DungeonAdvanceResult:
    status: Literal["missing", "blocked", "updated", "combat", "abandoned"]
    player: PlayerProfile | None = None
    run: ActiveDungeonRun | None = None
    combat: CombatSession | None = None
    message: str | None = None


@dataclass(slots=True)
class DungeonCombatResolutionResult:
    status: Literal["missing", "updated", "completed", "failed"]
    player: PlayerProfile | None = None
    run: ActiveDungeonRun | None = None
    progress: DungeonProgressState | None = None
    outcome: CombatResolutionType | None = None


def _deserialize_progress(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return value
    return {}


async def fetch_active_dungeon_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_DUNGEON_COLUMNS}
        FROM active_dungeons
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def fetch_active_dungeon_record_by_message(
    connection: Connection,
    message_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_DUNGEON_COLUMNS}
        FROM active_dungeons
        WHERE message_id = $1
        {lock_clause}
        """,
        message_id,
    )


async def get_active_dungeon_run(pool: Pool | None, user_id: int) -> ActiveDungeonRun | None:
    if pool is None:
        return None
    async with pool.acquire() as connection:
        record = await fetch_active_dungeon_record(connection, user_id)
        if record is None:
            return None
        return ActiveDungeonRun.from_record(record)


async def get_active_dungeon_run_by_message(pool: Pool | None, message_id: int) -> ActiveDungeonRun | None:
    if pool is None:
        return None
    async with pool.acquire() as connection:
        record = await fetch_active_dungeon_record_by_message(connection, message_id)
        if record is None:
            return None
        return ActiveDungeonRun.from_record(record)


async def create_active_dungeon_run(
    connection: Connection,
    *,
    user_id: int,
    channel_id: int,
    message_id: int | None,
    dungeon_key: str,
    location: str,
    current_room_index: int = 0,
    progress: DungeonProgressState | None = None,
) -> ActiveDungeonRun:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_dungeons (
            user_id,
            channel_id,
            message_id,
            dungeon_key,
            location,
            current_room_index,
            progress_state
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        RETURNING {ACTIVE_DUNGEON_COLUMNS}
        """,
        user_id,
        channel_id,
        message_id,
        dungeon_key,
        location,
        current_room_index,
        json.dumps((progress or DungeonProgressState()).to_dict()),
    )
    return ActiveDungeonRun.from_record(record)


async def update_active_dungeon_run(
    connection: Connection,
    user_id: int,
    *,
    message_id: int | None | object = None,
    current_room_index: int | None = None,
    progress: DungeonProgressState | None = None,
) -> ActiveDungeonRun:
    assignments: list[str] = []
    values: list[Any] = []

    if message_id is not None:
        assignments.append(f"message_id = ${len(values) + 1}")
        values.append(message_id)
    if current_room_index is not None:
        assignments.append(f"current_room_index = ${len(values) + 1}")
        values.append(current_room_index)
    if progress is not None:
        assignments.append(f"progress_state = ${len(values) + 1}::jsonb")
        values.append(json.dumps(progress.to_dict()))

    values.append(user_id)
    record = await connection.fetchrow(
        f"""
        UPDATE active_dungeons
        SET {", ".join(assignments)}, updated_at = NOW()
        WHERE user_id = ${len(values)}
        RETURNING {ACTIVE_DUNGEON_COLUMNS}
        """,
        *values,
    )
    return ActiveDungeonRun.from_record(record)


async def delete_active_dungeon_run(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_dungeons
        WHERE user_id = $1
        """,
        user_id,
    )


def get_dungeon_room(run: ActiveDungeonRun) -> DungeonRoomDefinition:
    definition = get_dungeon_definition(run.dungeon_key)
    return definition.rooms[run.current_room_index]


def get_dungeon_definition_for_run(run: ActiveDungeonRun) -> DungeonDefinition:
    return get_dungeon_definition(run.dungeon_key)


def _merge_loot_entries(
    current_items: tuple[DungeonLootEntry, ...],
    granted_items: tuple[DungeonLootEntry, ...],
) -> tuple[DungeonLootEntry, ...]:
    merged: dict[str, DungeonLootEntry] = {
        item.item_key: DungeonLootEntry(
            item_key=item.item_key,
            item_name=item.item_name,
            quantity=item.quantity,
        )
        for item in current_items
    }
    for item in granted_items:
        existing = merged.get(item.item_key)
        if existing is None:
            merged[item.item_key] = DungeonLootEntry(
                item_key=item.item_key,
                item_name=item.item_name,
                quantity=item.quantity,
            )
            continue
        existing.quantity += item.quantity
    return tuple(merged.values())


def build_progress_update(
    progress: DungeonProgressState,
    *,
    xp_gain: int = 0,
    kan_gain: int = 0,
    reputation_gain: int = 0,
    granted_items: tuple[DungeonLootEntry, ...] = (),
    history_entry: str | None = None,
) -> DungeonProgressState:
    history = progress.history
    if history_entry:
        history = (*history, history_entry)
    return DungeonProgressState(
        total_xp=progress.total_xp + xp_gain,
        total_kan=progress.total_kan + kan_gain,
        total_reputation=progress.total_reputation + reputation_gain,
        history=history,
        items=_merge_loot_entries(progress.items, granted_items),
    )


async def _grant_item_rewards(
    connection: Connection,
    *,
    user_id: int,
    source_text: str,
    item_rewards: tuple[DungeonItemRewardDefinition, ...],
) -> tuple[DungeonLootEntry, ...]:
    granted: list[DungeonLootEntry] = []
    for reward in item_rewards:
        await grant_inventory_item_for_connection(
            connection,
            user_id=user_id,
            item_key=reward.key,
            item_name=reward.name,
            quantity=reward.quantity,
            item_description=reward.description,
            item_type=reward.item_type,
            rarity=reward.rarity,
            stackable=reward.stackable,
            source_text=source_text,
        )
        granted.append(
            DungeonLootEntry(
                item_key=reward.key,
                item_name=reward.name,
                quantity=reward.quantity,
            )
        )
    return tuple(granted)


async def _apply_player_rewards(
    connection: Connection,
    *,
    player: PlayerProfile,
    location_key: str,
    xp_gain: int = 0,
    kan_gain: int = 0,
    reputation_change: int = 0,
    heal_hp: int = 0,
    heal_stamina: int = 0,
) -> tuple[PlayerProfile, int, int, int]:
    adjusted_xp = apply_rep_xp(xp_gain, get_location_reputation_value(player, location_key))
    new_level, new_xp, _, applied_xp = apply_experience_gain(
        current_level=player.level,
        current_xp=player.xp,
        xp_gain=adjusted_xp,
    )

    updates: dict[str, Any] = {
        "level": new_level,
        "xp": new_xp,
    }
    applied_kan = max(0, kan_gain)
    if applied_kan > 0:
        updates["kan"] = player.kan + applied_kan
    if heal_hp != 0:
        updates["hp_current"] = max(1, min(player.hp_max, player.hp_current + heal_hp))
    if heal_stamina != 0:
        updates["stamina_current"] = max(0, min(player.stamina_max, player.stamina_current + heal_stamina))

    applied_reputation_change = 0
    if reputation_change != 0:
        reputation_field = get_location_reputation_field(location_key)
        current_reputation = get_location_reputation_value(player, location_key)
        updated_reputation = apply_reputation_change(current_reputation, reputation_change)
        applied_reputation_change = updated_reputation - current_reputation
        updates[reputation_field] = updated_reputation

    updated_record = await update_player_record(connection, player.user_id, updates)
    return PlayerProfile.from_record(updated_record), applied_xp, applied_kan, applied_reputation_change


def _busy_reason_from_records(
    *,
    active_exploration: Record | None,
    pending_choice: Record | None,
    active_training: Record | None,
    active_travel: Record | None,
) -> str | None:
    if pending_choice is not None:
        return "A street decision is still waiting on you."
    if active_exploration is not None:
        return "Finish your current exploration first."
    if active_training is not None:
        return "Finish your training first."
    if active_travel is not None:
        return "Finish your travel first."
    return None


async def start_first_dungeon(
    pool: Pool | None,
    *,
    user_id: int,
    channel_id: int,
) -> StartDungeonResult:
    if pool is None:
        return StartDungeonResult(status="missing_profile")

    dungeon = get_first_dungeon_definition()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return StartDungeonResult(status="missing_profile")

            player = PlayerProfile.from_record(player_sync.record)
            if player.location != dungeon.location_key:
                return StartDungeonResult(status="wrong_location", player=player)
            if player.is_resting:
                return StartDungeonResult(status="resting", player=player)

            if await fetch_active_dungeon_record(connection, user_id, for_update=True) is not None:
                record = await fetch_active_dungeon_record(connection, user_id, for_update=True)
                return StartDungeonResult(
                    status="active",
                    player=player,
                    run=ActiveDungeonRun.from_record(record) if record is not None else None,
                )

            if await fetch_active_combat_record(connection, user_id, for_update=True) is not None:
                return StartDungeonResult(status="active_combat", player=player)

            active_exploration = await fetch_active_exploration_record(connection, user_id, for_update=True)
            pending_choice = await fetch_pending_choice_record(connection, user_id, for_update=True)
            active_training = await fetch_active_training_record(connection, user_id, for_update=True)
            active_travel = await fetch_active_travel_record(connection, user_id, for_update=True)
            busy_reason = _busy_reason_from_records(
                active_exploration=active_exploration,
                pending_choice=pending_choice,
                active_training=active_training,
                active_travel=active_travel,
            )
            if busy_reason is not None:
                return StartDungeonResult(status="busy", player=player, reason=busy_reason)

            if player.stamina_current < dungeon.stamina_cost:
                return StartDungeonResult(
                    status="insufficient_stamina",
                    player=player,
                    stamina_cost=dungeon.stamina_cost,
                )

            updated_player_record = await update_player_record(
                connection,
                user_id,
                {
                    "stamina_current": player.stamina_current - dungeon.stamina_cost,
                    "stamina_updated_at": now,
                },
            )
            updated_player = PlayerProfile.from_record(updated_player_record)
            run = await create_active_dungeon_run(
                connection,
                user_id=user_id,
                channel_id=channel_id,
                message_id=None,
                dungeon_key=dungeon.key,
                location=dungeon.location_key,
                progress=DungeonProgressState(),
            )
            return StartDungeonResult(
                status="started",
                player=updated_player,
                run=run,
                stamina_cost=dungeon.stamina_cost,
            )


async def bind_dungeon_message(
    pool: Pool | None,
    *,
    user_id: int,
    message_id: int,
) -> ActiveDungeonRun | None:
    if pool is None:
        return None
    async with pool.acquire() as connection:
        async with connection.transaction():
            if await fetch_active_dungeon_record(connection, user_id, for_update=True) is None:
                return None
            return await update_active_dungeon_run(
                connection,
                user_id,
                message_id=message_id,
            )


async def advance_dungeon_room(
    pool: Pool | None,
    *,
    message_id: int,
    user_id: int,
    option_slot: int,
) -> DungeonAdvanceResult:
    if pool is None:
        return DungeonAdvanceResult(status="missing")

    async with pool.acquire() as connection:
        async with connection.transaction():
            record = await fetch_active_dungeon_record_by_message(connection, message_id, for_update=True)
            if record is None:
                return DungeonAdvanceResult(status="missing")

            run = ActiveDungeonRun.from_record(record)
            if run.user_id != user_id:
                return DungeonAdvanceResult(status="missing")

            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                await delete_active_dungeon_run(connection, user_id)
                return DungeonAdvanceResult(status="missing")
            player = PlayerProfile.from_record(player_sync.record)

            room = get_dungeon_room(run)
            if room.kind == "choice":
                if option_slot < 1 or option_slot > len(room.options):
                    return DungeonAdvanceResult(status="blocked", run=run, player=player, message="That path is not available.")
                option = room.options[option_slot - 1]
                updated_player, applied_xp, applied_kan, applied_rep = await _apply_player_rewards(
                    connection,
                    player=player,
                    location_key=run.location,
                    xp_gain=option.xp_reward,
                    kan_gain=option.kan_reward,
                    reputation_change=option.reputation_change,
                    heal_hp=option.heal_hp,
                    heal_stamina=option.heal_stamina,
                )
                granted_items = await _grant_item_rewards(
                    connection,
                    user_id=user_id,
                    source_text=get_dungeon_definition(run.dungeon_key).title,
                    item_rewards=option.item_rewards,
                )
                progress = build_progress_update(
                    run.progress,
                    xp_gain=applied_xp,
                    kan_gain=applied_kan,
                    reputation_gain=applied_rep,
                    granted_items=granted_items,
                    history_entry=option.summary_text,
                )
                updated_run = await update_active_dungeon_run(
                    connection,
                    user_id,
                    current_room_index=run.current_room_index + 1,
                    progress=progress,
                )
                return DungeonAdvanceResult(status="updated", run=updated_run, player=updated_player)

            if option_slot != 1 or room.combat is None:
                return DungeonAdvanceResult(status="blocked", run=run, player=player, message="There is only one clean way forward here.")

            combat = await create_active_dungeon_combat(
                connection,
                user_id=user_id,
                channel_id=run.channel_id,
                message_id=run.message_id,
                location=run.location,
                approach=run.dungeon_key,
                player=player,
                room=room,
            )
            return DungeonAdvanceResult(status="combat", run=run, player=player, combat=combat)


async def abandon_dungeon_run(
    pool: Pool | None,
    *,
    user_id: int,
    message_id: int,
) -> DungeonAdvanceResult:
    if pool is None:
        return DungeonAdvanceResult(status="missing")

    async with pool.acquire() as connection:
        async with connection.transaction():
            record = await fetch_active_dungeon_record_by_message(connection, message_id, for_update=True)
            if record is None:
                return DungeonAdvanceResult(status="missing")
            run = ActiveDungeonRun.from_record(record)
            if run.user_id != user_id:
                return DungeonAdvanceResult(status="missing")
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            player = None if player_sync is None else PlayerProfile.from_record(player_sync.record)
            await delete_active_dungeon_run(connection, user_id)
            return DungeonAdvanceResult(status="abandoned", run=run, player=player)


async def resolve_dungeon_combat(
    pool: Pool | None,
    *,
    user_id: int,
    outcome: CombatResolutionType,
) -> DungeonCombatResolutionResult:
    if pool is None:
        return DungeonCombatResolutionResult(status="missing", outcome=outcome)

    async with pool.acquire() as connection:
        async with connection.transaction():
            record = await fetch_active_dungeon_record(connection, user_id, for_update=True)
            if record is None:
                return DungeonCombatResolutionResult(status="missing", outcome=outcome)

            run = ActiveDungeonRun.from_record(record)
            room = get_dungeon_room(run)
            combat_definition = room.combat
            if combat_definition is None:
                return DungeonCombatResolutionResult(status="missing", outcome=outcome)

            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                await delete_active_dungeon_run(connection, user_id)
                return DungeonCombatResolutionResult(status="missing", outcome=outcome)
            player = PlayerProfile.from_record(player_sync.record)

            if outcome == "victory":
                updated_player, applied_xp, applied_kan, applied_rep = await _apply_player_rewards(
                    connection,
                    player=player,
                    location_key=run.location,
                    xp_gain=combat_definition.xp_reward_win,
                    kan_gain=combat_definition.kan_reward_win,
                    reputation_change=combat_definition.reputation_change_win,
                )
                granted_items = await _grant_item_rewards(
                    connection,
                    user_id=user_id,
                    source_text=get_dungeon_definition(run.dungeon_key).title,
                    item_rewards=combat_definition.item_rewards_win,
                )
                progress = build_progress_update(
                    run.progress,
                    xp_gain=applied_xp,
                    kan_gain=applied_kan,
                    reputation_gain=applied_rep,
                    granted_items=granted_items,
                    history_entry=combat_definition.victory_summary_text,
                )
                next_room_index = run.current_room_index + 1
                if next_room_index >= len(get_dungeon_definition(run.dungeon_key).rooms):
                    await delete_active_dungeon_run(connection, user_id)
                    return DungeonCombatResolutionResult(
                        status="completed",
                        player=updated_player,
                        progress=progress,
                        outcome=outcome,
                    )
                updated_run = await update_active_dungeon_run(
                    connection,
                    user_id,
                    current_room_index=next_room_index,
                    progress=progress,
                )
                return DungeonCombatResolutionResult(
                    status="updated",
                    player=updated_player,
                    run=updated_run,
                    progress=progress,
                    outcome=outcome,
                )

            updated_player, applied_xp, _, _ = await _apply_player_rewards(
                connection,
                player=player,
                location_key=run.location,
                xp_gain=combat_definition.xp_reward_lose,
            )
            progress = build_progress_update(
                run.progress,
                xp_gain=applied_xp,
                history_entry=combat_definition.failure_summary_text,
            )
            await delete_active_dungeon_run(connection, user_id)
            return DungeonCombatResolutionResult(
                status="failed",
                player=updated_player,
                progress=progress,
                outcome=outcome,
            )


def get_room_options(room: DungeonRoomDefinition) -> tuple[DungeonChoiceOptionDefinition, ...]:
    if room.kind == "choice":
        return room.options
    if room.combat is None:
        return ()
    return (
        DungeonChoiceOptionDefinition(
            key="advance",
            label="Push forward",
            style="danger" if room.kind == "boss" else "primary",
            summary_text="",
        ),
    )
