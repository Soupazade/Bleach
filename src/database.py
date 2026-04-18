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
    kan INTEGER NOT NULL DEFAULT 500,
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
    unspent_stat_points INTEGER NOT NULL DEFAULT 0,
    trait TEXT NOT NULL DEFAULT 'resilient',
    location TEXT NOT NULL DEFAULT 'rukongai_streets',
    rukongai_rep INTEGER NOT NULL DEFAULT 0,
    has_minor_setback BOOLEAN NOT NULL DEFAULT FALSE,
    setback_source TEXT,
    setback_at TIMESTAMPTZ,
    is_resting BOOLEAN NOT NULL DEFAULT FALSE,
    rest_start_time TIMESTAMPTZ,
    rest_stamina_snapshot INTEGER,
    rest_hp_snapshot INTEGER,
    rest_mana_snapshot INTEGER,
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

CREATE_ACTIVE_WORKS_TABLE = """
CREATE TABLE IF NOT EXISTS active_works (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    location TEXT NOT NULL,
    work_key TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    stamina_cost INTEGER NOT NULL
);
"""

CREATE_ACTIVE_DUNGEONS_TABLE = """
CREATE TABLE IF NOT EXISTS active_dungeons (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    dungeon_key TEXT NOT NULL,
    location TEXT NOT NULL,
    current_room_index INTEGER NOT NULL DEFAULT 0,
    progress_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_ACTIVE_TRAVELS_TABLE = """
CREATE TABLE IF NOT EXISTS active_travels (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    source_location TEXT NOT NULL,
    destination_location TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    stamina_cost INTEGER NOT NULL
);
"""

CREATE_ACTIVE_TRAININGS_TABLE = """
CREATE TABLE IF NOT EXISTS active_trainings (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    stat_target TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    stamina_cost INTEGER NOT NULL
);
"""

CREATE_ACTIVE_EXPLORATION_CHOICES_TABLE = """
CREATE TABLE IF NOT EXISTS active_exploration_choices (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    session_kind TEXT NOT NULL DEFAULT 'decision',
    npc_id TEXT,
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
    base_rep_change INTEGER,
    base_combat_outcome TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_ACTIVE_EXPLORATION_COMBATS_TABLE = """
CREATE TABLE IF NOT EXISTS active_exploration_combats (
    user_id BIGINT PRIMARY KEY REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    location TEXT NOT NULL,
    approach TEXT NOT NULL,
    encounter_title TEXT NOT NULL,
    encounter_description TEXT NOT NULL,
    resolution_title TEXT NOT NULL,
    resolution_description TEXT NOT NULL,
    enemy_name TEXT NOT NULL,
    enemy_hp_current INTEGER NOT NULL,
    enemy_hp_max INTEGER NOT NULL,
    enemy_power INTEGER NOT NULL,
    enemy_defense INTEGER NOT NULL,
    enemy_speed INTEGER NOT NULL,
    reward_xp_win INTEGER NOT NULL,
    reward_xp_lose INTEGER NOT NULL,
    reputation_change INTEGER NOT NULL DEFAULT 0,
    player_hp_current INTEGER NOT NULL,
    player_hp_max INTEGER NOT NULL,
    player_mana_current INTEGER NOT NULL,
    player_mana_max INTEGER NOT NULL,
    player_power INTEGER NOT NULL,
    player_defense INTEGER NOT NULL,
    player_speed INTEGER NOT NULL,
    player_reiatsu INTEGER NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    focus_bonus INTEGER NOT NULL DEFAULT 0,
    guard_active BOOLEAN NOT NULL DEFAULT FALSE,
    last_round_summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_ACTIVE_COMBATS_TABLE = """
CREATE TABLE IF NOT EXISTS active_combats (
    fight_id BIGSERIAL PRIMARY KEY,
    fight_log_id BIGINT NOT NULL,
    user_id BIGINT UNIQUE NOT NULL REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    source_kind TEXT NOT NULL,
    location TEXT NOT NULL,
    approach TEXT NOT NULL,
    encounter_title TEXT NOT NULL,
    encounter_description TEXT NOT NULL,
    resolution_title TEXT NOT NULL,
    resolution_description TEXT NOT NULL,
    reward_xp_win INTEGER NOT NULL DEFAULT 0,
    reward_xp_lose INTEGER NOT NULL DEFAULT 0,
    reputation_change INTEGER NOT NULL DEFAULT 0,
    round_number INTEGER NOT NULL DEFAULT 1,
    afk_skips INTEGER NOT NULL DEFAULT 0,
    last_round_summary TEXT NOT NULL DEFAULT '',
    turn_deadline_at TIMESTAMPTZ NOT NULL,
    player_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    enemies_state JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_COMBAT_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS combat_logs (
    fight_log_id BIGSERIAL PRIMARY KEY,
    fight_id BIGINT NOT NULL DEFAULT 0,
    user_id BIGINT NOT NULL REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    source_kind TEXT NOT NULL,
    outcome TEXT,
    readable_log TEXT NOT NULL DEFAULT '',
    turn_payloads JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalized_at TIMESTAMPTZ
);
"""

CREATE_PLAYER_NPC_PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS player_npc_progress (
    user_id BIGINT NOT NULL REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    npc_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'default',
    stage INTEGER NOT NULL DEFAULT 0,
    last_encounter_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, npc_id)
);
"""

CREATE_PLAYER_EFFECTS_TABLE = """
CREATE TABLE IF NOT EXISTS player_effects (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    effect_key TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    effect_type TEXT NOT NULL,
    magnitude INTEGER NOT NULL,
    duration_minutes INTEGER,
    expires_at TIMESTAMPTZ,
    remaining_explores INTEGER,
    source_text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_PLAYER_INVENTORY_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS player_inventory_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    item_name TEXT NOT NULL,
    item_description TEXT NOT NULL DEFAULT '',
    item_type TEXT NOT NULL DEFAULT 'misc',
    rarity TEXT NOT NULL DEFAULT 'common',
    quantity INTEGER NOT NULL DEFAULT 1,
    stackable BOOLEAN NOT NULL DEFAULT TRUE,
    source_text TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_PLAYER_QUESTS_TABLE = """
CREATE TABLE IF NOT EXISTS player_quests (
    user_id BIGINT NOT NULL REFERENCES player_profiles(user_id) ON DELETE CASCADE,
    quest_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    current_step_index INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, quest_key)
);
"""

PLAYER_PROFILE_COLUMN_DEFAULTS = (
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS user_id BIGINT",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS race TEXT NOT NULL DEFAULT 'Soul'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rank TEXT NOT NULL DEFAULT 'Wandering Soul'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS level INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS xp INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS kan INTEGER NOT NULL DEFAULT 500",
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
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS unspent_stat_points INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS trait TEXT NOT NULL DEFAULT 'resilient'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT 'rukongai_streets'",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rukongai_rep INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS has_minor_setback BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS setback_source TEXT",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS setback_at TIMESTAMPTZ",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS is_resting BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rest_start_time TIMESTAMPTZ",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rest_stamina_snapshot INTEGER",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rest_hp_snapshot INTEGER",
    "ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS rest_mana_snapshot INTEGER",
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

CREATE_ACTIVE_WORKS_END_TIME_INDEX = """
CREATE INDEX IF NOT EXISTS idx_active_works_end_time
ON active_works (end_time);
"""

CREATE_ACTIVE_DUNGEONS_MESSAGE_ID_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_dungeons_message_id
ON active_dungeons (message_id)
WHERE message_id IS NOT NULL;
"""

CREATE_ACTIVE_TRAVELS_END_TIME_INDEX = """
CREATE INDEX IF NOT EXISTS idx_active_travels_end_time
ON active_travels (end_time);
"""

CREATE_ACTIVE_TRAININGS_END_TIME_INDEX = """
CREATE INDEX IF NOT EXISTS idx_active_trainings_end_time
ON active_trainings (end_time);
"""

CREATE_ACTIVE_EXPLORATION_CHOICES_MESSAGE_ID_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_exploration_choices_message_id
ON active_exploration_choices (message_id)
WHERE message_id IS NOT NULL;
"""

CREATE_ACTIVE_EXPLORATION_COMBATS_MESSAGE_ID_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_exploration_combats_message_id
ON active_exploration_combats (message_id)
WHERE message_id IS NOT NULL;
"""

CREATE_ACTIVE_COMBATS_MESSAGE_ID_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_combats_message_id
ON active_combats (message_id)
WHERE message_id IS NOT NULL;
"""

CREATE_ACTIVE_COMBATS_USER_ID_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_combats_user_id
ON active_combats (user_id);
"""

CREATE_ACTIVE_COMBATS_DEADLINE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_active_combats_turn_deadline
ON active_combats (turn_deadline_at);
"""

CREATE_COMBAT_LOGS_FIGHT_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_combat_logs_fight_id
ON combat_logs (fight_id);
"""

ACTIVE_EXPLORATION_CHOICE_COLUMN_DEFAULTS = (
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS session_kind TEXT NOT NULL DEFAULT 'decision'",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS npc_id TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS special_event_key TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_event_type TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_title TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_description TEXT",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_xp INTEGER",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_rep_change INTEGER",
    "ALTER TABLE active_exploration_choices ADD COLUMN IF NOT EXISTS base_combat_outcome TEXT",
)

CREATE_PLAYER_NPC_PROGRESS_LOOKUP_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_npc_progress_user_npc
ON player_npc_progress (user_id, npc_id);
"""

CREATE_PLAYER_EFFECTS_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_effects_user_id
ON player_effects (user_id);
"""

CREATE_PLAYER_EFFECTS_EXPIRES_AT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_effects_expires_at
ON player_effects (expires_at);
"""

CREATE_PLAYER_INVENTORY_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_inventory_user_id
ON player_inventory_items (user_id);
"""

CREATE_PLAYER_INVENTORY_ITEM_KEY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_inventory_item_key
ON player_inventory_items (user_id, item_key);
"""

CREATE_PLAYER_QUESTS_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_quests_user_id
ON player_quests (user_id);
"""

CREATE_PLAYER_QUESTS_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_quests_status
ON player_quests (user_id, status);
"""


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

        await connection.execute(
            """
            UPDATE player_profiles
            SET rukongai_rep = GREATEST(-100, LEAST(100, COALESCE(rukongai_rep, 0)))
            WHERE rukongai_rep IS NULL
               OR rukongai_rep < -100
               OR rukongai_rep > 100
            """
        )

        await connection.execute(CREATE_PLAYER_PROFILE_USER_ID_INDEX)
        await connection.execute(CREATE_ACTIVE_EXPLORATIONS_TABLE)
        await connection.execute(CREATE_ACTIVE_EXPLORATIONS_END_TIME_INDEX)
        await connection.execute(CREATE_ACTIVE_WORKS_TABLE)
        await connection.execute(CREATE_ACTIVE_WORKS_END_TIME_INDEX)
        await connection.execute(CREATE_ACTIVE_DUNGEONS_TABLE)
        await connection.execute(CREATE_ACTIVE_DUNGEONS_MESSAGE_ID_INDEX)
        await connection.execute(CREATE_ACTIVE_TRAVELS_TABLE)
        await connection.execute(CREATE_ACTIVE_TRAVELS_END_TIME_INDEX)
        await connection.execute(CREATE_ACTIVE_TRAININGS_TABLE)
        await connection.execute(CREATE_ACTIVE_TRAININGS_END_TIME_INDEX)
        await connection.execute(CREATE_ACTIVE_EXPLORATION_CHOICES_TABLE)
        for statement in ACTIVE_EXPLORATION_CHOICE_COLUMN_DEFAULTS:
            await connection.execute(statement)
        await connection.execute(CREATE_ACTIVE_EXPLORATION_CHOICES_MESSAGE_ID_INDEX)
        await connection.execute(CREATE_ACTIVE_EXPLORATION_COMBATS_TABLE)
        await connection.execute(CREATE_ACTIVE_EXPLORATION_COMBATS_MESSAGE_ID_INDEX)
        await connection.execute(CREATE_ACTIVE_COMBATS_TABLE)
        await connection.execute(CREATE_ACTIVE_COMBATS_MESSAGE_ID_INDEX)
        await connection.execute(CREATE_ACTIVE_COMBATS_USER_ID_INDEX)
        await connection.execute(CREATE_ACTIVE_COMBATS_DEADLINE_INDEX)
        await connection.execute(CREATE_COMBAT_LOGS_TABLE)
        await connection.execute(CREATE_COMBAT_LOGS_FIGHT_ID_INDEX)
        await connection.execute(CREATE_PLAYER_NPC_PROGRESS_TABLE)
        await connection.execute(CREATE_PLAYER_NPC_PROGRESS_LOOKUP_INDEX)
        await connection.execute(CREATE_PLAYER_EFFECTS_TABLE)
        await connection.execute(CREATE_PLAYER_EFFECTS_USER_INDEX)
        await connection.execute(CREATE_PLAYER_EFFECTS_EXPIRES_AT_INDEX)
        await connection.execute(CREATE_PLAYER_INVENTORY_ITEMS_TABLE)
        await connection.execute(CREATE_PLAYER_INVENTORY_USER_INDEX)
        await connection.execute(CREATE_PLAYER_INVENTORY_ITEM_KEY_INDEX)
        await connection.execute(CREATE_PLAYER_QUESTS_TABLE)
        await connection.execute(CREATE_PLAYER_QUESTS_USER_INDEX)
        await connection.execute(CREATE_PLAYER_QUESTS_STATUS_INDEX)
