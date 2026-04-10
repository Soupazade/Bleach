from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.inventory_service import list_player_inventory
from src.services.player_service import get_player_profile
from src.ui.inventory_view import (
    build_inventory_embed,
    build_inventory_missing_embed,
    build_inventory_unavailable_embed,
)

if TYPE_CHECKING:
    from src.main import BleachBot


def register_inventory_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="inventory", description="View the items currently stored in your inventory.")
    @app_commands.guild_only()
    async def inventory(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                embed=build_inventory_unavailable_embed(),
                ephemeral=True,
            )
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(
                embed=build_inventory_missing_embed(),
                ephemeral=True,
            )
            return

        items = await list_player_inventory(bot.db_pool, interaction.user.id)
        await interaction.response.send_message(
            embed=build_inventory_embed(
                player=player,
                discord_user=interaction.user,
                items=items,
            ),
            ephemeral=True,
        )
