from __future__ import annotations

from asyncpg import Pool

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
    strength,
    defense,
    speed,
    intelligence,
    trait,
    location,
    created_at
"""


async def get_player_profile(pool: Pool | None, user_id: int) -> PlayerProfile | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            f"""
            SELECT {PLAYER_PROFILE_COLUMNS}
            FROM player_profiles
            WHERE user_id = $1
            """,
            user_id,
        )

    if record is None:
        return None

    return PlayerProfile.from_record(record)


async def create_player_profile(pool: Pool | None, user_id: int) -> tuple[PlayerProfile | None, bool]:
    if pool is None:
        return None, False

    trait = roll_random_soul_trait()

    async with pool.acquire() as connection:
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
                strength,
                defense,
                speed,
                intelligence,
                trait,
                location
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9,
                $10, $11, $12, $13, $14, $15, $16, $17
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
        )

        if record is None:
            existing_profile = await connection.fetchrow(
                f"""
                SELECT {PLAYER_PROFILE_COLUMNS}
                FROM player_profiles
                WHERE user_id = $1
                """,
                user_id,
            )
            if existing_profile is None:
                return None, False

            return PlayerProfile.from_record(existing_profile), False

    return PlayerProfile.from_record(record), True
