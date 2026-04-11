from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncpg import Connection, Pool, Record

from src.data.items import get_item_definition
from src.data.quests import QUEST_DEFINITIONS, get_quest_definition, list_quests_for_category
from src.models.player import PlayerProfile
from src.models.quest import (
    QuestActionType,
    QuestCategory,
    QuestDefinition,
    QuestProgressUpdate,
    QuestRewardItemGrant,
    PlayerQuestRecord,
)
from src.services.formulas import apply_experience_gain
from src.services.inventory_service import grant_inventory_item_for_connection
from src.services.player_service import get_or_sync_player_record, update_player_record


PLAYER_QUEST_COLUMNS = """
    user_id,
    quest_key,
    status,
    current_step_index,
    started_at,
    completed_at,
    created_at,
    updated_at
"""

QUEST_CATEGORY_ORDER: tuple[QuestCategory, ...] = ("main", "side", "daily", "repeatable")
QUEST_CATEGORY_LABELS: dict[QuestCategory, str] = {
    "main": "Main Quests",
    "side": "Side Quests",
    "daily": "Daily Quests",
    "repeatable": "Repeatable Quests",
}


@dataclass(slots=True)
class PlayerQuestEntry:
    quest: QuestDefinition
    state: str
    current_step_index: int = 0
    completed_at: object | None = None


@dataclass(slots=True)
class PlayerQuestBoard:
    player: PlayerProfile
    quests_by_category: dict[QuestCategory, list[PlayerQuestEntry]]


async def fetch_player_quest_record(
    connection: Connection,
    user_id: int,
    quest_key: str,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {PLAYER_QUEST_COLUMNS}
        FROM player_quests
        WHERE user_id = $1
          AND quest_key = $2
        {lock_clause}
        """,
        user_id,
        quest_key,
    )


async def list_player_quest_records(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> list[PlayerQuestRecord]:
    lock_clause = " FOR UPDATE" if for_update else ""
    records = await connection.fetch(
        f"""
        SELECT {PLAYER_QUEST_COLUMNS}
        FROM player_quests
        WHERE user_id = $1
        ORDER BY created_at ASC
        {lock_clause}
        """,
        user_id,
    )
    return [PlayerQuestRecord.from_record(record) for record in records]


async def create_player_quest_record(
    connection: Connection,
    *,
    user_id: int,
    quest_key: str,
    status: str = "active",
    current_step_index: int = 0,
) -> PlayerQuestRecord:
    record = await connection.fetchrow(
        f"""
        INSERT INTO player_quests (
            user_id,
            quest_key,
            status,
            current_step_index,
            started_at
        )
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (user_id, quest_key) DO UPDATE
        SET updated_at = NOW()
        RETURNING {PLAYER_QUEST_COLUMNS}
        """,
        user_id,
        quest_key,
        status,
        current_step_index,
    )
    return PlayerQuestRecord.from_record(record)


async def update_player_quest_record(
    connection: Connection,
    *,
    user_id: int,
    quest_key: str,
    status: str,
    current_step_index: int,
    completed: bool = False,
) -> PlayerQuestRecord:
    completed_sql = "NOW()" if completed else "completed_at"
    record = await connection.fetchrow(
        f"""
        UPDATE player_quests
        SET
            status = $3,
            current_step_index = $4,
            completed_at = {completed_sql},
            updated_at = NOW()
        WHERE user_id = $1
          AND quest_key = $2
        RETURNING {PLAYER_QUEST_COLUMNS}
        """,
        user_id,
        quest_key,
        status,
        current_step_index,
    )
    return PlayerQuestRecord.from_record(record)


def _matches_requirement(record: PlayerQuestRecord, quest: QuestDefinition, action_type: QuestActionType, context: dict[str, Any]) -> bool:
    if record.status != "active":
        return False
    if record.current_step_index < 0 or record.current_step_index >= len(quest.steps):
        return False

    requirement = quest.steps[record.current_step_index].requirement
    if requirement.action_type != action_type:
        return False

    if requirement.accepted_item_keys:
        crafted_item_key = str(context.get("item_key", ""))
        if crafted_item_key not in requirement.accepted_item_keys:
            return False

    if requirement.required_location is not None:
        location_key = str(context.get("location_key", ""))
        if location_key != requirement.required_location:
            return False

    return True


async def ensure_auto_start_quests_for_connection(
    connection: Connection,
    player: PlayerProfile,
) -> list[PlayerQuestRecord]:
    created_records: list[PlayerQuestRecord] = []
    for quest in QUEST_DEFINITIONS.values():
        if not quest.auto_start or player.level < quest.min_level:
            continue

        existing = await fetch_player_quest_record(
            connection,
            player.user_id,
            quest.key,
            for_update=True,
        )
        if existing is not None:
            continue

        created_records.append(
            await create_player_quest_record(
                connection,
                user_id=player.user_id,
                quest_key=quest.key,
            )
        )
    return created_records


async def ensure_auto_start_quests(
    pool: Pool | None,
    user_id: int,
) -> None:
    if pool is None:
        return

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return

            await ensure_auto_start_quests_for_connection(
                connection,
                PlayerProfile.from_record(player_sync.record),
            )


async def get_player_quest_board(
    pool: Pool | None,
    user_id: int,
) -> PlayerQuestBoard | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return None

            player = PlayerProfile.from_record(player_sync.record)
            await ensure_auto_start_quests_for_connection(connection, player)
            records = await list_player_quest_records(connection, user_id, for_update=True)

    records_by_key = {record.quest_key: record for record in records}
    quests_by_category: dict[QuestCategory, list[PlayerQuestEntry]] = {
        category: [] for category in QUEST_CATEGORY_ORDER
    }
    for category in QUEST_CATEGORY_ORDER:
        for quest in list_quests_for_category(category):
            if player.level < quest.min_level:
                continue

            record = records_by_key.get(quest.key)
            if record is None:
                quests_by_category[category].append(
                    PlayerQuestEntry(quest=quest, state="available")
                )
                continue

            quests_by_category[category].append(
                PlayerQuestEntry(
                    quest=quest,
                    state=record.status,
                    current_step_index=record.current_step_index,
                    completed_at=record.completed_at,
                )
            )

    return PlayerQuestBoard(player=player, quests_by_category=quests_by_category)


async def accept_quest(
    pool: Pool | None,
    user_id: int,
    quest_key: str,
) -> str:
    if pool is None:
        return "missing_profile"

    try:
        quest = get_quest_definition(quest_key)
    except ValueError:
        return "invalid_quest"

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return "missing_profile"

            player = PlayerProfile.from_record(player_sync.record)
            if player.level < quest.min_level:
                return "ineligible"

            existing_record = await fetch_player_quest_record(
                connection,
                user_id,
                quest_key,
                for_update=True,
            )
            if existing_record is not None:
                existing = PlayerQuestRecord.from_record(existing_record)
                if existing.status == "completed":
                    return "completed"
                return "active"

            await create_player_quest_record(
                connection,
                user_id=user_id,
                quest_key=quest_key,
                status="active",
                current_step_index=0,
            )
            return "accepted"


async def reset_quest(
    pool: Pool | None,
    user_id: int,
    quest_key: str,
) -> str:
    if pool is None:
        return "missing_profile"

    try:
        get_quest_definition(quest_key)
    except ValueError:
        return "invalid_quest"

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return "missing_profile"

            existing_record = await fetch_player_quest_record(
                connection,
                user_id,
                quest_key,
                for_update=True,
            )
            if existing_record is None:
                return "not_active"

            existing = PlayerQuestRecord.from_record(existing_record)
            if existing.status == "completed":
                return "completed"

            await connection.execute(
                """
                DELETE FROM player_quests
                WHERE user_id = $1
                  AND quest_key = $2
                """,
                user_id,
                quest_key,
            )
            return "reset"


async def _apply_quest_rewards(
    connection: Connection,
    *,
    user_id: int,
    quest: QuestDefinition,
) -> tuple[int, int, int, int, tuple[QuestRewardItemGrant, ...]]:
    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        return 0, 0, 0, 0, ()

    player = PlayerProfile.from_record(player_sync.record)
    new_level, new_xp, levels_gained, applied_xp = apply_experience_gain(
        current_level=player.level,
        current_xp=player.xp,
        xp_gain=quest.reward.xp,
    )
    await update_player_record(
        connection,
        user_id,
        {
            "level": new_level,
            "xp": new_xp,
            "kan": player.kan + quest.reward.kan,
            "unspent_stat_points": player.unspent_stat_points + quest.reward.stat_points,
        },
    )

    granted_items: list[QuestRewardItemGrant] = []
    for reward_item in quest.reward.items:
        item_definition = get_item_definition(reward_item.item_key)
        await grant_inventory_item_for_connection(
            connection,
            user_id=user_id,
            item_key=item_definition.key,
            item_name=item_definition.name,
            quantity=reward_item.quantity,
            item_description=item_definition.description,
            item_type=item_definition.item_type,
            rarity=item_definition.rarity,
            stackable=item_definition.stackable,
            source_text=quest.title,
        )
        granted_items.append(
            QuestRewardItemGrant(
                item_key=item_definition.key,
                item_name=item_definition.name,
                quantity=reward_item.quantity,
            )
        )

    return applied_xp, quest.reward.kan, quest.reward.stat_points, levels_gained, tuple(granted_items)


async def record_quest_action_for_connection(
    connection: Connection,
    user_id: int,
    action_type: QuestActionType,
    **context: Any,
) -> tuple[QuestProgressUpdate, ...]:
    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        return ()

    player = PlayerProfile.from_record(player_sync.record)
    await ensure_auto_start_quests_for_connection(connection, player)
    records = await list_player_quest_records(connection, user_id, for_update=True)

    updates: list[QuestProgressUpdate] = []
    for record in records:
        quest = get_quest_definition(record.quest_key)
        if not _matches_requirement(record, quest, action_type, context):
            continue

        previous_step_index = record.current_step_index
        next_step_index = previous_step_index + 1
        if next_step_index >= len(quest.steps):
            applied_xp, kan_gained, stat_points_gained, levels_gained, granted_items = await _apply_quest_rewards(
                connection,
                user_id=user_id,
                quest=quest,
            )
            await update_player_quest_record(
                connection,
                user_id=user_id,
                quest_key=quest.key,
                status="completed",
                current_step_index=len(quest.steps),
                completed=True,
            )
            updates.append(
                QuestProgressUpdate(
                    quest=quest,
                    status="completed",
                    previous_step_index=previous_step_index,
                    current_step_index=len(quest.steps),
                    xp_gained=applied_xp,
                    kan_gained=kan_gained,
                    stat_points_gained=stat_points_gained,
                    levels_gained=levels_gained,
                    granted_items=granted_items,
                )
            )
            continue

        await update_player_quest_record(
            connection,
            user_id=user_id,
            quest_key=quest.key,
            status="active",
            current_step_index=next_step_index,
        )
        updates.append(
            QuestProgressUpdate(
                quest=quest,
                status="advanced",
                previous_step_index=previous_step_index,
                current_step_index=next_step_index,
            )
        )

    return tuple(updates)


async def record_quest_action(
    pool: Pool | None,
    user_id: int,
    action_type: QuestActionType,
    **context: Any,
) -> tuple[QuestProgressUpdate, ...]:
    if pool is None:
        return ()

    async with pool.acquire() as connection:
        async with connection.transaction():
            return await record_quest_action_for_connection(
                connection,
                user_id,
                action_type,
                **context,
            )
