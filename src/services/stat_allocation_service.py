from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncpg import Connection, Pool

from src.models.player import PlayerProfile
from src.services.formulas import get_remaining_stat_capacity
from src.services.player_service import get_or_sync_player_record, update_player_record


AllocatableStat = Literal["power", "defense", "speed", "reiatsu"]
VALID_ALLOCATABLE_STATS: tuple[AllocatableStat, ...] = ("power", "defense", "speed", "reiatsu")


@dataclass(slots=True)
class StatAllocationResult:
    status: Literal["allocated", "missing_profile", "no_points", "invalid_stat", "cap_reached"]
    player: PlayerProfile | None = None
    stat_name: AllocatableStat | None = None
    points_spent: int = 0
    remaining_points: int = 0
    remaining_capacity: int = 0


async def allocate_stat_point_for_connection(
    connection: Connection,
    *,
    user_id: int,
    stat_name: str,
    points: int = 1,
) -> StatAllocationResult:
    if stat_name not in VALID_ALLOCATABLE_STATS:
        return StatAllocationResult(status="invalid_stat")

    normalized_points = max(1, points)
    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        return StatAllocationResult(status="missing_profile")

    player = PlayerProfile.from_record(player_sync.record)
    remaining_capacity = get_remaining_stat_capacity(
        level=player.level,
        power=player.power,
        defense=player.defense,
        speed=player.speed,
        reiatsu=player.reiatsu,
    )
    if player.unspent_stat_points <= 0:
        return StatAllocationResult(
            status="no_points",
            player=player,
            remaining_points=0,
            remaining_capacity=remaining_capacity,
        )
    if remaining_capacity <= 0:
        return StatAllocationResult(
            status="cap_reached",
            player=player,
            remaining_points=player.unspent_stat_points,
            remaining_capacity=0,
        )

    points_spent = min(normalized_points, player.unspent_stat_points, remaining_capacity)
    if points_spent <= 0:
        return StatAllocationResult(
            status="cap_reached",
            player=player,
            stat_name=stat_name,
            remaining_points=player.unspent_stat_points,
            remaining_capacity=remaining_capacity,
        )

    updated_record = await update_player_record(
        connection,
        user_id,
        {
            stat_name: getattr(player, stat_name) + points_spent,
            "unspent_stat_points": player.unspent_stat_points - points_spent,
        },
    )
    updated_player = PlayerProfile.from_record(updated_record)
    updated_capacity = get_remaining_stat_capacity(
        level=updated_player.level,
        power=updated_player.power,
        defense=updated_player.defense,
        speed=updated_player.speed,
        reiatsu=updated_player.reiatsu,
    )
    return StatAllocationResult(
        status="allocated",
        player=updated_player,
        stat_name=stat_name,
        points_spent=points_spent,
        remaining_points=updated_player.unspent_stat_points,
        remaining_capacity=updated_capacity,
    )


async def allocate_stat_point(
    pool: Pool | None,
    *,
    user_id: int,
    stat_name: str,
    points: int = 1,
) -> StatAllocationResult:
    if pool is None:
        return StatAllocationResult(status="missing_profile")

    async with pool.acquire() as connection:
        async with connection.transaction():
            return await allocate_stat_point_for_connection(
                connection,
                user_id=user_id,
                stat_name=stat_name,
                points=points,
            )
