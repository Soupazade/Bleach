import logging
import os

import asyncpg


CREATE_PLAYER_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS player_profiles (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    race TEXT NOT NULL DEFAULT 'Soul',
    rank TEXT NOT NULL DEFAULT 'Wandering Soul',
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    hp_current INTEGER NOT NULL DEFAULT 100,
    hp_max INTEGER NOT NULL DEFAULT 100,
    stamina_current INTEGER NOT NULL DEFAULT 100,
    stamina_max INTEGER NOT NULL DEFAULT 100,
    mana_current INTEGER NOT NULL DEFAULT 50,
    mana_max INTEGER NOT NULL DEFAULT 50,
    power INTEGER NOT NULL DEFAULT 0,
    defense INTEGER NOT NULL DEFAULT 0,
    speed INTEGER NOT NULL DEFAULT 0,
    reiatsu INTEGER NOT NULL DEFAULT 0,
    trait TEXT NOT NULL DEFAULT 'resilient',
    location TEXT NOT NULL DEFAULT 'rukongai_streets',
    is_resting BOOLEAN NOT NULL DEFAULT FALSE,
    rest_start_time TIMESTAMPTZ,
    rest_stamina_snapshot INTEGER,
    stamina_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_ACTIVE_EXPLORATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS active_explorations (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    location TEXT NOT NULL,
    approach TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL
);
"""

CREATE_ACTIVE_EXPLORATION_CHOICES_TABLE = """
CREATE TABLE IF NOT EXISTS active_exploration_choices (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    session_kind TEXT NOT NULL DEFAULT 'decision',
    location TEXT NOT NULL,
    approach TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    event_key TEXT NOT NULL,
    special_event_key TEXT,
    event_flow TEXT NOT NULL,
    current_step TEXT NOT NULL,
    choice_history TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    base_event_type TEXT,
    base_title TEXT,
    base_description TEXT,
    base_xp INTEGER,
    base_combat_outcome TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

PLAYER_PROFILE_COLUMN_DEFAULTS = (
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS user_id BIGINT",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS race TEXT NOT NULL DEFAULT 'Soul'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rank TEXT NOT NULL DEFAULT 'Wandering Soul'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS level INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS xp INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS hp_current INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS hp_max INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS stamina_current INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS stamina_max INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS mana_current INTEGER NOT NULL DEFAULT 50",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS mana_max INTEGER NOT NULL DEFAULT 50",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS power INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS defense INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS speed INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS reiatsu INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS trait TEXT NOT NULL DEFAULT 'resilient'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT 'rukongai_streets'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS is_resting BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rest_start_time TIMESTAMPTZ",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rest_stamina_snapshot INTEGER",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS stamina_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
)

CREATE_PLAYER_PROFILE_USER_ID_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_player_profiles_user_id
ON player_profiles (user_id);
"""

CREATE_ACTIVE_EXPLORATIONS_END_TIME_INDEX = """
CREATE INDEX IF NOT EXISTS idx_active_explorations_end_time
ON active_explorations (end_time);
"""

CREATE_ACTIVE_EXPLORATION_CHOICES_MESSAGE_ID_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_exploration_choices_message_id
ON active_exploration_choices (message_id)
WHERE message_id IS NOT NULL;
"""

ACTIVE_EXPLORATION_CHOICE_COLUMN_DEFAULTS = (
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS session_kind TEXT NOT NULL DEFAULT 'decision'",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS special_event_key TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_event_type TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_title TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_description TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_xp INTEGER",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_combat_outcome TEXT",
)


async def create_pool() -> asyncpg.Pool | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logging.warning("DATABASE_URL is not set. Database features are disabled.")
        return None

    try:
        pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
    except Exception as error:
        logging.exception("Failed to connect to PostgreSQL. Database features are disabled.")
        logging.warning("Startup will continue without a database connection: %s", error)
        return None

    logging.info("Connected to PostgreSQL.")
    return pool


async def ensure_schema(pool: asyncpg.Pool | None) -> None:
    if pool is None:
        return

    async with pool.acquire() as connection:
        await connection.execute(CREATE_PLAYER_PROFILES_TABLE)
        existing_columns = await connection.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'player_profiles'
            """
        )
        column_names = {row["column_name"] for row in existing_columns}

        if "discord_user_id" in column_names:
            if "user_id" not in column_names:
                await connection.execute("ALTER TABLE player_profiles ADD COLUMN user_id BIGINT")

            await connection.execute(
                """
                UPDATE player_profiles
                SET user_id = NULLIF(discord_user_id, '')::BIGINT
                WHERE user_id IS NULL
                  AND NULLIF(discord_user_id, '') IS NOT NULL
                """
            )
            await connection.execute(
                """
                UPDATE player_profiles
                SET discord_user_id = user_id::TEXT
                WHERE discord_user_id IS NULL
                  AND user_id IS NOT NULL
                """
            )
            await connection.execute(
                "ALTER TABLE player_profiles ALTER COLUMN discord_user_id DROP NOT NULL"
            )

        if "experience" in column_names and "xp" not in column_names:
            await connection.execute(
                "ALTER TABLE player_profiles ADD COLUMN xp INTEGER NOT NULL DEFAULT 0"
            )
            await connection.execute(
                """
                UPDATE player_profiles
                SET xp = COALESCE(experience, 0)
                WHERE xp = 0
                """
            )

        if "strength" in column_names and "power" not in column_names:
            await connection.execute("ALTER TABLE player_profiles ADD COLUMN power INTEGER NOT NULL DEFAULT 0")
            await connection.execute(
                """
                UPDATE player_profiles
                SET power = COALESCE(strength, 0)
                WHERE power = 0
                """
            )

        if "intelligence" in column_names and "reiatsu" not in column_names:
            await connection.execute("ALTER TABLE player_profiles ADD COLUMN reiatsu INTEGER NOT NULL DEFAULT 0")
            await connection.execute(
                """
                UPDATE player_profiles
                SET reiatsu = COALESCE(intelligence, 0)
                WHERE reiatsu = 0
                """
            )

        for statement in PLAYER_PROFILE_COLUMN_DEFAULTS:
            await connection.execute(statement)

        await connection.execute(CREATE_PLAYER_PROFILE_USER_ID_INDEX)
        await connection.execute(CREATE_ACTIVE_EXPLORATIONS_TABLE)
        await connection.execute(CREATE_ACTIVE_EXPLORATIONS_END_TIME_INDEX)
        await connection.execute(CREATE_ACTIVE_EXPLORATION_CHOICES_TABLE)
        for statement in ACTIVE_EXPLORATION_CHOICE_COLUMN_DEFAULTS:
            await connection.execute(statement)
        await connection.execute(CREATE_ACTIVE_EXPLORATION_CHOICES_MESSAGE_ID_INDEX)
