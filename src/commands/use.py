from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.data.items import list_usable_items
from src.services.item_service import use_item
from src.ui.inventory_view import (
    build_item_use_blocked_embed,
    build_item_use_empty_embed,
    build_item_use_success_embed,
    build_item_use_unavailable_embed,
    build_inventory_missing_embed,
)

if TYPE_CHECKING:
    from src.main import BleachBot


USABLE_ITEM_CHOICES = [
    app_commands.Choice(name=item.name, value=item.key)
    for item in list_usable_items()
]


def register_use_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="use", description="Use an item from your inventory.")
    @app_commands.guild_only()
    @app_commands.choices(item=USABLE_ITEM_CHOICES)
    async def use(
        interaction: discord.Interaction,
        item: app_commands.Choice[str],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                embed=build_item_use_unavailable_embed(),
                ephemeral=True,
            )
            return

        result = await use_item(
            bot.db_pool,
            user_id=interaction.user.id,
            item_key=item.value,
        )

        if result.status == "used" and result.player is not None and result.item_definition is not None:
            await interaction.response.send_message(
                embed=build_item_use_success_embed(
                    player=result.player,
                    item_definition=result.item_definition,
                    healed_amount=result.healed_amount,
                    restored_stamina=result.restored_stamina,
                    quantity_remaining=result.quantity_remaining,
                ),
                ephemeral=True,
            )
            return

        if result.status == "active_combat":
            await interaction.response.send_message(
                embed=build_item_use_blocked_embed(
                    "🩹 No Time to Use That",
                    "You cannot stop to use supplies in the middle of a live fight. Finish the clash first.",
                    kind="combat",
                ),
                ephemeral=True,
            )
            return

        if result.status == "nothing_to_heal" and result.player is not None and result.item_definition is not None:
            await interaction.response.send_message(
                embed=build_item_use_empty_embed(
                    player=result.player,
                    item_definition=result.item_definition,
                    reason="Your HP is already full. There is no point wasting clean wraps right now.",
                ),
                ephemeral=True,
            )
            return

        if result.status == "nothing_to_restore" and result.player is not None and result.item_definition is not None:
            await interaction.response.send_message(
                embed=build_item_use_empty_embed(
                    player=result.player,
                    item_definition=result.item_definition,
                    reason="Your stamina is already full. Save the meal for when the streets actually wear you down.",
                ),
                ephemeral=True,
            )
            return

        if result.status == "missing_item" and result.player is not None and result.item_definition is not None:
            await interaction.response.send_message(
                embed=build_item_use_empty_embed(
                    player=result.player,
                    item_definition=result.item_definition,
                    reason="You do not have that item in your inventory yet.",
                ),
                ephemeral=True,
            )
            return

        if result.status == "missing_profile":
            await interaction.response.send_message(
                embed=build_inventory_missing_embed(),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=build_item_use_unavailable_embed(),
            ephemeral=True,
        )
