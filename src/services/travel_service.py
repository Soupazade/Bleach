from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import TYPE_CHECKING, Literal

import discord
from asyncpg import Connection, Pool, Record

from src.data.locations import get_location_definition
from src.data.travel import TravelRouteDefinition, get_travel_route
from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.models.player import PlayerProfile
from src.models.quest import QuestProgressUpdate
from src.models.travel import ActiveTravel
from src.models.work import ActiveWork
from src.services.combat_service import fetch_active_combat_record
from src.services.exploration_service import (
    fetch_active_exploration_record,
    fetch_pending_choice_record,
)
from src.services.formulas import format_remaining_duration
from src.services.effect_service import apply_travel_time_modifier, list_active_player_effects_for_connection
from src.services.location_service import resolve_location_channel
from src.services.player_service import get_or_sync_player_record, update_player_record
from src.services.quest_service import record_quest_action_for_connection
from src.services.reputation_service import (
    apply_rep_stamina_cost,
    get_location_reputation_title,
    get_location_reputation_value,
)
from src.services.role_service import sync_member_location_role

if TYPE_CHECKING:
    from src.main import BleachBot


ACTIVE_TRAVEL_COLUMNS = """
    user_id,
    channel_id,
    source_location,
    destination_location,
    start_time,
    end_time,
    stamina_cost
"""


@dataclass(slots=True)
class StartTravelResult:
    status: Literal[
        "started",
        "missing_profile",
        "resting",
        "insufficient_stamina",
        "active_travel",
        "finished",
        "active_exploration",
        "pending_choice",
        "active_combat",
        "active_work",
        "invalid_route",
    ]
    player: PlayerProfile | None = None
    travel: ActiveTravel | None = None
    exploration: ActiveExploration | None = None
    pending_choice: PendingExplorationChoice | None = None
    work: ActiveWork | None = None
    stamina_cost: int = 0
    base_stamina_cost: int = 0


@dataclass(slots=True)
class TravelResolution:
    travel: ActiveTravel
    player: PlayerProfile
    destination_name: str
    role_summary: str | None = None
    role_warning: str | None = None
    quest_updates: tuple[QuestProgressUpdate, ...] = ()


def _resolve_destination_channel(
    bot: "BleachBot",
    destination_location_key: str,
) -> tuple[discord.Guild | None, discord.abc.GuildChannel | discord.Thread | None]:
    destination_location = get_location_definition(destination_location_key)

    if bot.guild_id is not None:
        guild = bot.get_guild(bot.guild_id)
        if guild is None:
            return None, None
        return guild, resolve_location_channel(guild, destination_location)

    for guild in bot.guilds:
        channel = resolve_location_channel(guild, destination_location)
        if channel is not None:
            return guild, channel

    return None, None


async def fetch_active_travel_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_TRAVEL_COLUMNS}
        FROM active_travels
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def list_active_travels(pool: Pool | None) -> list[ActiveTravel]:
    if pool is None:
        return []

    async with pool.acquire() as connection:
        records = await connection.fetch(
            f"""
            SELECT {ACTIVE_TRAVEL_COLUMNS}
            FROM active_travels
            """
        )

    return [ActiveTravel.from_record(record) for record in records]


async def get_active_travel(pool: Pool | None, user_id: int) -> ActiveTravel | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_travel_record(connection, user_id)
        if record is None:
            return None

        return ActiveTravel.from_record(record)


async def create_active_travel(
    connection: Connection,
    *,
    user_id: int,
    channel_id: int,
    source_location: str,
    destination_location: str,
    start_time: datetime,
    end_time: datetime,
    stamina_cost: int,
) -> ActiveTravel:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_travels (
            user_id,
            channel_id,
            source_location,
            destination_location,
            start_time,
            end_time,
            stamina_cost
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING {ACTIVE_TRAVEL_COLUMNS}
        """,
        user_id,
        channel_id,
        source_location,
        destination_location,
        start_time,
        end_time,
        stamina_cost,
    )
    return ActiveTravel.from_record(record)


async def delete_active_travel(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_travels
        WHERE user_id = $1
        """,
        user_id,
    )


def _apply_location_travel_stamina_cost(
    player: PlayerProfile,
    base_cost: int,
) -> tuple[int, int]:
    rep_value = get_location_reputation_value(player, player.location)
    adjusted_cost = apply_rep_stamina_cost(base_cost, rep_value)
    return adjusted_cost, adjusted_cost - base_cost


async def start_travel(
    pool: Pool | None,
    user_id: int,
    channel_id: int,
    destination_location: str,
) -> StartTravelResult:
    from src.services.work_service import fetch_active_work_record

    if pool is None:
        return StartTravelResult(status="missing_profile")

    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return StartTravelResult(status="missing_profile")

            player = PlayerProfile.from_record(player_sync.record)
            if player.is_resting:
                return StartTravelResult(status="resting", player=player)

            pending_choice_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            if pending_choice_record is not None:
                return StartTravelResult(
                    status="pending_choice",
                    player=player,
                    pending_choice=PendingExplorationChoice.from_record(pending_choice_record),
                )

            combat_record = await fetch_active_combat_record(connection, user_id, for_update=True)
            if combat_record is not None:
                return StartTravelResult(status="active_combat", player=player)

            exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if exploration_record is not None:
                exploration = ActiveExploration.from_record(exploration_record)
                return StartTravelResult(status="active_exploration", player=player, exploration=exploration)

            travel_record = await fetch_active_travel_record(connection, user_id, for_update=True)
            if travel_record is not None:
                travel = ActiveTravel.from_record(travel_record)
                if travel.end_time > now:
                    return StartTravelResult(status="active_travel", player=player, travel=travel)
                return StartTravelResult(status="finished", player=player, travel=travel)

            work_record = await fetch_active_work_record(connection, user_id, for_update=True)
            if work_record is not None:
                return StartTravelResult(
                    status="active_work",
                    player=player,
                    work=ActiveWork.from_record(work_record),
                )

            try:
                route = get_travel_route(player.location, destination_location)
            except ValueError:
                return StartTravelResult(status="invalid_route", player=player)

            active_effects = await list_active_player_effects_for_connection(connection, user_id)
            stamina_cost, _ = _apply_location_travel_stamina_cost(player, route.stamina_cost)
            if player.stamina_current < stamina_cost:
                return StartTravelResult(
                    status="insufficient_stamina",
                    player=player,
                    stamina_cost=stamina_cost,
                    base_stamina_cost=route.stamina_cost,
                )

            duration_minutes = apply_travel_time_modifier(route.duration_minutes, active_effects)
            updated_player_record = await update_player_record(
                connection,
                user_id,
                {
                    "stamina_current": player.stamina_current - stamina_cost,
                    "stamina_updated_at": now,
                },
            )
            updated_player = PlayerProfile.from_record(updated_player_record)
            travel = await create_active_travel(
                connection,
                user_id=user_id,
                channel_id=channel_id,
                source_location=player.location,
                destination_location=destination_location,
                start_time=now,
                end_time=now.replace(microsecond=0) + timedelta(minutes=duration_minutes),
                stamina_cost=stamina_cost,
            )
            return StartTravelResult(
                status="started",
                player=updated_player,
                travel=travel,
                stamina_cost=stamina_cost,
                base_stamina_cost=route.stamina_cost,
            )


async def resolve_travel(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
) -> TravelResolution | None:
    if bot.db_pool is None:
        return None

    async with bot.db_pool.acquire() as connection:
        async with connection.transaction():
            travel_record = await fetch_active_travel_record(connection, user_id, for_update=True)
            if travel_record is None:
                return None

            travel = ActiveTravel.from_record(travel_record)
            if travel.end_time > datetime.now(timezone.utc) and not force:
                return None

            updated_player_record = await update_player_record(
                connection,
                user_id,
                {"location": travel.destination_location},
            )
            updated_player = PlayerProfile.from_record(updated_player_record)
            await delete_active_travel(connection, user_id)
            quest_updates = await record_quest_action_for_connection(
                connection,
                user_id,
                "travel_completed",
                location_key=travel.destination_location,
            )

    destination_location = updated_player.location_data
    role_summary = None
    role_warning = None
    guild, _ = _resolve_destination_channel(bot, travel.destination_location)

    if guild is not None:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                member = None

        if member is not None:
            role_summary, role_warning = await sync_member_location_role(
                member,
                destination_location,
                reason="Completed timed travel",
            )

    return TravelResolution(
        travel=travel,
        player=updated_player,
        destination_name=destination_location.name,
        role_summary=role_summary,
        role_warning=role_warning,
        quest_updates=quest_updates,
    )


async def post_travel_arrival(bot: "BleachBot", resolution: TravelResolution) -> None:
    from src.ui.travel_view import build_travel_arrived_embed

    _, channel = _resolve_destination_channel(bot, resolution.travel.destination_location)

    if channel is None:
        source_channel = bot.get_channel(resolution.travel.channel_id)
        if source_channel is not None and hasattr(source_channel, "send"):
            channel = source_channel

    if channel is None:
        logging.warning("Could not find a channel to post travel arrival for user %s.", resolution.travel.user_id)
        return

    embed = build_travel_arrived_embed(resolution)
    try:
        await channel.send(content=f"<@{resolution.travel.user_id}>", embed=embed)
    except discord.HTTPException:
        logging.exception("Failed to post travel arrival for user %s.", resolution.travel.user_id)


async def resolve_and_post_travel(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
) -> TravelResolution | None:
    resolution = await resolve_travel(bot, user_id, force=force)
    if resolution is None:
        return None

    await post_travel_arrival(bot, resolution)
    return resolution


async def _run_travel_task(bot: "BleachBot", travel: ActiveTravel) -> None:
    try:
        while True:
            delay_seconds = (
                travel.end_time.astimezone(timezone.utc) - datetime.now(timezone.utc)
            ).total_seconds()
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds + 0.25)

            resolution = await resolve_and_post_travel(bot, travel.user_id)
            if resolution is not None:
                break

            refreshed_travel = await get_active_travel(bot.db_pool, travel.user_id)
            if refreshed_travel is None:
                break

            travel = refreshed_travel
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Unexpected error while resolving travel for user %s.", travel.user_id)
    finally:
        bot.travel_tasks.pop(travel.user_id, None)


def schedule_travel_task(bot: "BleachBot", travel: ActiveTravel) -> None:
    existing_task = bot.travel_tasks.get(travel.user_id)
    if existing_task is not None:
        existing_task.cancel()

    bot.travel_tasks[travel.user_id] = asyncio.create_task(_run_travel_task(bot, travel))


async def restore_travel_tasks(bot: "BleachBot") -> None:
    for travel in await list_active_travels(bot.db_pool):
        schedule_travel_task(bot, travel)


def get_travel_remaining_time(travel: ActiveTravel) -> str:
    return format_remaining_duration(travel.end_time)


def get_travel_stamina_text(player: PlayerProfile, route: TravelRouteDefinition) -> tuple[int, int, str]:
    stamina_cost, modifier = _apply_location_travel_stamina_cost(player, route.stamina_cost)
    reputation_title = get_location_reputation_title(player, player.location)
    return stamina_cost, modifier, reputation_title
