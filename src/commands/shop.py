from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.data.locations import RUKONGAI_MARKET
from src.services.location_service import channel_matches_location
from src.services.player_service import get_player_profile
from src.services.shop_service import get_shop_session_data
from src.ui.shop_view import (
    ShopView,
    build_shop_embed,
    build_shop_market_required_embed,
    build_shop_missing_profile_embed,
    build_shop_unavailable_embed,
)

if TYPE_CHECKING:
    from src.main import BleachBot


def register_shop_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="shop", description="Browse the market stalls and buy what you can afford.")
    @app_commands.guild_only()
    async def shop(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                embed=build_shop_unavailable_embed(),
                ephemeral=True,
            )
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(
                embed=build_shop_missing_profile_embed(),
                ephemeral=True,
            )
            return

        if player.location != RUKONGAI_MARKET.key or not channel_matches_location(RUKONGAI_MARKET, interaction.channel):
            await interaction.response.send_message(
                embed=build_shop_market_required_embed(player.location_data.name),
                ephemeral=True,
            )
            return

        session = await get_shop_session_data(bot.db_pool, interaction.user.id)
        if session is None:
            await interaction.response.send_message(
                embed=build_shop_unavailable_embed(),
                ephemeral=True,
            )
            return

        view = ShopView(bot=bot, owner_id=interaction.user.id, session=session)
        await interaction.response.send_message(
            embed=build_shop_embed(session),
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()
