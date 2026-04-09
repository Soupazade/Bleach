from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random

from asyncpg import Connection, Pool, Record

from src.data.npcs import (
    NpcEncounterDefinition,
    RecurringNpcDefinition,
    get_location_npcs,
    get_npc_definition,
    get_npc_encounter,
)
from src.models.npc import PlayerNpcProgress


PLAYER_NPC_PROGRESS_COLUMNS = """
    user_id,
    npc_id,
    state,
    stage,
    last_encounter_at,
    created_at,
    updated_at
"""


@dataclass(frozen=True, slots=True)
class EligibleNpcEncounter:
    npc: RecurringNpcDefinition
    encounter: NpcEncounterDefinition
    progress: PlayerNpcProgress | None


async def fetch_player_npc_progress_record(
    connection: Connection,
    user_id: int,
    npc_id: str,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {PLAYER_NPC_PROGRESS_COLUMNS}
        FROM player_npc_progress
        WHERE user_id = $1
          AND npc_id = $2
        {lock_clause}
        """,
        user_id,
        npc_id,
    )


async def get_player_npc_progress(
    pool: Pool | None,
    user_id: int,
    npc_id: str,
) -> PlayerNpcProgress | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_player_npc_progress_record(connection, user_id, npc_id)
        if record is None:
            return None

        return PlayerNpcProgress.from_record(record)


async def upsert_player_npc_progress(
    connection: Connection,
    *,
    user_id: int,
    npc_id: str,
    state: str,
    stage: int,
    last_encounter_at: datetime,
) -> PlayerNpcProgress:
    record = await connection.fetchrow(
        f"""
        INSERT INTO player_npc_progress (
            user_id,
            npc_id,
            state,
            stage,
            last_encounter_at
        )
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, npc_id)
        DO UPDATE SET
            state = EXCLUDED.state,
            stage = EXCLUDED.stage,
            last_encounter_at = EXCLUDED.last_encounter_at,
            updated_at = NOW()
        RETURNING {PLAYER_NPC_PROGRESS_COLUMNS}
        """,
        user_id,
        npc_id,
        state,
        stage,
        last_encounter_at,
    )
    return PlayerNpcProgress.from_record(record)


def _is_npc_on_cooldown(
    npc: RecurringNpcDefinition,
    progress: PlayerNpcProgress | None,
    now: datetime,
) -> bool:
    if progress is None or progress.last_encounter_at is None:
        return False

    return now < progress.last_encounter_at + timedelta(minutes=npc.cooldown_minutes)


def _roll_npc_encounter(npc: RecurringNpcDefinition, stage: int) -> bool:
    return random.random() < npc.get_stage_chance(stage)


async def get_eligible_npc_encounter(
    connection: Connection,
    *,
    user_id: int,
    location_key: str,
) -> EligibleNpcEncounter | None:
    now = datetime.now(timezone.utc)

    for npc in get_location_npcs(location_key):
        progress_record = await fetch_player_npc_progress_record(connection, user_id, npc.id, for_update=True)
        progress = PlayerNpcProgress.from_record(progress_record) if progress_record is not None else None
        current_stage = progress.stage if progress is not None else 0
        current_state = progress.state if progress is not None else "default"

        if current_stage >= 3:
            continue

        if _is_npc_on_cooldown(npc, progress, now):
            continue

        encounter = get_npc_encounter(npc.id, stage=current_stage, state=current_state)
        if encounter is None:
            continue

        if not _roll_npc_encounter(npc, current_stage):
            continue

        return EligibleNpcEncounter(
            npc=npc,
            encounter=encounter,
            progress=progress,
        )

    return None


def get_npc_encounter_definition(
    npc_id: str,
    encounter_key: str,
) -> NpcEncounterDefinition:
    npc = get_npc_definition(npc_id)
    for encounter in npc.encounters.values():
        if encounter.key == encounter_key:
            return encounter

    raise ValueError(f"Unknown NPC encounter: {npc_id}:{encounter_key}")
