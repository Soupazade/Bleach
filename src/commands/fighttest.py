from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.combat_service import post_combat_prompt, start_fight_test
from src.ui.explore_embed_style import add_explore_divider, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


def _build_fighttest_embed(title: str, description: str, *, kind: str = "choice") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color(kind),
    )
    add_explore_divider(embed)
    return embed


def register_fighttest_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="fighttest", description="Start a test fight against a generic bandit.")
    @app_commands.guild_only()
    async def fighttest(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                embed=_build_fighttest_embed(
                    "Fight Test Unavailable",
                    "The combat records are not reachable right now.",
                    kind="combat",
                ),
                ephemeral=True,
            )
            return

        if interaction.channel_id is None:
            await interaction.response.send_message(
                embed=_build_fighttest_embed(
                    "Fight Test Failed",
                    "I could not determine which channel to use for the fight.",
                    kind="combat",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        result = await start_fight_test(
            bot.db_pool,
            user_id=interaction.user.id,
            channel_id=interaction.channel_id,
        )

        if result.status == "started" and result.combat is not None:
            await post_combat_prompt(bot, result.combat)
            await interaction.followup.send(
                embed=_build_fighttest_embed(
                    "Fight Test Started",
                    "The combat prompt has been posted in this channel.",
                    kind="combat",
                ),
                ephemeral=True,
            )
            return

        if result.status == "resting":
            await interaction.followup.send(
                embed=_build_fighttest_embed(
                    "Fight Test Blocked",
                    "You are resting right now. Finish that first.",
                    kind="combat",
                ),
                ephemeral=True,
            )
            return

        if result.status == "active_combat":
            await interaction.followup.send(
                embed=_build_fighttest_embed(
                    "Fight Test Blocked",
                    "You already have a live fight running.",
                    kind="combat",
                ),
                ephemeral=True,
            )
            return

        if result.status == "busy":
            await interaction.followup.send(
                embed=_build_fighttest_embed(
                    "Fight Test Blocked",
                    result.reason or "You are already committed to another timed action.",
                    kind="combat",
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=_build_fighttest_embed(
                "Fight Test Failed",
                "You need a profile before you can start a fight test.",
                kind="combat",
            ),
            ephemeral=True,
        )
