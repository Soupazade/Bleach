from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.data.exploration import get_random_explore_options_for_location
from src.services.combat_service import get_active_exploration_combat
from src.services.exploration_service import (
    get_active_exploration,
    get_pending_exploration_prompt,
    resolve_and_post_exploration,
)
from src.services.player_service import build_resting_block_message, get_player_profile, get_rest_status
from src.ui.explore_view import (
    ExploreView,
    build_explore_active_embed,
    build_explore_menu_embed,
    build_explore_pending_embed,
    build_explore_resolution_posted_embed,
    build_explore_resting_embed,
    build_explore_wrong_location_embed,
)
from src.ui.exploration_combat_view import build_active_combat_embed

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

        if interaction.channel_id != player.location_data.room_id:
            await interaction.response.send_message(
                embed=build_explore_wrong_location_embed(player),
                ephemeral=True,
            )
            return

        if player.is_resting:
            rest_minutes, recovered_stamina = get_rest_status(player)
            embed = build_explore_resting_embed(
                build_resting_block_message(player, rest_minutes, recovered_stamina)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        pending_prompt = await get_pending_exploration_prompt(bot.db_pool, interaction.user.id)
        if pending_prompt is not None:
            embed = build_explore_pending_embed(
                pending_prompt.event_title,
                pending_prompt.step_number,
                pending_prompt.total_steps,
                pending_prompt.session.channel_id,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        active_combat = await get_active_exploration_combat(bot.db_pool, interaction.user.id)
        if active_combat is not None:
            await interaction.response.send_message(
                embed=build_active_combat_embed(active_combat, interaction.user),
                ephemeral=True,
            )
            return

        active_exploration = await get_active_exploration(bot.db_pool, interaction.user.id)
        now = datetime.now(timezone.utc)
        if active_exploration is not None:
            if active_exploration.end_time > now:
                await interaction.response.send_message(
                    embed=build_explore_active_embed(player, active_exploration),
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
                embed=build_explore_resolution_posted_embed(resolution.status),
                ephemeral=True,
            )
            return

        approaches = get_random_explore_options_for_location(player.location)
        view = ExploreView(bot=bot, owner_id=interaction.user.id, player=player, approaches=approaches)
        embed = build_explore_menu_embed(player)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()
