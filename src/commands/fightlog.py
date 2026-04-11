from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.commands.checks import require_staff_rank
from src.services.combat.repository import get_fight_log
from src.services.combat_service import build_fight_log_file
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


def register_fightlog_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="fightlog", description="Fetch a detailed combat log by fight log ID.")
    @app_commands.guild_only()
    @require_staff_rank("mod")
    async def fightlog(
        interaction: discord.Interaction,
        fight_log_id: app_commands.Range[int, 1],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                "The database is unavailable right now.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        record = await get_fight_log(bot.db_pool, fight_log_id)
        if record is None:
            await interaction.followup.send(
                f"No fight log with ID `{fight_log_id}` was found.",
                ephemeral=True,
            )
            return

        built_file = await build_fight_log_file(bot.db_pool, fight_log_id)
        if built_file is None:
            await interaction.followup.send(
                f"The fight log `{fight_log_id}` could not be built.",
                ephemeral=True,
            )
            return

        filename, payload = built_file
        embed = discord.Embed(
            title=f"Fight Log {record.fight_log_id}",
            description="Detailed combat trace attached for review.",
            color=get_explore_color("combat"),
        )
        embed.add_field(
            name="Summary",
            value=build_explore_info_lines(
                f"Fight ID: **{record.fight_id}**",
                f"User ID: **{record.user_id}**",
                f"Source: **{record.source_kind}**",
                f"Outcome: **{record.outcome or 'active'}**",
                f"Turns Logged: **{len(record.turn_payloads)}**",
            ),
            inline=False,
        )
        add_explore_divider(embed)
        await interaction.followup.send(
            embed=embed,
            file=discord.File(payload, filename=filename),
            ephemeral=True,
        )
