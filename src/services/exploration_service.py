from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import random
from typing import TYPE_CHECKING, Any, Literal

import discord
from asyncpg import Connection, Pool, Record

from src.data.exploration import (
    ExploreApproachDefinition,
    ExploreEventType,
    ExplorationDecisionEventDefinition,
    ExplorationDecisionOptionDefinition,
    ExplorationEventTemplate,
    ExplorationOutcomeDefinition,
    get_decision_event_definition,
    get_decision_step_definition,
    get_explore_approach,
    get_location_event_pool,
    get_random_decision_event,
)
from src.data.locations import get_location_definition
from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.models.player import PlayerProfile
from src.services.formulas import apply_experience_gain, format_remaining_duration
from src.services.player_service import get_or_sync_player_record, update_player_record

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

PENDING_EXPLORATION_CHOICE_COLUMNS = """
    user_id,
    channel_id,
    message_id,
    location,
    approach,
    start_time,
    end_time,
    event_key,
    event_flow,
    current_step,
    choice_history,
    created_at,
    updated_at
"""


@dataclass(slots=True)
class StartExplorationResult:
    status: Literal[
        "started",
        "missing_profile",
        "resting",
        "insufficient_stamina",
        "active",
        "finished",
        "pending_choice",
    ]
    player: PlayerProfile | None = None
    exploration: ActiveExploration | None = None
    rest_minutes: int = 0
    rest_recovery: int = 0
    pending_choice: "ExplorationDecisionPrompt | None" = None


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


@dataclass(frozen=True, slots=True)
class ExplorationDecisionOptionRender:
    slot: int
    label: str
    style: Literal["primary", "secondary", "success", "danger"]


@dataclass(slots=True)
class ExplorationDecisionPrompt:
    session: PendingExplorationChoice
    event_title: str
    step_title: str
    description: str
    step_number: int
    total_steps: int
    options: tuple[ExplorationDecisionOptionRender, ...]


@dataclass(slots=True)
class ExplorationPostResult:
    status: Literal["instant", "choice_prompt"]
    resolution: ExplorationResolution | None = None
    prompt: ExplorationDecisionPrompt | None = None


@dataclass(slots=True)
class ExplorationChoiceAdvanceResult:
    status: Literal["missing", "advanced", "resolved"]
    prompt: ExplorationDecisionPrompt | None = None
    resolution: ExplorationResolution | None = None


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


async def fetch_pending_choice_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {PENDING_EXPLORATION_CHOICE_COLUMNS}
        FROM active_exploration_choices
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def fetch_pending_choice_record_by_message(
    connection: Connection,
    message_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {PENDING_EXPLORATION_CHOICE_COLUMNS}
        FROM active_exploration_choices
        WHERE message_id = $1
        {lock_clause}
        """,
        message_id,
    )


async def get_active_exploration(pool: Pool | None, user_id: int) -> ActiveExploration | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_exploration_record(connection, user_id)
        if record is None:
            return None

        return ActiveExploration.from_record(record)


async def get_pending_exploration_choice(pool: Pool | None, user_id: int) -> PendingExplorationChoice | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_pending_choice_record(connection, user_id)
        if record is None:
            return None

        return PendingExplorationChoice.from_record(record)


async def get_pending_exploration_choice_by_message(
    pool: Pool | None,
    message_id: int,
) -> PendingExplorationChoice | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_pending_choice_record_by_message(connection, message_id)
        if record is None:
            return None

        return PendingExplorationChoice.from_record(record)


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


async def create_pending_exploration_choice(
    connection: Connection,
    exploration: ActiveExploration,
    event: ExplorationDecisionEventDefinition,
) -> PendingExplorationChoice:
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_exploration_choices (
            user_id,
            channel_id,
            message_id,
            location,
            approach,
            start_time,
            end_time,
            event_key,
            event_flow,
            current_step,
            choice_history
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING {PENDING_EXPLORATION_CHOICE_COLUMNS}
        """,
        exploration.user_id,
        exploration.channel_id,
        None,
        exploration.location,
        exploration.approach,
        exploration.start_time,
        exploration.end_time,
        event.key,
        event.flow_type,
        event.initial_step_id,
        [],
    )
    return PendingExplorationChoice.from_record(record)


async def update_pending_choice(
    connection: Connection,
    user_id: int,
    fields: dict[str, Any],
) -> PendingExplorationChoice:
    assignments: list[str] = []
    values: list[Any] = []

    for index, (column_name, value) in enumerate(fields.items(), start=1):
        assignments.append(f"{column_name} = ${index}")
        values.append(value)

    values.append(user_id)
    user_id_placeholder = len(values)

    record = await connection.fetchrow(
        f"""
        UPDATE active_exploration_choices
        SET {", ".join(assignments)}, updated_at = NOW()
        WHERE user_id = ${user_id_placeholder}
        RETURNING {PENDING_EXPLORATION_CHOICE_COLUMNS}
        """,
        *values,
    )
    return PendingExplorationChoice.from_record(record)


async def delete_active_exploration(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_explorations
        WHERE user_id = $1
        """,
        user_id,
    )


async def delete_pending_choice(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_exploration_choices
        WHERE user_id = $1
        """,
        user_id,
    )


def _format_text(
    text: str,
    *,
    approach: ExploreApproachDefinition,
    location_name: str,
) -> str:
    return text.format(
        approach=approach.label,
        location=location_name,
    )


def _weighted_event_type(exploration: ActiveExploration) -> ExploreEventType:
    approach = get_explore_approach(exploration.approach)
    event_types = tuple(approach.event_biases.keys())
    weights = tuple(approach.event_biases.values())
    return random.choices(event_types, weights=weights, k=1)[0]


def _roll_resolution_flow(approach: ExploreApproachDefinition) -> ExploreFlowType:
    weights_by_risk = {
        "low": (70, 24, 6),
        "medium": (60, 30, 10),
        "high": (48, 36, 16),
    }
    instant_weight, single_weight, multi_weight = weights_by_risk.get(
        approach.risk_tier,
        (60, 30, 10),
    )
    return random.choices(
        ("instant", "single_choice", "multi_step"),
        weights=(instant_weight, single_weight, multi_weight),
        k=1,
    )[0]


def _format_event_description(
    template: ExplorationEventTemplate,
    exploration: ActiveExploration,
) -> str:
    approach = get_explore_approach(exploration.approach)
    location = get_location_definition(exploration.location)
    return _format_text(
        template.description,
        approach=approach,
        location_name=location.name,
    )


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


def roll_instant_exploration_event(
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


def _resolve_outcome_xp(
    approach: ExploreApproachDefinition,
    xp_profile: Literal[
        "none",
        "approach_low",
        "approach_base",
        "approach_high",
        "combat_win",
        "combat_lose",
    ],
) -> int:
    if xp_profile == "none":
        return 0
    if xp_profile == "combat_win":
        return random.randint(12, 20)
    if xp_profile == "combat_lose":
        return 5
    if xp_profile == "approach_low":
        xp_floor = max(1, approach.xp_min - 3)
        xp_ceiling = max(xp_floor, approach.xp_min)
        return random.randint(xp_floor, xp_ceiling)
    if xp_profile == "approach_high":
        xp_floor = approach.xp_min + 2
        xp_ceiling = max(xp_floor, approach.xp_max + 4)
        return random.randint(xp_floor, xp_ceiling)

    return random.randint(approach.xp_min, approach.xp_max)


async def _apply_xp_gain(
    connection: Connection,
    user_id: int,
    xp_gained: int,
) -> tuple[PlayerProfile, int]:
    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        raise ValueError(f"Missing player profile for user {user_id}")

    player_record = player_sync.record
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
    return PlayerProfile.from_record(updated_player_record), levels_gained


def _build_decision_prompt(session: PendingExplorationChoice) -> ExplorationDecisionPrompt:
    event = get_decision_event_definition(session.location, session.event_key)
    step = get_decision_step_definition(event, session.current_step)
    approach = get_explore_approach(session.approach)
    location = get_location_definition(session.location)
    step_number = min(event.step_count, len(session.choice_history) + 1)

    options = tuple(
        ExplorationDecisionOptionRender(
            slot=index,
            label=option.label,
            style=option.style,
        )
        for index, option in enumerate(step.options, start=1)
    )
    return ExplorationDecisionPrompt(
        session=session,
        event_title=event.title,
        step_title=step.title,
        description=_format_text(step.description, approach=approach, location_name=location.name),
        step_number=step_number,
        total_steps=event.step_count,
        options=options,
    )


async def get_pending_exploration_prompt(
    pool: Pool | None,
    user_id: int,
) -> ExplorationDecisionPrompt | None:
    session = await get_pending_exploration_choice(pool, user_id)
    if session is None:
        return None

    return _build_decision_prompt(session)


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

            pending_choice_record = await fetch_pending_choice_record(connection, user_id, for_update=True)
            if pending_choice_record is not None:
                pending_choice = PendingExplorationChoice.from_record(pending_choice_record)
                return StartExplorationResult(
                    status="pending_choice",
                    player=player,
                    pending_choice=_build_decision_prompt(pending_choice),
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
) -> ExplorationPostResult | None:
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

            approach = get_explore_approach(exploration.approach)
            resolution_flow = _roll_resolution_flow(approach)

            if resolution_flow == "instant":
                event_type, title, description, xp_gained, combat_outcome = roll_instant_exploration_event(exploration)
                player, levels_gained = await _apply_xp_gain(connection, user_id, xp_gained)
                await delete_active_exploration(connection, user_id)
                return ExplorationPostResult(
                    status="instant",
                    resolution=ExplorationResolution(
                        exploration=exploration,
                        player=player,
                        event_type=event_type,
                        title=title,
                        description=description,
                        xp_gained=xp_gained,
                        levels_gained=levels_gained,
                        combat_outcome=combat_outcome,
                    ),
                )

            event = get_random_decision_event(exploration.location, resolution_flow)
            pending_choice = await create_pending_exploration_choice(connection, exploration, event)
            await delete_active_exploration(connection, user_id)
            return ExplorationPostResult(
                status="choice_prompt",
                prompt=_build_decision_prompt(pending_choice),
            )


async def advance_exploration_choice(
    pool: Pool | None,
    *,
    message_id: int,
    user_id: int,
    option_slot: int,
) -> ExplorationChoiceAdvanceResult:
    if pool is None:
        return ExplorationChoiceAdvanceResult(status="missing")

    async with pool.acquire() as connection:
        async with connection.transaction():
            session_record = await fetch_pending_choice_record_by_message(connection, message_id, for_update=True)
            if session_record is None:
                return ExplorationChoiceAdvanceResult(status="missing")

            session = PendingExplorationChoice.from_record(session_record)
            if session.user_id != user_id:
                return ExplorationChoiceAdvanceResult(status="missing")

            event = get_decision_event_definition(session.location, session.event_key)
            step = get_decision_step_definition(event, session.current_step)
            if option_slot < 1 or option_slot > len(step.options):
                return ExplorationChoiceAdvanceResult(status="missing")

            selected_option = step.options[option_slot - 1]
            choice_history = [*session.choice_history, selected_option.key]

            if selected_option.next_step_id is not None:
                updated_session = await update_pending_choice(
                    connection,
                    user_id,
                    {
                        "current_step": selected_option.next_step_id,
                        "choice_history": choice_history,
                    },
                )
                return ExplorationChoiceAdvanceResult(
                    status="advanced",
                    prompt=_build_decision_prompt(updated_session),
                )

            if selected_option.outcome is None:
                return ExplorationChoiceAdvanceResult(status="missing")

            approach = get_explore_approach(session.approach)
            outcome = selected_option.outcome
            xp_gained = _resolve_outcome_xp(approach, outcome.xp_profile)
            player, levels_gained = await _apply_xp_gain(connection, user_id, xp_gained)
            await delete_pending_choice(connection, user_id)

            exploration = session.to_active_exploration()
            resolution = ExplorationResolution(
                exploration=exploration,
                player=player,
                event_type=outcome.event_type,
                title=outcome.title,
                description=_format_text(
                    outcome.description,
                    approach=approach,
                    location_name=get_location_definition(session.location).name,
                ),
                xp_gained=xp_gained,
                levels_gained=levels_gained,
                combat_outcome=outcome.combat_outcome,
            )
            return ExplorationChoiceAdvanceResult(status="resolved", resolution=resolution)


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


async def post_exploration_choice_prompt(
    bot: "BleachBot",
    prompt: ExplorationDecisionPrompt,
) -> None:
    from src.ui.exploration_choice_view import ExplorationChoiceView, build_exploration_choice_embed

    async def _clear_pending_choice() -> None:
        if bot.db_pool is None:
            return

        async with bot.db_pool.acquire() as connection:
            async with connection.transaction():
                await delete_pending_choice(connection, prompt.session.user_id)

    channel = bot.get_channel(prompt.session.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(prompt.session.channel_id)
        except discord.HTTPException:
            logging.exception(
                "Could not fetch channel %s for exploration choice.",
                prompt.session.channel_id,
            )
            await _clear_pending_choice()
            return

    if not hasattr(channel, "send"):
        logging.warning("Channel %s is not messageable for exploration choice.", prompt.session.channel_id)
        await _clear_pending_choice()
        return

    view = ExplorationChoiceView(bot, prompt)
    embed = build_exploration_choice_embed(prompt)
    try:
        message = await channel.send(
            content=f"<@{prompt.session.user_id}>",
            embed=embed,
            view=view,
        )
    except discord.HTTPException:
        logging.exception("Failed to send exploration choice prompt for user %s.", prompt.session.user_id)
        await _clear_pending_choice()
        return

    if bot.db_pool is None:
        return

    async with bot.db_pool.acquire() as connection:
        async with connection.transaction():
            session_record = await fetch_pending_choice_record(connection, prompt.session.user_id, for_update=True)
            if session_record is None:
                return

            await update_pending_choice(
                connection,
                prompt.session.user_id,
                {"message_id": message.id},
            )


async def resolve_and_post_exploration(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
) -> ExplorationPostResult | None:
    post_result = await resolve_exploration(bot.db_pool, user_id, force=force)
    if post_result is None:
        return None

    if post_result.status == "instant" and post_result.resolution is not None:
        await post_exploration_result(bot, post_result.resolution)
    elif post_result.status == "choice_prompt" and post_result.prompt is not None:
        await post_exploration_choice_prompt(bot, post_result.prompt)

    return post_result


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

    bot.exploration_tasks[exploration.user_id] = asyncio.create_task(_run_exploration_task(bot, exploration))


async def restore_exploration_tasks(bot: "BleachBot") -> None:
    active_explorations = await list_active_explorations(bot.db_pool)
    for exploration in active_explorations:
        schedule_exploration_task(bot, exploration)


def get_exploration_remaining_time(exploration: ActiveExploration) -> str:
    return format_remaining_duration(exploration.end_time)
