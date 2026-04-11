from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.craft_service import craft_item, list_craft_recipes
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


CRAFT_RECIPE_CHOICES = [
    app_commands.Choice(name=recipe.label, value=recipe.key)
    for recipe in list_craft_recipes()
]


def _build_craft_unavailable_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Crafting Unavailable",
        description="The district ledger is out of reach right now. Give it a moment and try again.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    return embed


def _build_craft_missing_profile_embed() -> discord.Embed:
    embed = discord.Embed(
        title="No Soul Record Found",
        description="Use `/start` before trying to turn scraps into something worth carrying.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    return embed


def _build_missing_ingredients_embed(*, result) -> discord.Embed:
    recipe = result.recipe
    ingredient = result.ingredient_item
    output = result.output_item
    embed = discord.Embed(
        title=f"Cannot Craft {output.name if output is not None else 'Item'}",
        description="You do not have enough materials for that recipe yet.",
        color=get_explore_color("flavor"),
    )
    if recipe is not None and ingredient is not None and output is not None:
        embed.add_field(
            name="Recipe",
            value=build_explore_info_lines(
                f"Output: {output.name} x{recipe.output_quantity}",
                f"Needs: {ingredient.name} x{recipe.ingredient_quantity}",
                f"Owned: {result.ingredient_owned}",
            ),
            inline=False,
        )
    add_explore_divider(embed)
    return embed


def _build_craft_success_embed(*, result) -> discord.Embed:
    recipe = result.recipe
    ingredient = result.ingredient_item
    output = result.output_item
    embed = discord.Embed(
        title=f"{output.name if output is not None else 'Item'} Crafted",
        description="You sort the salvage, tie it down, and turn loose scraps into something you can actually use.",
        color=get_explore_color("reward"),
    )
    if recipe is not None and ingredient is not None and output is not None:
        embed.add_field(
            name="Recipe Result",
            value=build_explore_info_lines(
                f"Created: {output.name} x{recipe.output_quantity}",
                f"Spent: {ingredient.name} x{recipe.ingredient_quantity}",
                f"{ingredient.name} Left: {result.ingredient_remaining}",
            ),
            inline=False,
        )
    add_explore_divider(embed)
    return embed


def register_craft_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="craft", description="Turn salvage into simple supplies.")
    @app_commands.guild_only()
    @app_commands.choices(recipe=CRAFT_RECIPE_CHOICES)
    async def craft(
        interaction: discord.Interaction,
        recipe: app_commands.Choice[str],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                embed=_build_craft_unavailable_embed(),
                ephemeral=True,
            )
            return

        result = await craft_item(
            bot.db_pool,
            user_id=interaction.user.id,
            recipe_key=recipe.value,
        )

        if result.status == "missing_profile":
            await interaction.response.send_message(
                embed=_build_craft_missing_profile_embed(),
                ephemeral=True,
            )
            return

        if result.status in {"invalid_recipe", "missing_ingredients"}:
            await interaction.response.send_message(
                embed=_build_missing_ingredients_embed(result=result),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=_build_craft_success_embed(result=result),
            ephemeral=True,
        )
