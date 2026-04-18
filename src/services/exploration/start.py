from __future__ import annotations

from datetime import datetime, timedelta, timezone

from asyncpg import Pool

from src.data.exploration import get_explore_approach
from src.models.exploration import PendingExplorationChoice
from src.models.player import PlayerProfile
from src.models.work import ActiveWork
from src.services.exploration.choices import build_decision_prompt
from src.services.exploration.repository import (
    create_active_exploration,
    fetch_active_exploration_record,
    fetch_pending_choice_record,
)
from src.services.exploration.rewards import apply_location_stamina_cost_modifier
from src.services.status_service import is_player_wounded_for_connection
from src.services.exploration.types import StartExplorationResult
from src.services.player_service import get_or_sync_player_record, update_player_record


async def start_exploration(
    pool: Pool | None,
    user_id: int,
    channel_id: int,
    approach_key: str,
) -> StartExplorationResult:
    from src.services.work_service import fetch_active_work_record

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

            pending_choice_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            if pending_choice_record is not None:
                pending_choice = PendingExplorationChoice.from_record(pending_choice_record)
                return StartExplorationResult(
                    status="pending_choice",
                    player=player,
                    pending_choice=build_decision_prompt(pending_choice, player),
                )

            existing_exploration_record = await fetch_active_exploration_record(connection, user_id, for_update=True)
            if existing_exploration_record is not None:
                from src.models.exploration import ActiveExploration

                exploration = ActiveExploration.from_record(existing_exploration_record)
                if exploration.end_time > now:
                    return StartExplorationResult(status="active", player=player, exploration=exploration)

                return StartExplorationResult(status="finished", player=player, exploration=exploration)

            active_work_record = await fetch_active_work_record(connection, user_id, for_update=True)
            if active_work_record is not None:
                return StartExplorationResult(
                    status="active_work",
                    player=player,
                    work=ActiveWork.from_record(active_work_record),
                )

            stamina_cost, _ = apply_location_stamina_cost_modifier(
                player,
                player.location,
                approach.stamina_cost,
            )
            duration_minutes = approach.duration_minutes
            wounded_penalty = await is_player_wounded_for_connection(connection, user_id, for_update=True)
            if wounded_penalty:
                stamina_cost *= 2
                duration_minutes *= 2
            if player.stamina_current < stamina_cost:
                return StartExplorationResult(
                    status="insufficient_stamina",
                    player=player,
                    stamina_cost=stamina_cost,
                    base_stamina_cost=approach.stamina_cost,
                    duration_minutes=duration_minutes,
                    base_duration_minutes=approach.duration_minutes,
                    wounded_penalty=wounded_penalty,
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

            exploration = await create_active_exploration(
                connection=connection,
                user_id=user_id,
                channel_id=channel_id,
                location=updated_player.location,
                approach=approach.key,
                start_time=now,
                end_time=now.replace(microsecond=0) + timedelta(minutes=duration_minutes),
            )
            return StartExplorationResult(
                status="started",
                player=updated_player,
                exploration=exploration,
                stamina_cost=stamina_cost,
                base_stamina_cost=approach.stamina_cost,
                duration_minutes=duration_minutes,
                base_duration_minutes=approach.duration_minutes,
                wounded_penalty=wounded_penalty,
            )
