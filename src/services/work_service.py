from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import random
from typing import TYPE_CHECKING, Literal

import discord
from asyncpg import Connection, Pool, Record

from src.data.work import WorkDefinition, get_work_definition
from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.models.player import PlayerProfile
from src.models.travel import ActiveTravel
from src.models.training import ActiveTraining
from src.models.work import ActiveWork
from src.services.combat_service import fetch_active_combat_record
from src.services.dungeon_service import fetch_active_dungeon_record
from src.services.exploration_service import (
    fetch_active_exploration_record,
    fetch_pending_choice_record,
)
from src.services.formulas import format_remaining_duration
from src.services.player_service import (
    get_or_sync_player_record,
    set_stamina_resume_timestamp,
    update_player_record,
)
from src.services.reputation_service import (
    apply_rep_stamina_cost,
    apply_reputation_change,
    get_location_reputation_field,
    get_location_reputation_title,
    get_location_reputation_value,
)
from src.services.training_service import fetch_active_training_record
from src.services.travel_service import fetch_active_travel_record

if TYPE_CHECKING:
    from src.main import BleachBot


ACTIVE_WORK_COLUMNS = """
    user_id,
    channel_id,
    location,
    work_key,
    start_time,
    end_time,
    stamina_cost
"""


@dataclass(slots=True)
class StartWorkResult:
    status: Literal[
        "started",
        "missing_profile",
        "resting",
        "insufficient_stamina",
        "active_work",
        "finished",
        "active_exploration",
        "pending_choice",
        "active_combat",
        "active_travel",
        "active_training",
        "active_dungeon",
        "invalid_work",
        "wrong_location",
    ]
    player: PlayerProfile | None = None
    work: ActiveWork | None = None
    exploration: ActiveExploration | None = None
    pending_choice: PendingExplorationChoice | None = None
    travel: ActiveTravel | None = None
    training: ActiveTraining | None = None
    stamina_cost: int = 0
    base_stamina_cost: int = 0


@dataclass(slots=True)
class WorkResolution:
    work: ActiveWork
    player: PlayerProfile
    job: WorkDefinition
    kan_earned: int
    reputation_change: int
    payout_modifier: int


def _apply_work_stamina_cost(player: PlayerProfile, base_cost: int) -> tuple[int, int]:
    rep_value = get_location_reputation_value(player, player.location)
    adjusted_cost = apply_rep_stamina_cost(base_cost, rep_value)
    return adjusted_cost, adjusted_cost - base_cost


def calculate_work_payout(
    *,
    work: WorkDefinition,
    reputation_value: int,
    rng: random.Random | None = None,
) -> tuple[int, int]:
    generator = rng or random
    base_reward = generator.randint(work.kan_min, work.kan_max)
    payout_modifier = 0
    if work.alignment == "legit":
        payout_modifier = max(0, reputation_value // 25)
    elif work.alignment == "shady":
        payout_modifier = max(0, abs(min(reputation_value, 0)) // 12)
    elif work.key == "streets_beg_cookfires":
        payout_modifier = max(0, abs(reputation_value) // 30)
    return max(1, base_reward + payout_modifier), payout_modifier


async def fetch_active_work_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_WORK_COLUMNS}
        FROM active_works
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def list_active_works(pool: Pool | None) -> list[ActiveWork]:
    if pool is None:
        return []

    async with pool.acquire() as connection:
        records = await connection.fetch(
            f"""
            SELECT {ACTIVE_WORK_COLUMNS}
            FROM active_works
            """
        )

    return [ActiveWork.from_record(record) for record in records]


async def get_active_work(pool: Pool | None, user_id: int) -> ActiveWork | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_work_record(connection, user_id)
        if record is None:
            return None

        return ActiveWork.from_record(record)


async def create_active_work(
    connection: Connection,
    *,
    user_id: int,
    channel_id: int,
    location: str,
    work_key: str,
    start_time: datetime,
    end_time: datetime,
    stamina_cost: int,
) -> ActiveWork:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_works (
            user_id,
            channel_id,
            location,
            work_key,
            start_time,
            end_time,
            stamina_cost
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING {ACTIVE_WORK_COLUMNS}
        """,
        user_id,
        channel_id,
        location,
        work_key,
        start_time,
        end_time,
        stamina_cost,
    )
    return ActiveWork.from_record(record)


async def delete_active_work(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_works
        WHERE user_id = $1
        """,
        user_id,
    )


async def start_work(
    pool: Pool | None,
    *,
    user_id: int,
    channel_id: int,
    work_key: str,
) -> StartWorkResult:
    if pool is None:
        return StartWorkResult(status="missing_profile")

    try:
        job = get_work_definition(work_key)
    except ValueError:
        return StartWorkResult(status="invalid_work")

    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return StartWorkResult(status="missing_profile")

            player = PlayerProfile.from_record(player_sync.record)
            if player.is_resting:
                return StartWorkResult(status="resting", player=player)
            if player.location != job.location_key:
                return StartWorkResult(status="wrong_location", player=player)

            pending_choice_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            if pending_choice_record is not None:
                return StartWorkResult(
                    status="pending_choice",
                    player=player,
                    pending_choice=PendingExplorationChoice.from_record(pending_choice_record),
                )

            combat_record = await fetch_active_combat_record(connection, user_id, for_update=True)
            if combat_record is not None:
                return StartWorkResult(status="active_combat", player=player)

            exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if exploration_record is not None:
                return StartWorkResult(
                    status="active_exploration",
                    player=player,
                    exploration=ActiveExploration.from_record(exploration_record),
                )

            travel_record = await fetch_active_travel_record(connection, user_id, for_update=True)
            if travel_record is not None:
                return StartWorkResult(
                    status="active_travel",
                    player=player,
                    travel=ActiveTravel.from_record(travel_record),
                )

            training_record = await fetch_active_training_record(connection, user_id, for_update=True)
            if training_record is not None:
                return StartWorkResult(
                    status="active_training",
                    player=player,
                    training=ActiveTraining.from_record(training_record),
                )

            dungeon_record = await fetch_active_dungeon_record(connection, user_id, for_update=True)
            if dungeon_record is not None:
                return StartWorkResult(status="active_dungeon", player=player)

            work_record = await fetch_active_work_record(connection, user_id, for_update=True)
            if work_record is not None:
                work = ActiveWork.from_record(work_record)
                if work.end_time > now:
                    return StartWorkResult(status="active_work", player=player, work=work)
                return StartWorkResult(status="finished", player=player, work=work)

            stamina_cost, _ = _apply_work_stamina_cost(player, job.stamina_cost)
            if player.stamina_current < stamina_cost:
                return StartWorkResult(
                    status="insufficient_stamina",
                    player=player,
                    stamina_cost=stamina_cost,
                    base_stamina_cost=job.stamina_cost,
                )

            updated_player_record = await update_player_record(
                connection,
                user_id,
                {
                    "stamina_current": player.stamina_current - stamina_cost,
                    "stamina_updated_at": now,
                },
            )
            updated_player = PlayerProfile.from_record(updated_player_record)
            work = await create_active_work(
                connection,
                user_id=user_id,
                channel_id=channel_id,
                location=updated_player.location,
                work_key=job.key,
                start_time=now,
                end_time=now.replace(microsecond=0) + timedelta(minutes=job.duration_minutes),
                stamina_cost=stamina_cost,
            )
            return StartWorkResult(
                status="started",
                player=updated_player,
                work=work,
                stamina_cost=stamina_cost,
                base_stamina_cost=job.stamina_cost,
            )


async def resolve_work(
    pool: Pool | None,
    user_id: int,
    *,
    force: bool = False,
) -> WorkResolution | None:
    if pool is None:
        return None

    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            work_record = await fetch_active_work_record(connection, user_id, for_update=True)
            if work_record is None:
                return None

            work = ActiveWork.from_record(work_record)
            if work.end_time > now and not force:
                return None

            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return None

            player = PlayerProfile.from_record(player_sync.record)
            job = get_work_definition(work.work_key)
            current_reputation = get_location_reputation_value(player, work.location)
            kan_earned, payout_modifier = calculate_work_payout(
                work=job,
                reputation_value=current_reputation,
            )
            applied_reputation_change = 0
            updates = {
                "kan": player.kan + kan_earned,
            }
            if job.reputation_change != 0:
                reputation_field = get_location_reputation_field(work.location)
                updated_reputation = apply_reputation_change(current_reputation, job.reputation_change)
                applied_reputation_change = updated_reputation - current_reputation
                updates[reputation_field] = updated_reputation

            updated_record = await update_player_record(connection, user_id, updates)
            await set_stamina_resume_timestamp(
                connection,
                user_id,
                now if force and work.end_time > now else work.end_time,
            )
            await delete_active_work(connection, user_id)
            return WorkResolution(
                work=work,
                player=PlayerProfile.from_record(updated_record),
                job=job,
                kan_earned=kan_earned,
                reputation_change=applied_reputation_change,
                payout_modifier=payout_modifier,
            )


async def post_work_completion(bot: "BleachBot", resolution: WorkResolution) -> None:
    from src.ui.work_view import build_work_complete_embed

    channel = bot.get_channel(resolution.work.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(resolution.work.channel_id)
        except discord.HTTPException:
            logging.exception(
                "Could not fetch channel %s for work completion.",
                resolution.work.channel_id,
            )
            return

    if not hasattr(channel, "send"):
        logging.warning(
            "Work completion channel %s does not support sending messages.",
            resolution.work.channel_id,
        )
        return

    try:
        await channel.send(
            content=f"<@{resolution.work.user_id}>",
            embed=build_work_complete_embed(resolution),
        )
    except discord.HTTPException:
        logging.exception(
            "Failed to post work completion for user %s.",
            resolution.work.user_id,
        )


async def resolve_and_post_work(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
) -> WorkResolution | None:
    resolution = await resolve_work(bot.db_pool, user_id, force=force)
    if resolution is None:
        return None

    await post_work_completion(bot, resolution)
    return resolution


async def _run_work_task(bot: "BleachBot", work: ActiveWork) -> None:
    try:
        while True:
            delay_seconds = (
                work.end_time.astimezone(timezone.utc) - datetime.now(timezone.utc)
            ).total_seconds()
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds + 0.25)

            resolution = await resolve_and_post_work(bot, work.user_id)
            if resolution is not None:
                break

            refreshed_work = await get_active_work(bot.db_pool, work.user_id)
            if refreshed_work is None:
                break

            work = refreshed_work
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Unexpected error while resolving work for user %s.", work.user_id)
    finally:
        bot.work_tasks.pop(work.user_id, None)


def schedule_work_task(bot: "BleachBot", work: ActiveWork) -> None:
    existing_task = bot.work_tasks.get(work.user_id)
    if existing_task is not None:
        existing_task.cancel()

    bot.work_tasks[work.user_id] = asyncio.create_task(_run_work_task(bot, work))


async def restore_work_tasks(bot: "BleachBot") -> None:
    for work in await list_active_works(bot.db_pool):
        schedule_work_task(bot, work)


def get_work_remaining_time(work: ActiveWork) -> str:
    return format_remaining_duration(work.end_time)


def get_work_stamina_text(player: PlayerProfile, work_key: str) -> tuple[int, int, str]:
    job = get_work_definition(work_key)
    stamina_cost, modifier = _apply_work_stamina_cost(player, job.stamina_cost)
    reputation_title = get_location_reputation_title(player, player.location)
    return stamina_cost, modifier, reputation_title
