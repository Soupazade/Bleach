from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING

from src.models.exploration import ActiveExploration
from src.services.exploration.posting import resolve_and_post_exploration
from src.services.exploration.repository import get_active_exploration, list_active_explorations
from src.services.formulas import format_remaining_duration

if TYPE_CHECKING:
    from src.main import BleachBot


async def _run_exploration_task(bot: "BleachBot", exploration: ActiveExploration) -> None:
    try:
        while True:
            delay_seconds = (
                exploration.end_time.astimezone(timezone.utc) - datetime.now(timezone.utc)
            ).total_seconds()
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds + 0.25)

            post_result = await resolve_and_post_exploration(bot, exploration.user_id)
            if post_result is not None:
                break

            refreshed_exploration = await get_active_exploration(bot.db_pool, exploration.user_id)
            if refreshed_exploration is None:
                break

            exploration = refreshed_exploration
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Unexpected error while resolving exploration for user %s.", exploration.user_id)
    finally:
        bot.exploration_tasks.pop(exploration.user_id, None)


async def _run_exploration_watchdog(bot: "BleachBot") -> None:
    try:
        while True:
            active_explorations = await list_active_explorations(bot.db_pool)
            for exploration in active_explorations:
                tracked_task = bot.exploration_tasks.get(exploration.user_id)
                if tracked_task is None or tracked_task.done():
                    schedule_exploration_task(bot, exploration)
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Unexpected error in exploration watchdog.")


def schedule_exploration_task(bot: "BleachBot", exploration: ActiveExploration) -> None:
    existing_task = bot.exploration_tasks.get(exploration.user_id)
    if existing_task is not None:
        existing_task.cancel()

    bot.exploration_tasks[exploration.user_id] = asyncio.create_task(_run_exploration_task(bot, exploration))


async def restore_exploration_tasks(bot: "BleachBot") -> None:
    active_explorations = await list_active_explorations(bot.db_pool)
    for exploration in active_explorations:
        schedule_exploration_task(bot, exploration)


def start_exploration_watchdog(bot: "BleachBot") -> None:
    existing_task = getattr(bot, "exploration_watchdog_task", None)
    if existing_task is not None:
        existing_task.cancel()
    bot.exploration_watchdog_task = asyncio.create_task(_run_exploration_watchdog(bot))


def get_exploration_remaining_time(exploration: ActiveExploration) -> str:
    return format_remaining_duration(exploration.end_time)
