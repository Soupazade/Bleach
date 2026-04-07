import logging
import os

import asyncpg


CREATE_PLAYER_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS player_profiles (
    id BIGSERIAL PRIMARY KEY,
    discord_user_id TEXT UNIQUE NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    experience INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def create_pool() -> asyncpg.Pool | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logging.warning("DATABASE_URL is not set. Database features are disabled.")
        return None

    try:
        pool = await asyncpg.create_pool(database_url)
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
