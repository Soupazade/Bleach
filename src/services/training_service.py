from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import TYPE_CHECKING, Literal

import discord
from asyncpg import Connection, Pool, Record

from src.data.training import (
    ALL_STATS_KEY,
    TRAINING_YARD_LOCATION_KEY,
    get_training_duration,
    get_training_earned_reward,
    get_training_early_stop_reward,
    get_training_focus,
    get_training_full_reward,
    get_training_milestones_completed,
    is_valid_training_selection,
)
from src.models.exploration import ActiveExploration
from src.models.player import PlayerProfile
from src.models.training import ActiveTraining
from src.models.travel import ActiveTravel
from src.models.work import ActiveWork
from src.services.combat_service import fetch_active_combat_record
from src.services.exploration_service import (
    fetch_active_exploration_record,
    fetch_pending_choice_record,
)
from src.services.formulas import (
    calculate_minutes_elapsed,
    format_remaining_duration,
    get_remaining_stat_capacity,
)
from src.services.player_service import (
    fetch_player_record,
    get_or_sync_player_record,
    set_stamina_resume_timestamp,
    update_player_record,
)
from src.services.reputation_service import (
    apply_rep_stamina_cost,
    get_location_reputation_title,
    get_location_reputation_value,
)
from src.services.status_service import is_player_wounded_for_connection
from src.services.travel_service import fetch_active_travel_record

if TYPE_CHECKING:
    from src.main import BleachBot


ACTIVE_TRAINING_COLUMNS = """
    user_id,
    channel_id,
    stat_target,
    duration_minutes,
    start_time,
    end_time,
    stamina_cost
"""


@dataclass(slots=True)
class TrainingProgressSnapshot:
    elapsed_minutes: int
    remaining_text: str
    milestones_completed: int
    earned_reward: dict[str, int]
    early_stop_reward: dict[str, int]


@dataclass(slots=True)
class StartTrainingResult:
    status: Literal[
        "started",
        "missing_profile",
        "resting",
        "insufficient_stamina",
        "active_training",
        "finished",
        "active_exploration",
        "pending_choice",
        "active_combat",
        "active_travel",
        "active_work",
        "invalid_selection",
        "wrong_location",
        "wounded",
    ]
    player: PlayerProfile | None = None
    training: ActiveTraining | None = None
    exploration: ActiveExploration | None = None
    travel: ActiveTravel | None = None
    work: ActiveWork | None = None
    stamina_cost: int = 0
    base_stamina_cost: int = 0


@dataclass(slots=True)
class TrainingResolution:
    training: ActiveTraining
    player: PlayerProfile
    reward: dict[str, int]
    elapsed_minutes: int
    milestones_completed: int
    was_early_stop: bool


async def fetch_active_training_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_TRAINING_COLUMNS}
        FROM active_trainings
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def list_active_trainings(pool: Pool | None) -> list[ActiveTraining]:
    if pool is None:
        return []

    async with pool.acquire() as connection:
        records = await connection.fetch(
            f"""
            SELECT {ACTIVE_TRAINING_COLUMNS}
            FROM active_trainings
            """
        )

    return [ActiveTraining.from_record(record) for record in records]


async def get_active_training(pool: Pool | None, user_id: int) -> ActiveTraining | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_training_record(connection, user_id)
        if record is None:
            return None

        return ActiveTraining.from_record(record)


async def create_active_training(
    connection: Connection,
    *,
    user_id: int,
    channel_id: int,
    stat_target: str,
    duration_minutes: int,
    start_time: datetime,
    end_time: datetime,
    stamina_cost: int,
) -> ActiveTraining:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_trainings (
            user_id,
            channel_id,
            stat_target,
            duration_minutes,
            start_time,
            end_time,
            stamina_cost
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING {ACTIVE_TRAINING_COLUMNS}
        """,
        user_id,
        channel_id,
        stat_target,
        duration_minutes,
        start_time,
        end_time,
        stamina_cost,
    )
    return ActiveTraining.from_record(record)


async def delete_active_training(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_trainings
        WHERE user_id = $1
        """,
        user_id,
    )


def _apply_training_stamina_cost(
    player: PlayerProfile,
    base_cost: int,
) -> tuple[int, int]:
    rep_value = get_location_reputation_value(player, player.location)
    adjusted_cost = apply_rep_stamina_cost(base_cost, rep_value)
    return adjusted_cost, adjusted_cost - base_cost


def _apply_shared_stat_cap(
    player: PlayerProfile,
    reward: dict[str, int],
) -> dict[str, int]:
    remaining_capacity = get_remaining_stat_capacity(
        level=player.level,
        power=player.power,
        defense=player.defense,
        speed=player.speed,
        reiatsu=player.reiatsu,
    )
    if remaining_capacity <= 0 or not reward:
        return {}

    capped_reward: dict[str, int] = {}
    for stat_name in ("power", "defense", "speed", "reiatsu"):
        gain = reward.get(stat_name, 0)
        if gain <= 0 or remaining_capacity <= 0:
            continue

        applied_gain = min(gain, remaining_capacity)
        capped_reward[stat_name] = applied_gain
        remaining_capacity -= applied_gain

    return capped_reward


def get_training_progress_snapshot(
    training: ActiveTraining,
    *,
    now: datetime | None = None,
) -> TrainingProgressSnapshot:
    if now is None:
        now = datetime.now(timezone.utc)

    elapsed_minutes = min(
        training.duration_minutes,
        calculate_minutes_elapsed(training.start_time, now),
    )
    milestones_completed = get_training_milestones_completed(
        training.duration_minutes,
        elapsed_minutes,
    )
    return TrainingProgressSnapshot(
        elapsed_minutes=elapsed_minutes,
        remaining_text=format_remaining_duration(training.end_time, now),
        milestones_completed=milestones_completed,
        earned_reward=get_training_earned_reward(
            training.stat_target,
            training.duration_minutes,
            elapsed_minutes,
        ),
        early_stop_reward=get_training_early_stop_reward(
            training.stat_target,
            training.duration_minutes,
            elapsed_minutes,
        ),
    )


async def start_training(
    pool: Pool | None,
    user_id: int,
    channel_id: int,
    stat_target: str,
    duration_minutes: int,
) -> StartTrainingResult:
    from src.services.work_service import fetch_active_work_record

    if pool is None:
        return StartTrainingResult(status="missing_profile")

    if not is_valid_training_selection(stat_target, duration_minutes):
        return StartTrainingResult(status="invalid_selection")

    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return StartTrainingResult(status="missing_profile")

            player = PlayerProfile.from_record(player_sync.record)
            if player.is_resting:
                return StartTrainingResult(status="resting", player=player)

            if await is_player_wounded_for_connection(connection, user_id, for_update=True):
                return StartTrainingResult(status="wounded", player=player)

            if player.location != TRAINING_YARD_LOCATION_KEY:
                return StartTrainingResult(status="wrong_location", player=player)

            pending_choice_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            if pending_choice_record is not None:
                return StartTrainingResult(status="pending_choice", player=player)

            combat_record = await fetch_active_combat_record(connection, user_id, for_update=True)
            if combat_record is not None:
                return StartTrainingResult(status="active_combat", player=player)

            exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if exploration_record is not None:
                return StartTrainingResult(
                    status="active_exploration",
                    player=player,
                    exploration=ActiveExploration.from_record(exploration_record),
                )

            travel_record = await fetch_active_travel_record(connection, user_id, for_update=True)
            if travel_record is not None:
                return StartTrainingResult(
                    status="active_travel",
                    player=player,
                    travel=ActiveTravel.from_record(travel_record),
                )

            training_record = await fetch_active_training_record(connection, user_id, for_update=True)
            if training_record is not None:
                training = ActiveTraining.from_record(training_record)
                if training.end_time > now:
                    return StartTrainingResult(status="active_training", player=player, training=training)
                return StartTrainingResult(status="finished", player=player, training=training)

            work_record = await fetch_active_work_record(connection, user_id, for_update=True)
            if work_record is not None:
                return StartTrainingResult(
                    status="active_work",
                    player=player,
                    work=ActiveWork.from_record(work_record),
                )

            duration = get_training_duration(duration_minutes)
            stamina_cost, _ = _apply_training_stamina_cost(player, duration.stamina_cost)
            if player.stamina_current < stamina_cost:
                return StartTrainingResult(
                    status="insufficient_stamina",
                    player=player,
                    stamina_cost=stamina_cost,
                    base_stamina_cost=duration.stamina_cost,
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
            training = await create_active_training(
                connection,
                user_id=user_id,
                channel_id=channel_id,
                stat_target=stat_target,
                duration_minutes=duration_minutes,
                start_time=now,
                end_time=now.replace(microsecond=0) + timedelta(minutes=duration_minutes),
                stamina_cost=stamina_cost,
            )
            return StartTrainingResult(
                status="started",
                player=updated_player,
                training=training,
                stamina_cost=stamina_cost,
                base_stamina_cost=duration.stamina_cost,
            )


async def resolve_training(
    pool: Pool | None,
    user_id: int,
    *,
    force: bool = False,
    early_stop: bool = False,
) -> TrainingResolution | None:
    if pool is None:
        return None

    now = datetime.now(timezone.utc)

    async with pool.acquire() as connection:
        async with connection.transaction():
            training_record = await fetch_active_training_record(connection, user_id, for_update=True)
            if training_record is None:
                return None

            training = ActiveTraining.from_record(training_record)
            if training.end_time > now and not force and not early_stop:
                return None

            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return None

            current_player = PlayerProfile.from_record(player_sync.record)
            elapsed_minutes = min(
                training.duration_minutes,
                calculate_minutes_elapsed(training.start_time, now),
            )
            milestones_completed = get_training_milestones_completed(
                training.duration_minutes,
                elapsed_minutes,
            )
            if early_stop:
                reward = get_training_early_stop_reward(
                    training.stat_target,
                    training.duration_minutes,
                    elapsed_minutes,
                )
                resume_at = now
            else:
                reward = get_training_full_reward(
                    training.stat_target,
                    training.duration_minutes,
                )
                resume_at = now if force and training.end_time > now else training.end_time

            reward = _apply_shared_stat_cap(current_player, reward)

            stat_updates = {
                stat_name: getattr(current_player, stat_name) + gain
                for stat_name, gain in reward.items()
            }
            if stat_updates:
                await update_player_record(connection, user_id, stat_updates)

            await set_stamina_resume_timestamp(connection, user_id, resume_at)
            await delete_active_training(connection, user_id)

            final_record = await fetch_player_record(connection, user_id, for_update=True)
            if final_record is None:
                return None

            return TrainingResolution(
                training=training,
                player=PlayerProfile.from_record(final_record),
                reward=reward,
                elapsed_minutes=elapsed_minutes,
                milestones_completed=milestones_completed,
                was_early_stop=early_stop and training.end_time > now,
            )


async def post_training_completion(bot: "BleachBot", resolution: TrainingResolution) -> None:
    from src.ui.train_view import build_training_complete_embed

    channel = bot.get_channel(resolution.training.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(resolution.training.channel_id)
        except discord.HTTPException:
            logging.exception(
                "Could not fetch channel %s for training completion.",
                resolution.training.channel_id,
            )
            return

    if not hasattr(channel, "send"):
        logging.warning(
            "Training completion channel %s does not support sending messages.",
            resolution.training.channel_id,
        )
        return

    try:
        await channel.send(
            content=f"<@{resolution.training.user_id}>",
            embed=build_training_complete_embed(resolution),
        )
    except discord.HTTPException:
        logging.exception(
            "Failed to post training completion for user %s.",
            resolution.training.user_id,
        )


async def resolve_and_post_training(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
    early_stop: bool = False,
) -> TrainingResolution | None:
    resolution = await resolve_training(
        bot.db_pool,
        user_id,
        force=force,
        early_stop=early_stop,
    )
    if resolution is None:
        return None

    if not early_stop:
        await post_training_completion(bot, resolution)
    return resolution


async def _run_training_task(bot: "BleachBot", training: ActiveTraining) -> None:
    try:
        while True:
            delay_seconds = (
                training.end_time.astimezone(timezone.utc) - datetime.now(timezone.utc)
            ).total_seconds()
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds + 0.25)

            resolution = await resolve_and_post_training(bot, training.user_id)
            if resolution is not None:
                break

            refreshed_training = await get_active_training(bot.db_pool, training.user_id)
            if refreshed_training is None:
                break

            training = refreshed_training
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception(
            "Unexpected error while resolving training for user %s.",
            training.user_id,
        )
    finally:
        bot.training_tasks.pop(training.user_id, None)


def schedule_training_task(bot: "BleachBot", training: ActiveTraining) -> None:
    existing_task = bot.training_tasks.get(training.user_id)
    if existing_task is not None:
        existing_task.cancel()

    bot.training_tasks[training.user_id] = asyncio.create_task(_run_training_task(bot, training))


async def restore_training_tasks(bot: "BleachBot") -> None:
    for training in await list_active_trainings(bot.db_pool):
        schedule_training_task(bot, training)


def get_training_remaining_time(training: ActiveTraining) -> str:
    return format_remaining_duration(training.end_time)


def get_training_stamina_text(
    player: PlayerProfile,
    duration_minutes: int,
) -> tuple[int, int, str]:
    base_duration = get_training_duration(duration_minutes)
    stamina_cost, modifier = _apply_training_stamina_cost(player, base_duration.stamina_cost)
    reputation_title = get_location_reputation_title(player, player.location)
    return stamina_cost, modifier, reputation_title


def format_training_reward_lines(reward: dict[str, int]) -> str:
    if not reward:
        return "No gains have set in yet."

    lines: list[str] = []
    for stat_name in ("power", "defense", "speed", "reiatsu"):
        gain = reward.get(stat_name)
        if not gain:
            continue

        label = get_training_focus(stat_name).label
        lines.append(f"📈 {label}: +{gain}")

    return "\n".join(lines) if lines else "No gains have set in yet."


def get_training_focus_label(stat_target: str) -> str:
    if stat_target == ALL_STATS_KEY:
        return "All Stats"

    return get_training_focus(stat_target).label
