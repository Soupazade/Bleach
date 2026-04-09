from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from asyncpg import Pool

from src.data.locations import get_location_definition
from src.data.traits import get_trait_definition
from src.models.combat import ActiveExplorationCombat
from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.models.player import PlayerProfile
from src.models.training import ActiveTraining
from src.models.travel import ActiveTravel
from src.services.combat_service import (
    delete_active_exploration_combat,
    fetch_active_combat_record,
    get_active_exploration_combat,
)
from src.services.exploration_service import (
    delete_active_exploration,
    delete_pending_choice,
    fetch_active_exploration_record,
    fetch_pending_choice_record,
    get_active_exploration,
    get_pending_exploration_choice,
)
from src.services.travel_service import (
    delete_active_travel,
    fetch_active_travel_record,
    get_active_travel,
)
from src.services.training_service import (
    delete_active_training,
    fetch_active_training_record,
    get_active_training,
)
from src.services.formulas import apply_experience_gain
from src.services.player_service import (
    get_player_profile,
    get_rest_status,
    get_or_sync_player_record,
    update_player_record,
)


@dataclass(slots=True)
class CooldownResetResult:
    player: PlayerProfile
    cleared_exploration: bool
    cleared_choice: bool
    cleared_combat: bool
    cleared_training: bool
    cleared_travel: bool
    cleared_resting: bool


@dataclass(slots=True)
class PlayerDebugState:
    player: PlayerProfile
    active_exploration: ActiveExploration | None
    pending_choice: PendingExplorationChoice | None
    active_combat: ActiveExplorationCombat | None
    active_training: ActiveTraining | None
    active_travel: ActiveTravel | None
    rest_minutes: int
    projected_rest_recovery: int


VALID_STAT_FIELDS = {"power", "defense", "speed", "reiatsu"}


async def delete_player_profile(pool: Pool | None, user_id: int) -> bool:
    if pool is None:
        return False

    async with pool.acquire() as connection:
        async with connection.transaction():
            result = await connection.execute(
                """
                DELETE FROM player_profiles
                WHERE user_id = $1
                """,
                user_id,
            )

    return result.endswith("1")


async def set_player_xp(pool: Pool | None, user_id: int, xp_amount: int) -> tuple[PlayerProfile | None, int]:
    if pool is None:
        return None, 0

    normalized_xp = max(0, xp_amount)

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None, 0

            record = sync_result.record
            level, xp, levels_gained = apply_experience_gain(
                current_level=int(record["level"]),
                current_xp=0,
                xp_gain=normalized_xp,
            )
            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    "level": level,
                    "xp": xp,
                },
            )

    return PlayerProfile.from_record(updated_record), levels_gained


async def set_player_level(pool: Pool | None, user_id: int, level_amount: int) -> PlayerProfile | None:
    if pool is None:
        return None

    normalized_level = max(1, level_amount)

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None

            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    "level": normalized_level,
                    "xp": 0,
                },
            )

    return PlayerProfile.from_record(updated_record)


async def give_player_xp(pool: Pool | None, user_id: int, xp_amount: int) -> tuple[PlayerProfile | None, int]:
    if pool is None:
        return None, 0

    normalized_xp = max(0, xp_amount)

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None, 0

            record = sync_result.record
            level, xp, levels_gained = apply_experience_gain(
                current_level=int(record["level"]),
                current_xp=int(record["xp"]),
                xp_gain=normalized_xp,
            )
            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    "level": level,
                    "xp": xp,
                },
            )

    return PlayerProfile.from_record(updated_record), levels_gained


async def set_player_stamina(pool: Pool | None, user_id: int, stamina_amount: int) -> PlayerProfile | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None

            record = sync_result.record
            clamped_stamina = max(0, min(int(record["stamina_max"]), stamina_amount))
            updates = {
                "stamina_current": clamped_stamina,
                "stamina_updated_at": datetime.now(timezone.utc),
            }

            if bool(record["is_resting"]):
                updates["rest_start_time"] = datetime.now(timezone.utc)
                updates["rest_stamina_snapshot"] = clamped_stamina

            updated_record = await update_player_record(connection, user_id, updates)

    return PlayerProfile.from_record(updated_record)


async def set_player_trait(pool: Pool | None, user_id: int, trait_key: str) -> PlayerProfile | None:
    if pool is None:
        return None

    get_trait_definition(trait_key)

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None

            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    "trait": trait_key,
                },
            )

    return PlayerProfile.from_record(updated_record)


async def set_player_stat(
    pool: Pool | None,
    user_id: int,
    stat_name: str,
    stat_amount: int,
) -> PlayerProfile | None:
    if pool is None:
        return None

    if stat_name not in VALID_STAT_FIELDS:
        raise ValueError(f"Unknown stat field: {stat_name}")

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None

            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    stat_name: max(0, stat_amount),
                },
            )

    return PlayerProfile.from_record(updated_record)


async def set_player_location(pool: Pool | None, user_id: int, location_key: str) -> PlayerProfile | None:
    if pool is None:
        return None

    get_location_definition(location_key)

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None

            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    "location": location_key,
                },
            )

    return PlayerProfile.from_record(updated_record)


async def reset_player_action_timers(pool: Pool | None, user_id: int) -> CooldownResetResult | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        async with connection.transaction():
            sync_result = await get_or_sync_player_record(connection, user_id, for_update=True)
            if sync_result is None:
                return None

            record = sync_result.record
            exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            cleared_exploration = exploration_record is not None
            if cleared_exploration:
                await delete_active_exploration(connection, user_id)

            pending_choice_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            cleared_choice = pending_choice_record is not None
            if cleared_choice:
                await delete_pending_choice(connection, user_id)

            combat_record = await fetch_active_combat_record(connection, user_id, for_update=True)
            cleared_combat = combat_record is not None
            if cleared_combat:
                await delete_active_exploration_combat(connection, user_id)

            training_record = await fetch_active_training_record(connection, user_id, for_update=True)
            cleared_training = training_record is not None
            if cleared_training:
                await delete_active_training(connection, user_id)

            travel_record = await fetch_active_travel_record(connection, user_id, for_update=True)
            cleared_travel = travel_record is not None
            if cleared_travel:
                await delete_active_travel(connection, user_id)

            cleared_resting = bool(record["is_resting"])
            updated_record = record
            if cleared_resting:
                updated_record = await update_player_record(
                    connection,
                    user_id,
                    {
                        "is_resting": False,
                        "rest_start_time": None,
                        "rest_stamina_snapshot": None,
                        "stamina_updated_at": datetime.now(timezone.utc),
                    },
                )

    return CooldownResetResult(
        player=PlayerProfile.from_record(updated_record),
        cleared_exploration=cleared_exploration,
        cleared_choice=cleared_choice,
        cleared_combat=cleared_combat,
        cleared_training=cleared_training,
        cleared_travel=cleared_travel,
        cleared_resting=cleared_resting,
    )


async def get_player_debug_state(pool: Pool | None, user_id: int) -> PlayerDebugState | None:
    if pool is None:
        return None

    player = await get_player_profile(pool, user_id)
    if player is None:
        return None

    active_exploration = await get_active_exploration(pool, user_id)
    pending_choice = await get_pending_exploration_choice(pool, user_id)
    active_combat = await get_active_exploration_combat(pool, user_id)
    active_training = await get_active_training(pool, user_id)
    active_travel = await get_active_travel(pool, user_id)
    rest_minutes, projected_rest_recovery = get_rest_status(player)
    return PlayerDebugState(
        player=player,
        active_exploration=active_exploration,
        pending_choice=pending_choice,
        active_combat=active_combat,
        active_training=active_training,
        active_travel=active_travel,
        rest_minutes=rest_minutes,
        projected_rest_recovery=projected_rest_recovery,
    )
