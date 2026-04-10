from __future__ import annotations

from datetime import datetime
from typing import Any

from asyncpg import Connection, Pool, Record

from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.services.exploration.types import ExplorationResolution
from src.services.player_service import set_stamina_resume_timestamp


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


async def close_active_exploration(
    connection: Connection,
    exploration: ActiveExploration,
    *,
    resume_at: datetime | None = None,
) -> None:
    await set_stamina_resume_timestamp(
        connection,
        exploration.user_id,
        resume_at or exploration.end_time,
    )
    await delete_active_exploration(connection, exploration.user_id)


async def delete_pending_choice(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_exploration_choices
        WHERE user_id = $1
        """,
        user_id,
    )
