from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.data.exploration import get_random_explore_options_for_location
from src.services.exploration_service import get_active_exploration, resolve_and_post_exploration
from src.services.player_service import build_resting_block_message, get_player_profile, get_rest_status
from src.ui.explore_view import ExploreView, build_explore_active_embed, build_explore_menu_embed

if TYPE_CHECKING:
    from src.main import BleachBot


def register_explore_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="explore", description="Begin a timed exploration in your current district.")
    @app_commands.guild_only()
    async def explore(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                "The database is not connected right now, so exploration is unavailable.",
                ephemeral=True,
            )
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(
                "You don't have a profile yet. Use /start first.",
                ephemeral=True,
            )
            return

        if player.is_resting:
            rest_minutes, recovered_stamina = get_rest_status(player)
            embed = discord.Embed(
                title="You Are Resting",
                description=build_resting_block_message(player, rest_minutes, recovered_stamina),
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        active_exploration = await get_active_exploration(bot.db_pool, interaction.user.id)
        now = datetime.now(timezone.utc)
        if active_exploration is not None:
            if active_exploration.end_time > now:
                await interaction.response.send_message(
                    embed=build_explore_active_embed(active_exploration),
                    ephemeral=True,
                )
                return

            resolution = await resolve_and_post_exploration(bot, interaction.user.id)
            if resolution is None:
                await interaction.response.send_message(
                    "Your previous exploration could not be resolved right now. Please try again.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Previous Exploration Resolved",
                    description="Your previous patrol had already finished, so I posted the result in the channel.",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
            return

        approaches = get_random_explore_options_for_location(player.location)
        view = ExploreView(bot=bot, owner_id=interaction.user.id, player=player, approaches=approaches)
        embed = build_explore_menu_embed(player)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()
