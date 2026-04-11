from __future__ import annotations

from datetime import datetime, timedelta, timezone

from asyncpg import Connection, Pool

from src.models.effects import PlayerEffect
from src.services.effect_service import list_active_player_effects, list_active_player_effects_for_connection


WOUNDED_EFFECT_KEY = "wounded"
WOUNDED_DURATION_MINUTES = 30


def _get_wounded_effect_from_list(effects: list[PlayerEffect]) -> PlayerEffect | None:
    return next((effect for effect in effects if effect.effect_key == WOUNDED_EFFECT_KEY), None)


async def get_active_wounded_effect_for_connection(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> PlayerEffect | None:
    effects = await list_active_player_effects_for_connection(connection, user_id, for_update=for_update)
    return _get_wounded_effect_from_list(effects)


async def is_player_wounded_for_connection(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> bool:
    return await get_active_wounded_effect_for_connection(
        connection,
        user_id,
        for_update=for_update,
    ) is not None


async def get_active_wounded_effect(pool: Pool | None, user_id: int) -> PlayerEffect | None:
    effects = await list_active_player_effects(pool, user_id)
    return _get_wounded_effect_from_list(effects)


async def is_player_wounded(pool: Pool | None, user_id: int) -> bool:
    return await get_active_wounded_effect(pool, user_id) is not None


async def grant_wounded_status(
    connection: Connection,
    user_id: int,
    *,
    duration_minutes: int = WOUNDED_DURATION_MINUTES,
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    existing = await get_active_wounded_effect_for_connection(connection, user_id, for_update=True)
    if existing is not None:
        await connection.execute(
            """
            UPDATE player_effects
            SET
                title = 'Wounded',
                description = 'You blacked out in the street. Training is blocked, and exploration costs and duration are doubled.',
                effect_type = 'wounded',
                magnitude = $2,
                duration_minutes = $2,
                expires_at = $3,
                source_text = 'Blackout',
                updated_at = NOW()
            WHERE id = $1
            """,
            existing.id,
            duration_minutes,
            expires_at,
        )
        return

    await connection.execute(
        """
        INSERT INTO player_effects (
            user_id,
            effect_key,
            title,
            description,
            effect_type,
            magnitude,
            duration_minutes,
            expires_at,
            remaining_explores,
            source_text
        )
        VALUES ($1, 'wounded', 'Wounded', $2, 'wounded', $3, $3, $4, NULL, 'Blackout')
        """,
        user_id,
        "You blacked out in the street. Training is blocked, and exploration costs and duration are doubled.",
        duration_minutes,
        expires_at,
    )
