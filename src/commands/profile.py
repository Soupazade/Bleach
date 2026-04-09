from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.player_service import get_player_profile
from src.ui.profile_view import (
    ProfileView,
    build_profile_embed,
    build_profile_missing_embed,
    build_profile_unavailable_embed,
)

if TYPE_CHECKING:
    from src.main import BleachBot


def register_profile_command(bot: "BleachBot") -> None:
    async def _open_profile(interaction: discord.Interaction, *, initial_page: str) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(embed=build_profile_unavailable_embed(), ephemeral=True)
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(embed=build_profile_missing_embed(), ephemeral=True)
            return

        view = ProfileView(
            db_pool=bot.db_pool,
            owner_id=interaction.user.id,
            player=player,
            discord_user=interaction.user,
            initial_page=initial_page,
        )
        embed = build_profile_embed(player, interaction.user, initial_page)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @bot.tree.command(name="profile", description="View your Bleach RPG profile.")
    @app_commands.guild_only()
    async def profile(interaction: discord.Interaction) -> None:
        await _open_profile(interaction, initial_page="overview")

    @bot.tree.command(name="stats", description="Jump straight to the stats page of your Soul Record.")
    @app_commands.guild_only()
    async def stats(interaction: discord.Interaction) -> None:
        await _open_profile(interaction, initial_page="stats")
