from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.player_service import get_player_profile
from src.ui.profile_view import ProfileView, build_profile_embed

if TYPE_CHECKING:
    from src.main import BleachBot


def register_profile_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="profile", description="View your Bleach RPG profile.")
    @app_commands.guild_only()
    async def profile(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                "The database is not connected right now, so profiles are unavailable.",
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

        view = ProfileView(
            owner_id=interaction.user.id,
            player=player,
            discord_user=interaction.user,
        )
        embed = build_profile_embed(player, interaction.user, "overview")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()
