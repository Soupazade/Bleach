from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.data.training import TRAINING_YARD_LOCATION_KEY
from src.services.location_service import channel_matches_location
from src.services.combat_service import get_active_exploration_combat
from src.services.exploration_service import (
    get_active_exploration,
    get_pending_exploration_prompt,
    resolve_and_post_exploration,
)
from src.services.player_service import build_resting_block_message, get_player_profile, get_rest_status
from src.services.training_service import get_active_training, resolve_and_post_training
from src.services.travel_service import get_active_travel, resolve_and_post_travel
from src.services.work_service import get_active_work, resolve_and_post_work
from src.ui.explore_view import (
    ExploreView,
    build_explore_active_embed,
    build_explore_menu_embed,
    build_explore_pending_embed,
    build_explore_resolution_posted_embed,
    build_explore_resting_embed,
    build_explore_training_yard_embed,
    build_explore_wrong_location_embed,
)
from src.ui.exploration_combat_view import build_active_combat_embed
from src.ui.train_view import build_training_active_embed, build_training_resolution_posted_embed
from src.ui.travel_view import (
    build_travel_active_embed,
    build_travel_blocked_embed,
    build_travel_resolution_posted_embed,
)
from src.ui.work_view import build_work_active_embed, build_work_resolution_posted_embed

if TYPE_CHECKING:
    from src.main import BleachBot


def register_explore_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="explore", description="Begin a timed exploration in your current district.")
    @app_commands.guild_only()
    async def explore(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                "The database is not connected right now, so exploration is unavailable.",
            )
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(
                "You don't have a profile yet. Use /start first.",
            )
            return

        if not channel_matches_location(player.location_data, interaction.channel):
            await interaction.response.send_message(
                embed=build_explore_wrong_location_embed(player),
            )
            return

        if player.location == TRAINING_YARD_LOCATION_KEY:
            await interaction.response.send_message(
                embed=build_explore_training_yard_embed(player),
            )
            return

        if player.is_resting:
            rest_status = get_rest_status(player)
            embed = build_explore_resting_embed(
                build_resting_block_message(player, rest_status)
            )
            await interaction.response.send_message(embed=embed)
            return

        pending_prompt = await get_pending_exploration_prompt(bot.db_pool, interaction.user.id)
        if pending_prompt is not None:
            embed = build_explore_pending_embed(
                pending_prompt.event_title,
                pending_prompt.step_number,
                pending_prompt.total_steps,
                pending_prompt.session.channel_id,
            )
            await interaction.response.send_message(embed=embed)
            return

        active_combat = await get_active_exploration_combat(bot.db_pool, interaction.user.id)
        if active_combat is not None:
            await interaction.response.send_message(
                embed=build_active_combat_embed(active_combat, interaction.user),
            )
            return

        now = datetime.now(timezone.utc)
        active_work = await get_active_work(bot.db_pool, interaction.user.id)
        if active_work is not None:
            if active_work.end_time > now:
                await interaction.response.send_message(
                    embed=build_work_active_embed(player, active_work),
                )
                return

            resolution = await resolve_and_post_work(bot, interaction.user.id)
            if resolution is None:
                await interaction.response.send_message(
                    embed=build_travel_blocked_embed(
                        "Work Is Still Tangled",
                        "That shift should have been over by now, but I could not settle it cleanly just yet.",
                        kind="combat",
                    ),
                )
                return

            await interaction.response.send_message(
                embed=build_work_resolution_posted_embed(),
            )
            return

        active_training = await get_active_training(bot.db_pool, interaction.user.id)
        if active_training is not None:
            if active_training.end_time > now:
                await interaction.response.send_message(
                    embed=build_training_active_embed(player, active_training),
                )
                return

            resolution = await resolve_and_post_training(bot, interaction.user.id)
            if resolution is None:
                await interaction.response.send_message(
                    embed=build_travel_blocked_embed(
                        "🏋 Training Is Still Tangled",
                        "That session should have been over by now, but I could not settle it cleanly just yet.",
                        kind="combat",
                    ),
                )
                return

            await interaction.response.send_message(
                embed=build_training_resolution_posted_embed(),
            )
            return

        active_travel = await get_active_travel(bot.db_pool, interaction.user.id)
        if active_travel is not None:
            if active_travel.end_time > now:
                await interaction.response.send_message(
                    embed=build_travel_active_embed(player, active_travel),
                )
                return

            resolution = await resolve_and_post_travel(bot, interaction.user.id)
            if resolution is None:
                await interaction.response.send_message(
                    embed=build_travel_blocked_embed(
                        "🧭 Travel Is Still Tangled",
                        "The road should have been done with you by now, but I could not settle the arrival cleanly just yet.",
                        kind="combat",
                    ),
                )
                return

            await interaction.response.send_message(
                embed=build_travel_resolution_posted_embed(resolution),
            )
            return

        active_exploration = await get_active_exploration(bot.db_pool, interaction.user.id)
        if active_exploration is not None:
            if active_exploration.end_time > now:
                await interaction.response.send_message(
                    embed=build_explore_active_embed(player, active_exploration),
                )
                return

            resolution = await resolve_and_post_exploration(bot, interaction.user.id)
            if resolution is None:
                await interaction.response.send_message(
                    "Your previous exploration could not be resolved right now. Please try again.",
                )
                return

            await interaction.response.send_message(
                embed=build_explore_resolution_posted_embed(resolution.status),
            )
            return

        view = ExploreView(bot=bot, owner_id=interaction.user.id, player=player)
        embed = build_explore_menu_embed(player)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
