from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from asyncpg import Connection, Pool, Record

from src.data.game_constants import (
    DEFAULT_LOCATION_KEY,
    STARTING_HP,
    STARTING_LEVEL,
    STARTING_MANA,
    STARTING_RACE,
    STARTING_RANK,
    STARTING_STAMINA,
    STARTING_XP,
)
from src.data.traits import roll_random_soul_trait
from src.models.player import PlayerProfile
from src.services.formulas import (
    calculate_minutes_elapsed,
    calculate_passive_stamina_recovery,
    calculate_rest_stamina_recovery,
)


PLAYER_PROFILE_COLUMNS = """
    user_id,
    race,
    rank,
    level,
    xp,
    hp_current,
    hp_max,
    stamina_current,
    stamina_max,
    mana_current,
    mana_max,
    power,
    defense,
    speed,
    reiatsu,
    trait,
    location,
    rukongai_rep,
    has_minor_setback,
    setback_source,
    setback_at,
    is_resting,
    rest_start_time,
    rest_stamina_snapshot,
    stamina_updated_at,
    created_at
"""


@dataclass(slots=True)
class ResourceSyncResult:
    record: Record
    passive_stamina_gained: int = 0
    rest_stamina_gained: int = 0
    resting_minutes: int = 0


@dataclass(slots=True)
class TimedActivityWindow:
    activity_type: str
    start_time: datetime
    end_time: datetime


async def has_legacy_discord_user_id_column(connection: Connection) -> bool:
    return await connection.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'player_profiles'
              AND column_name = 'discord_user_id'
        )
        """
    )


async def fetch_player_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {PLAYER_PROFILE_COLUMNS}
        FROM player_profiles
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def update_player_record(
    connection: Connection,
    user_id: int,
    fields: dict[str, Any],
) -> Record:
    assignments: list[str] = []
    values: list[Any] = []

    for index, (column_name, value) in enumerate(fields.items(), start=1):
        assignments.append(f"{column_name} = ${index}")
        values.append(value)

    user_id_placeholder = len(values) + 1
    values.append(user_id)

    query = f"""
        UPDATE player_profiles
        SET {", ".join(assignments)}, updated_at = NOW()
        WHERE user_id = ${user_id_placeholder}
        RETURNING {PLAYER_PROFILE_COLUMNS}
    """
    return await connection.fetchrow(query, *values)


async def get_active_stamina_activity_window(
    connection: Connection,
    user_id: int,
) -> TimedActivityWindow | None:
    # Timed activities should pause passive stamina recovery while they are running.
    # Explore is live now, and training can plug into this same helper later.
    record = await connection.fetchrow(
        """
        SELECT
            'exploring' AS activity_type,
            start_time,
            end_time
        FROM active_explorations
        WHERE user_id = $1
        """,
        user_id,
    )
    if record is None:
        return None

    return TimedActivityWindow(
        activity_type=str(record["activity_type"]),
        start_time=record["start_time"],
        end_time=record["end_time"],
    )


async def sync_player_record(
    connection: Connection,
    record: Record,
) -> ResourceSyncResult:
    now = datetime.now(timezone.utc)
    stamina_current = int(record["stamina_current"])
    stamina_max = int(record["stamina_max"])
    updates: dict[str, Any] = {}
    passive_stamina_gained = 0
    rest_stamina_gained = 0
    resting_minutes = 0

    if bool(record["is_resting"]):
        rest_start_time = record["rest_start_time"] or now
        rest_snapshot = record["rest_stamina_snapshot"]
        if rest_snapshot is None:
            rest_snapshot = stamina_current
            updates["rest_stamina_snapshot"] = rest_snapshot

        resting_minutes = calculate_minutes_elapsed(rest_start_time, now)
        recovered_total = calculate_rest_stamina_recovery(resting_minutes)
        new_stamina = min(stamina_max, int(rest_snapshot) + recovered_total)
        rest_stamina_gained = new_stamina - int(rest_snapshot)

        if new_stamina != stamina_current:
            updates["stamina_current"] = new_stamina

        if rest_start_time != record["rest_start_time"]:
            updates["rest_start_time"] = rest_start_time

        if resting_minutes > 0:
            updates["stamina_updated_at"] = now
    else:
        stamina_updated_at = record["stamina_updated_at"] or now
        activity_window = await get_active_stamina_activity_window(
            connection,
            int(record["user_id"]),
        )
        if activity_window is not None and activity_window.end_time > now:
            elapsed_minutes = 0
        else:
            passive_recovery_start = stamina_updated_at
            if activity_window is not None:
                passive_recovery_start = max(
                    stamina_updated_at,
                    activity_window.end_time,
                )

            elapsed_minutes = calculate_minutes_elapsed(passive_recovery_start, now)

        if elapsed_minutes > 0:
            passive_stamina_gained = calculate_passive_stamina_recovery(
                current_stamina=stamina_current,
                stamina_max=stamina_max,
                elapsed_minutes=elapsed_minutes,
            )
            new_stamina = min(stamina_max, stamina_current + passive_stamina_gained)
            if new_stamina != stamina_current:
                updates["stamina_current"] = new_stamina

            updates["stamina_updated_at"] = now

    if updates:
        updated_record = await update_player_record(connection, int(record["user_id"]), updates)
        return ResourceSyncResult(
            record=updated_record,
            passive_stamina_gained=passive_stamina_gained,
            rest_stamina_gained=rest_stamina_gained,
            resting_minutes=resting_minutes,
        )

    return ResourceSyncResult(
        record=record,
        passive_stamina_gained=passive_stamina_gained,
        rest_stamina_gained=rest_stamina_gained,
        resting_minutes=resting_minutes,
    )


async def get_player_profile(
    pool: Pool | None,
    user_id: int,
    *,
    for_update: bool = False,
) -> PlayerProfile | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_player_record(connection, user_id, for_update=for_update)
        if record is None:
            return None

        sync_result = await sync_player_record(connection, record)
        return PlayerProfile.from_record(sync_result.record)


async def get_or_sync_player_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> ResourceSyncResult | None:
    record = await fetch_player_record(connection, user_id, for_update=for_update)
    if record is None:
        return None

    return await sync_player_record(connection, record)


async def create_player_profile(pool: Pool | None, user_id: int) -> tuple[PlayerProfile | None, bool]:
    if pool is None:
        return None, False

    trait = roll_random_soul_trait()

    async with pool.acquire() as connection:
        async with connection.transaction():
            has_legacy_column = await has_legacy_discord_user_id_column(connection)

            if has_legacy_column:
                record = await connection.fetchrow(
                    f"""
                    INSERT INTO player_profiles (
                        discord_user_id,
                        user_id,
                        race,
                        rank,
                        level,
                        xp,
                        hp_current,
                        hp_max,
                        stamina_current,
                        stamina_max,
                        mana_current,
                        mana_max,
                        power,
                        defense,
                        speed,
                        reiatsu,
                        trait,
                        location,
                        rukongai_rep,
                        is_resting,
                        rest_start_time,
                        rest_stamina_snapshot,
                        stamina_updated_at
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9,
                        $10, $11, $12, $13, $14, $15, $16, $17, $18,
                        $19, $20, $21, $22, $23
                    )
                    ON CONFLICT (user_id) DO NOTHING
                    RETURNING {PLAYER_PROFILE_COLUMNS}
                    """,
                    str(user_id),
                    user_id,
                    STARTING_RACE,
                    STARTING_RANK,
                    STARTING_LEVEL,
                    STARTING_XP,
                    STARTING_HP,
                    STARTING_HP,
                    STARTING_STAMINA,
                    STARTING_STAMINA,
                    STARTING_MANA,
                    STARTING_MANA,
                    0,
                    0,
                    0,
                    0,
                    trait.key,
                    DEFAULT_LOCATION_KEY,
                    0,
                    False,
                    None,
                    None,
                    datetime.now(timezone.utc),
                )
            else:
                record = await connection.fetchrow(
                    f"""
                    INSERT INTO player_profiles (
                        user_id,
                        race,
                        rank,
                        level,
                        xp,
                        hp_current,
                        hp_max,
                        stamina_current,
                        stamina_max,
                        mana_current,
                        mana_max,
                        power,
                        defense,
                        speed,
                        reiatsu,
                        trait,
                        location,
                        rukongai_rep,
                        is_resting,
                        rest_start_time,
                        rest_stamina_snapshot,
                        stamina_updated_at
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9,
                        $10, $11, $12, $13, $14, $15, $16, $17, $18,
                        $19, $20, $21, $22
                    )
                    ON CONFLICT (user_id) DO NOTHING
                    RETURNING {PLAYER_PROFILE_COLUMNS}
                    """,
                    user_id,
                    STARTING_RACE,
                    STARTING_RANK,
                    STARTING_LEVEL,
                    STARTING_XP,
                    STARTING_HP,
                    STARTING_HP,
                    STARTING_STAMINA,
                    STARTING_STAMINA,
                    STARTING_MANA,
                    STARTING_MANA,
                    0,
                    0,
                    0,
                    0,
                    trait.key,
                    DEFAULT_LOCATION_KEY,
                    0,
                    False,
                    None,
                    None,
                    datetime.now(timezone.utc),
                )

            if record is None:
                existing_profile = await fetch_player_record(connection, user_id)
                if existing_profile is None:
                    return None, False

                sync_result = await sync_player_record(connection, existing_profile)
                return PlayerProfile.from_record(sync_result.record), False

    return PlayerProfile.from_record(record), True


def build_resting_block_message(player: PlayerProfile, rest_minutes: int, recovered_stamina: int) -> str:
    return (
        "You are currently resting and must stop with `/rest` before using action commands.\n"
        f"Status: **Resting**\n"
        f"Resting Since: **{rest_minutes} minute(s) ago**\n"
        f"Projected Recovery: **+{recovered_stamina} stamina**"
    )


def get_rest_status(player: PlayerProfile) -> tuple[int, int]:
    if not player.is_resting or player.rest_start_time is None:
        return 0, 0

    resting_minutes = calculate_minutes_elapsed(player.rest_start_time, datetime.now(timezone.utc))
    rest_snapshot = player.rest_stamina_snapshot if player.rest_stamina_snapshot is not None else player.stamina_current
    recovered_stamina = max(0, player.stamina_current - rest_snapshot)
    return resting_minutes, recovered_stamina


async def toggle_resting(pool: Pool | None, user_id: int) -> tuple[PlayerProfile | None, bool, int, int]:
    if pool is None:
        return None, False, 0, 0

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None, False, 0, 0

            record = sync_result.record
            now = datetime.now(timezone.utc)

            if bool(record["is_resting"]):
                updated_record = await update_player_record(
                    connection,
                    user_id,
                    {
                        "is_resting": False,
                        "rest_start_time": None,
                        "rest_stamina_snapshot": None,
                        "stamina_updated_at": now,
                    },
                )
                return (
                    PlayerProfile.from_record(updated_record),
                    False,
                    sync_result.rest_stamina_gained,
                    sync_result.resting_minutes,
                )

            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    "is_resting": True,
                    "rest_start_time": now,
                    "rest_stamina_snapshot": int(record["stamina_current"]),
                    "stamina_updated_at": now,
                },
            )
            return PlayerProfile.from_record(updated_record), True, 0, 0
