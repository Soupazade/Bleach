from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from asyncpg import Connection, Pool, Record

from src.services.combat.types import CombatEntity, CombatSession, FightLogRecord


ACTIVE_COMBAT_COLUMNS = """
    fight_id,
    fight_log_id,
    user_id,
    channel_id,
    message_id,
    source_kind,
    location,
    approach,
    encounter_title,
    encounter_description,
    resolution_title,
    resolution_description,
    reward_xp_win,
    reward_xp_lose,
    reputation_change,
    round_number,
    afk_skips,
    last_round_summary,
    turn_deadline_at,
    player_state,
    enemies_state,
    created_at,
    updated_at
"""

FIGHT_LOG_COLUMNS = """
    fight_log_id,
    fight_id,
    user_id,
    source_kind,
    outcome,
    readable_log,
    turn_payloads,
    created_at,
    updated_at,
    finalized_at
"""


def _deserialize_payload(value: Any) -> dict[str, Any] | list[Any]:
    if isinstance(value, str):
        return json.loads(value)
    return value


def session_from_record(record: Record) -> CombatSession:
    player_payload = _deserialize_payload(record["player_state"])
    enemies_payload = _deserialize_payload(record["enemies_state"])
    return CombatSession(
        fight_id=int(record["fight_id"]),
        fight_log_id=int(record["fight_log_id"]),
        user_id=int(record["user_id"]),
        channel_id=int(record["channel_id"]),
        message_id=int(record["message_id"]) if record["message_id"] is not None else None,
        source_kind=str(record["source_kind"]),
        location=str(record["location"]),
        approach=str(record["approach"]),
        encounter_title=str(record["encounter_title"]),
        encounter_description=str(record["encounter_description"]),
        resolution_title=str(record["resolution_title"]),
        resolution_description=str(record["resolution_description"]),
        reward_xp_win=int(record["reward_xp_win"]),
        reward_xp_lose=int(record["reward_xp_lose"]),
        reputation_change=int(record["reputation_change"]),
        round_number=int(record["round_number"]),
        afk_skips=int(record["afk_skips"]),
        last_round_summary=str(record["last_round_summary"]),
        turn_deadline_at=record["turn_deadline_at"],
        player=CombatEntity.from_dict(player_payload),
        enemies=tuple(CombatEntity.from_dict(payload) for payload in enemies_payload),
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


def fight_log_from_record(record: Record) -> FightLogRecord:
    return FightLogRecord(
        fight_log_id=int(record["fight_log_id"]),
        fight_id=int(record["fight_id"]),
        user_id=int(record["user_id"]),
        source_kind=str(record["source_kind"]),
        outcome=None if record["outcome"] is None else str(record["outcome"]),
        readable_log=str(record["readable_log"]),
        turn_payloads=list(_deserialize_payload(record["turn_payloads"])),
        created_at=record["created_at"],
        updated_at=record["updated_at"],
        finalized_at=record["finalized_at"],
    )


async def create_fight_log(
    connection: Connection,
    *,
    user_id: int,
    source_kind: str,
    readable_log: str,
    turn_payloads: list[dict[str, Any]] | None = None,
) -> FightLogRecord:
    record = await connection.fetchrow(
        f"""
        INSERT INTO combat_logs (
            fight_id,
            user_id,
            source_kind,
            outcome,
            readable_log,
            turn_payloads
        )
        VALUES (0, $1, $2, NULL, $3, $4::jsonb)
        RETURNING {FIGHT_LOG_COLUMNS}
        """,
        user_id,
        source_kind,
        readable_log,
        json.dumps(turn_payloads or []),
    )
    return fight_log_from_record(record)


async def bind_fight_log_to_fight(
    connection: Connection,
    *,
    fight_log_id: int,
    fight_id: int,
) -> None:
    await connection.execute(
        """
        UPDATE combat_logs
        SET fight_id = $2, updated_at = NOW()
        WHERE fight_log_id = $1
        """,
        fight_log_id,
        fight_id,
    )


async def fetch_fight_log(connection: Connection, fight_log_id: int) -> FightLogRecord:
    record = await connection.fetchrow(
        f"""
        SELECT {FIGHT_LOG_COLUMNS}
        FROM combat_logs
        WHERE fight_log_id = $1
        """,
        fight_log_id,
    )
    return fight_log_from_record(record)


async def get_fight_log(pool: Pool | None, fight_log_id: int) -> FightLogRecord | None:
    if pool is None:
        return None
    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            f"""
            SELECT {FIGHT_LOG_COLUMNS}
            FROM combat_logs
            WHERE fight_log_id = $1
            """,
            fight_log_id,
        )
        if record is None:
            return None
        return fight_log_from_record(record)


async def append_fight_log_event(
    connection: Connection,
    *,
    fight_log_id: int,
    detail_text: str,
    payload: dict[str, Any],
) -> FightLogRecord:
    current = await fetch_fight_log(connection, fight_log_id)
    payloads = [*current.turn_payloads, payload]
    joined_log = current.readable_log.rstrip() + "\n\n" + detail_text.strip()
    record = await connection.fetchrow(
        f"""
        UPDATE combat_logs
        SET readable_log = $2, turn_payloads = $3::jsonb, updated_at = NOW()
        WHERE fight_log_id = $1
        RETURNING {FIGHT_LOG_COLUMNS}
        """,
        fight_log_id,
        joined_log,
        json.dumps(payloads),
    )
    return fight_log_from_record(record)


async def finalize_fight_log(
    connection: Connection,
    *,
    fight_log_id: int,
    outcome: str,
) -> None:
    await connection.execute(
        """
        UPDATE combat_logs
        SET outcome = $2, finalized_at = NOW(), updated_at = NOW()
        WHERE fight_log_id = $1
        """,
        fight_log_id,
        outcome,
    )


async def create_active_combat(
    connection: Connection,
    *,
    fight_log_id: int,
    user_id: int,
    channel_id: int,
    message_id: int | None,
    source_kind: str,
    location: str,
    approach: str,
    encounter_title: str,
    encounter_description: str,
    resolution_title: str,
    resolution_description: str,
    reward_xp_win: int,
    reward_xp_lose: int,
    reputation_change: int,
    player: CombatEntity,
    enemies: tuple[CombatEntity, ...],
    turn_deadline_at: datetime | None = None,
) -> CombatSession:
    deadline = turn_deadline_at or (datetime.now(timezone.utc) + timedelta(minutes=2))
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_combats (
            fight_log_id,
            user_id,
            channel_id,
            message_id,
            source_kind,
            location,
            approach,
            encounter_title,
            encounter_description,
            resolution_title,
            resolution_description,
            reward_xp_win,
            reward_xp_lose,
            reputation_change,
            round_number,
            afk_skips,
            last_round_summary,
            turn_deadline_at,
            player_state,
            enemies_state
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, 1, 0, $15, $16, $17::jsonb, $18::jsonb
        )
        RETURNING {ACTIVE_COMBAT_COLUMNS}
        """,
        fight_log_id,
        user_id,
        channel_id,
        message_id,
        source_kind,
        location,
        approach,
        encounter_title,
        encounter_description,
        resolution_title,
        resolution_description,
        reward_xp_win,
        reward_xp_lose,
        reputation_change,
        "The pressure snaps tight. One bad exchange and the whole fight tilts.",
        deadline,
        json.dumps(player.to_dict()),
        json.dumps([enemy.to_dict() for enemy in enemies]),
    )
    return session_from_record(record)


async def fetch_active_combat_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_COMBAT_COLUMNS}
        FROM active_combats
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def fetch_active_combat_record_by_message(
    connection: Connection,
    message_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_COMBAT_COLUMNS}
        FROM active_combats
        WHERE message_id = $1
        {lock_clause}
        """,
        message_id,
    )


async def get_active_combat(pool: Pool | None, user_id: int) -> CombatSession | None:
    if pool is None:
        return None
    async with pool.acquire() as connection:
        record = await fetch_active_combat_record(connection, user_id)
        if record is None:
            return None
        return session_from_record(record)


async def get_active_combat_by_message(pool: Pool | None, message_id: int) -> CombatSession | None:
    if pool is None:
        return None
    async with pool.acquire() as connection:
        record = await fetch_active_combat_record_by_message(connection, message_id)
        if record is None:
            return None
        return session_from_record(record)


async def list_active_combats(pool: Pool | None) -> list[CombatSession]:
    if pool is None:
        return []
    async with pool.acquire() as connection:
        records = await connection.fetch(
            f"""
            SELECT {ACTIVE_COMBAT_COLUMNS}
            FROM active_combats
            ORDER BY updated_at ASC
            """
        )
    return [session_from_record(record) for record in records]


async def update_active_combat(
    connection: Connection,
    *,
    fight_id: int,
    session: CombatSession,
    message_id: int | None = None,
) -> CombatSession:
    record = await connection.fetchrow(
        f"""
        UPDATE active_combats
        SET
            message_id = $2,
            round_number = $3,
            afk_skips = $4,
            last_round_summary = $5,
            turn_deadline_at = $6,
            player_state = $7::jsonb,
            enemies_state = $8::jsonb,
            updated_at = NOW()
        WHERE fight_id = $1
        RETURNING {ACTIVE_COMBAT_COLUMNS}
        """,
        fight_id,
        session.message_id if message_id is None else message_id,
        session.round_number,
        session.afk_skips,
        session.last_round_summary,
        session.turn_deadline_at,
        json.dumps(session.player.to_dict()),
        json.dumps([enemy.to_dict() for enemy in session.enemies]),
    )
    return session_from_record(record)


async def update_active_combat_message(
    connection: Connection,
    *,
    fight_id: int,
    message_id: int,
) -> CombatSession:
    record = await connection.fetchrow(
        f"""
        UPDATE active_combats
        SET message_id = $2, updated_at = NOW()
        WHERE fight_id = $1
        RETURNING {ACTIVE_COMBAT_COLUMNS}
        """,
        fight_id,
        message_id,
    )
    return session_from_record(record)


async def delete_active_combat(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_combats
        WHERE user_id = $1
        """,
        user_id,
    )
