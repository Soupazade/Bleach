from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.quest_service import get_player_quest_board
from src.ui.quest_view import QuestBoardView

if TYPE_CHECKING:
    from src.main import BleachBot


def register_quest_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="quest", description="Review your active and available quests.")
    @app_commands.guild_only()
    async def quest(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                "The quest ledger is out of reach right now.",
                ephemeral=True,
            )
            return

        board = await get_player_quest_board(bot.db_pool, interaction.user.id)
        if board is None:
            await interaction.response.send_message(
                "Use `/start` first so your soul record exists before you check the quest board.",
                ephemeral=True,
            )
            return

        view = QuestBoardView(bot=bot, owner_id=interaction.user.id, board=board)
        await interaction.response.send_message(
            embed=view.build_current_embed(),
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()
