from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.data.training import TRAINING_YARD_LOCATION_KEY
from src.services.combat_service import get_active_exploration_combat
from src.services.exploration_service import (
    get_active_exploration,
    get_pending_exploration_prompt,
    resolve_and_post_exploration,
)
from src.services.location_service import channel_matches_location
from src.services.player_service import build_resting_block_message, get_player_profile, get_rest_status
from src.services.status_service import is_player_wounded
from src.services.training_service import (
    get_active_training,
    resolve_and_post_training,
)
from src.services.travel_service import get_active_travel, resolve_and_post_travel
from src.ui.exploration_combat_view import build_active_combat_embed
from src.ui.explore_view import build_explore_resolution_posted_embed
from src.ui.train_view import (
    TrainingInterruptView,
    TrainingSetupView,
    build_training_active_embed,
    build_training_blocked_embed,
    build_training_location_required_embed,
    build_training_menu_embed,
    build_training_missing_profile_embed,
    build_training_resolution_posted_embed,
    build_training_resting_embed,
    build_training_wounded_embed,
    build_training_wrong_room_embed,
)
from src.ui.travel_view import build_travel_active_embed, build_travel_resolution_posted_embed

if TYPE_CHECKING:
    from src.main import BleachBot


def register_train_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="train", description="Begin a timed training session in the training yard.")
    @app_commands.guild_only()
    async def train(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                embed=build_training_blocked_embed(
                    "🏋 Training Is Unavailable",
                    "The soul records are out of reach right now, so nobody is getting proper work in.",
                    kind="combat",
                ),
            )
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(embed=build_training_missing_profile_embed())
            return

        now = datetime.now(timezone.utc)
        active_training = await get_active_training(bot.db_pool, interaction.user.id)
        if active_training is not None:
            if active_training.end_time > now:
                view = TrainingInterruptView(
                    bot=bot,
                    owner_id=interaction.user.id,
                    player=player,
                    training=active_training,
                )
                await interaction.response.send_message(
                    embed=build_training_active_embed(player, active_training),
                    view=view,
                )
                view.message = await interaction.original_response()
                return

            resolution = await resolve_and_post_training(bot, interaction.user.id)
            await interaction.response.send_message(
                embed=build_training_resolution_posted_embed() if resolution is not None else build_training_blocked_embed(
                    "🏋 Training Resolution Failed",
                    "That session should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
            )
            return

        if player.location != TRAINING_YARD_LOCATION_KEY:
            await interaction.response.send_message(
                embed=build_training_location_required_embed(player),
            )
            return

        if not channel_matches_location(player.location_data, interaction.channel):
            await interaction.response.send_message(
                embed=build_training_wrong_room_embed(),
            )
            return

        if player.is_resting:
            rest_status = get_rest_status(player)
            await interaction.response.send_message(
                embed=build_training_resting_embed(
                    build_resting_block_message(player, rest_status)
                ),
            )
            return

        if await is_player_wounded(bot.db_pool, interaction.user.id):
            await interaction.response.send_message(
                embed=build_training_wounded_embed(),
            )
            return

        pending_prompt = await get_pending_exploration_prompt(bot.db_pool, interaction.user.id)
        if pending_prompt is not None:
            await interaction.response.send_message(
                embed=build_training_blocked_embed(
                    "🏋 A Street Decision Is Still Waiting",
                    "Settle the last choice hanging over your run before you try to train.",
                    kind="choice",
                ),
            )
            return

        active_combat = await get_active_exploration_combat(bot.db_pool, interaction.user.id)
        if active_combat is not None:
            await interaction.response.send_message(
                embed=build_active_combat_embed(active_combat, interaction.user),
            )
            return

        active_exploration = await get_active_exploration(bot.db_pool, interaction.user.id)
        if active_exploration is not None:
            if active_exploration.end_time > now:
                await interaction.response.send_message(
                    embed=build_training_blocked_embed(
                        "🏋 You Are Already Out There",
                        "Finish the exploration you already committed to before you try to train.",
                        kind="explore",
                    ),
                )
                return

            resolution = await resolve_and_post_exploration(bot, interaction.user.id)
            await interaction.response.send_message(
                embed=build_explore_resolution_posted_embed(resolution.status) if resolution is not None else build_training_blocked_embed(
                    "🏋 Previous Exploration Is Still Tangled",
                    "That run should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
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
            await interaction.response.send_message(
                embed=build_travel_resolution_posted_embed(resolution) if resolution is not None else build_training_blocked_embed(
                    "🏋 Travel Resolution Failed",
                    "The trip ended, but I could not settle the arrival cleanly just yet.",
                    kind="combat",
                ),
            )
            return

        view = TrainingSetupView(bot=bot, owner_id=interaction.user.id, player=player)
        await interaction.response.send_message(
            embed=build_training_menu_embed(player),
            view=view,
        )
        view.message = await interaction.original_response()
