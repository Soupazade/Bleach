from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import random
from typing import TYPE_CHECKING, Literal

import discord
from asyncpg import Connection, Pool, Record

from src.data.exploration import (
    ExploreEventType,
    ExplorationEventTemplate,
    get_explore_approach,
    get_location_event_pool,
)
from src.data.locations import get_location_definition
from src.models.exploration import ActiveExploration
from src.models.player import PlayerProfile
from src.services.formulas import apply_experience_gain, format_remaining_duration
from src.services.player_service import (
    get_or_sync_player_record,
    update_player_record,
)

if TYPE_CHECKING:
    from src.main import BleachBot


ACTIVE_EXPLORATION_COLUMNS = """
    user_id,
    channel_id,
    location,
    approach,
    start_time,
    end_time
"""


@dataclass(slots=True)
class StartExplorationResult:
    status: Literal["started", "missing_profile", "resting", "insufficient_stamina", "active", "finished"]
    player: PlayerProfile | None = None
    exploration: ActiveExploration | None = None
    rest_minutes: int = 0
    rest_recovery: int = 0


@dataclass(slots=True)
class ExplorationResolution:
    exploration: ActiveExploration
    player: PlayerProfile
    event_type: Literal["reward", "combat", "choice", "flavor"]
    title: str
    description: str
    xp_gained: int
    levels_gained: int
    combat_outcome: str | None = None


async def fetch_active_exploration_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_EXPLORATION_COLUMNS}
        FROM active_explorations
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def get_active_exploration(pool: Pool | None, user_id: int) -> ActiveExploration | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_exploration_record(connection, user_id)
        if record is None:
            return None

        return ActiveExploration.from_record(record)


async def list_active_explorations(pool: Pool | None) -> list[ActiveExploration]:
    if pool is None:
        return []

    async with pool.acquire() as connection:
        records = await connection.fetch(
            f"""
            SELECT {ACTIVE_EXPLORATION_COLUMNS}
            FROM active_explorations
            """
        )

    return [ActiveExploration.from_record(record) for record in records]


async def create_active_exploration(
    connection: Connection,
    user_id: int,
    channel_id: int,
    location: str,
    approach: str,
    start_time: datetime,
    end_time: datetime,
) -> ActiveExploration:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_explorations (
            user_id,
            channel_id,
            location,
            approach,
            start_time,
            end_time
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING {ACTIVE_EXPLORATION_COLUMNS}
        """,
        user_id,
        channel_id,
        location,
        approach,
        start_time,
        end_time,
    )
    return ActiveExploration.from_record(record)


async def delete_active_exploration(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_explorations
        WHERE user_id = $1
        """,
        user_id,
    )


def _format_event_description(
    template: ExplorationEventTemplate,
    exploration: ActiveExploration,
) -> str:
    approach = get_explore_approach(exploration.approach)
    location = get_location_definition(exploration.location)
    return template.description.format(
        approach=approach.label,
        location=location.name,
    )


def _weighted_event_type(exploration: ActiveExploration) -> ExploreEventType:
    approach = get_explore_approach(exploration.approach)
    event_types = tuple(approach.event_biases.keys())
    weights = tuple(approach.event_biases.values())
    return random.choices(event_types, weights=weights, k=1)[0]


def _resolve_reward_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.reward_events)
    xp_gained = random.randint(approach.xp_min, approach.xp_max)
    description = _format_event_description(event, exploration)
    return event.title, description, xp_gained


def _resolve_combat_event(exploration: ActiveExploration) -> tuple[str, str, int, str]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.combat_events)
    description = _format_event_description(event, exploration)
    win_chance_by_risk = {
        "low": 0.75,
        "medium": 0.64,
        "high": 0.55,
    }
    won = random.random() < win_chance_by_risk.get(approach.risk_tier, 0.64)

    if won:
        xp_gained = random.randint(12, 20)
        outcome = "Victory"
        description = f"{description} You grit your teeth, answer the pressure head-on, and come out standing."
        title = f"{event.title} Won"
    else:
        xp_gained = 5
        outcome = "Setback"
        description = f"{description} You survive, but the clash leaves you bruised, breathing hard, and reminded what these streets cost."
        title = f"{event.title} Lost"

    return title, description, xp_gained, outcome


def _resolve_choice_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.choice_events)
    xp_floor = max(3, approach.xp_min - 1)
    xp_ceiling = max(xp_floor, approach.xp_max - 2)
    xp_gained = random.randint(xp_floor, xp_ceiling)
    description = (
        f"{_format_event_description(event, exploration)} "
        "Your read on the moment pays off, and the district teaches you something worth keeping."
    )
    return event.title, description, xp_gained


def _resolve_flavor_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.flavor_events)
    description = _format_event_description(event, exploration)
    return event.title, description, 0


def roll_exploration_event(
    exploration: ActiveExploration,
) -> tuple[Literal["reward", "combat", "choice", "flavor"], str, str, int, str | None]:
    event_type = _weighted_event_type(exploration)

    if event_type == "reward":
        title, description, xp_gained = _resolve_reward_event(exploration)
        return "reward", title, description, xp_gained, None

    if event_type == "combat":
        title, description, xp_gained, outcome = _resolve_combat_event(exploration)
        return "combat", title, description, xp_gained, outcome

    if event_type == "choice":
        title, description, xp_gained = _resolve_choice_event(exploration)
        return "choice", title, description, xp_gained, None

    title, description, xp_gained = _resolve_flavor_event(exploration)
    return "flavor", title, description, xp_gained, None


async def start_exploration(
    pool: Pool | None,
    user_id: int,
    channel_id: int,
    approach_key: str,
) -> StartExplorationResult:
    if pool is None:
        return StartExplorationResult(status="missing_profile")

    approach = get_explore_approach(approach_key)
    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return StartExplorationResult(status="missing_profile")

            player = PlayerProfile.from_record(player_sync.record)
            rest_minutes = player_sync.resting_minutes
            rest_recovery = player_sync.rest_stamina_gained

            if player.is_resting:
                return StartExplorationResult(
                    status="resting",
                    player=player,
                    rest_minutes=rest_minutes,
                    rest_recovery=rest_recovery,
                )

            existing_exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if existing_exploration_record is not None:
                exploration = ActiveExploration.from_record(existing_exploration_record)
                if exploration.end_time > now:
                    return StartExplorationResult(status="active", player=player, exploration=exploration)

                return StartExplorationResult(status="finished", player=player, exploration=exploration)

            if player.stamina_current < approach.stamina_cost:
                return StartExplorationResult(status="insufficient_stamina", player=player)

            updated_player_record = await update_player_record(
                connection,
                user_id,
                {
                    "stamina_current": player.stamina_current - approach.stamina_cost,
                    "stamina_updated_at": now,
                },
            )
            updated_player = PlayerProfile.from_record(updated_player_record)

            exploration = await create_active_exploration(
                connection=connection,
                user_id=user_id,
                channel_id=channel_id,
                location=updated_player.location,
                approach=approach.key,
                start_time=now,
                end_time=now.replace(microsecond=0) + timedelta(minutes=approach.duration_minutes),
            )
            return StartExplorationResult(status="started", player=updated_player, exploration=exploration)


async def resolve_exploration(
    pool: Pool | None,
    user_id: int,
    *,
    force: bool = False,
) -> ExplorationResolution | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        async with connection.transaction():
            exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if exploration_record is None:
                return None

            exploration = ActiveExploration.from_record(exploration_record)
            if exploration.end_time > datetime.now(timezone.utc) and not force:
                return None

            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return None

            player_record = player_sync.record
            event_type, title, description, xp_gained, combat_outcome = roll_exploration_event(exploration)
            new_level, new_xp, levels_gained = apply_experience_gain(
                current_level=int(player_record["level"]),
                current_xp=int(player_record["xp"]),
                xp_gain=xp_gained,
            )

            updated_player_record = await update_player_record(
                connection,
                user_id,
                {
                    "level": new_level,
                    "xp": new_xp,
                },
            )
            await delete_active_exploration(connection, user_id)

    player = PlayerProfile.from_record(updated_player_record)
    return ExplorationResolution(
        exploration=exploration,
        player=player,
        event_type=event_type,
        title=title,
        description=description,
        xp_gained=xp_gained,
        levels_gained=levels_gained,
        combat_outcome=combat_outcome,
    )


def build_exploration_result_embed(resolution: ExplorationResolution) -> discord.Embed:
    location = get_location_definition(resolution.exploration.location)
    approach = get_explore_approach(resolution.exploration.approach)

    color_by_event = {
        "reward": discord.Color.gold(),
        "combat": discord.Color.red(),
        "choice": discord.Color.blue(),
        "flavor": discord.Color.dark_teal(),
    }

    embed = discord.Embed(
        title=resolution.title,
        description=resolution.description,
        color=color_by_event[resolution.event_type],
    )
    embed.add_field(
        name="Street Run",
        value=(
            f"Location: **{location.name}**\n"
            f"Approach: **{approach.label}**\n"
            f"Duration: **{approach.duration_minutes} minute(s)**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Outcome",
        value=(
            f"XP Gained: **{resolution.xp_gained}**\n"
            f"Level: **{resolution.player.level}**\n"
            f"XP Progress: **{resolution.player.xp}**"
        ),
        inline=True,
    )

    if resolution.combat_outcome is not None:
        embed.add_field(name="Combat Result", value=f"**{resolution.combat_outcome}**", inline=False)

    if resolution.levels_gained > 0:
        embed.add_field(
            name="Level Up",
            value=f"Your reiatsu sharpens. You gained **{resolution.levels_gained}** level(s).",
            inline=False,
        )

    embed.set_footer(text="Bleach RPG | Exploration Complete")
    return embed


async def post_exploration_result(bot: "BleachBot", resolution: ExplorationResolution) -> None:
    channel = bot.get_channel(resolution.exploration.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(resolution.exploration.channel_id)
        except discord.HTTPException:
            logging.exception(
                "Could not fetch channel %s for exploration result.",
                resolution.exploration.channel_id,
            )
            return

    if not hasattr(channel, "send"):
        logging.warning("Channel %s is not messageable for exploration result.", resolution.exploration.channel_id)
        return

    embed = build_exploration_result_embed(resolution)
    try:
        await channel.send(content=f"<@{resolution.exploration.user_id}>", embed=embed)
    except discord.HTTPException:
        logging.exception("Failed to send exploration result for user %s.", resolution.exploration.user_id)


async def resolve_and_post_exploration(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
) -> ExplorationResolution | None:
    resolution = await resolve_exploration(bot.db_pool, user_id, force=force)
    if resolution is None:
        return None

    await post_exploration_result(bot, resolution)
    return resolution


async def _run_exploration_task(bot: "BleachBot", exploration: ActiveExploration) -> None:
    try:
        delay_seconds = max(
            0.0,
            (exploration.end_time.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds(),
        )
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        await resolve_and_post_exploration(bot, exploration.user_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Unexpected error while resolving exploration for user %s.", exploration.user_id)
    finally:
        bot.exploration_tasks.pop(exploration.user_id, None)


def schedule_exploration_task(bot: "BleachBot", exploration: ActiveExploration) -> None:
    existing_task = bot.exploration_tasks.get(exploration.user_id)
    if existing_task is not None:
        existing_task.cancel()

    bot.exploration_tasks[exploration.user_id] = asyncio.create_task(
        _run_exploration_task(bot, exploration)
    )


async def restore_exploration_tasks(bot: "BleachBot") -> None:
    active_explorations = await list_active_explorations(bot.db_pool)
    for exploration in active_explorations:
        schedule_exploration_task(bot, exploration)


def get_exploration_remaining_time(exploration: ActiveExploration) -> str:
    return format_remaining_duration(exploration.end_time)
