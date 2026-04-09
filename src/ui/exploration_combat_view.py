from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.services.exploration_service import (
    advance_exploration_combat,
    build_exploration_result_embed,
)
from src.services.combat_service import get_active_exploration_combat_by_message

if TYPE_CHECKING:
    from src.main import BleachBot
    from src.models.combat import ActiveExplorationCombat


def build_exploration_combat_embed(combat: "ActiveExplorationCombat") -> discord.Embed:
    embed = discord.Embed(
        title=f"Combat | {combat.encounter_title}",
        description=combat.encounter_description,
        color=discord.Color.dark_red(),
    )
    embed.add_field(
        name="You",
        value=(
            f"HP: **{combat.player_hp_current}/{combat.player_hp_max}**\n"
            f"Mana: **{combat.player_mana_current}/{combat.player_mana_max}**\n"
            f"Power: **{combat.player_power}** | Defense: **{combat.player_defense}**\n"
            f"Speed: **{combat.player_speed}** | Reiatsu: **{combat.player_reiatsu}**"
        ),
        inline=True,
    )
    embed.add_field(
        name=combat.enemy_name,
        value=(
            f"HP: **{combat.enemy_hp_current}/{combat.enemy_hp_max}**\n"
            f"Power: **{combat.enemy_power}**\n"
            f"Defense: **{combat.enemy_defense}**\n"
            f"Speed: **{combat.enemy_speed}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Round",
        value=(
            f"**{combat.round_number}/4**\n"
            f"Focus Bonus: **+{combat.focus_bonus}**"
        ),
        inline=False,
    )
    embed.add_field(name="Last Exchange", value=combat.last_round_summary, inline=False)
    embed.set_footer(
        text="Attack presses the fight. Guard softens the next hit. Focus charges the next strike. Retreat gambles on speed."
    )
    return embed


def build_active_combat_embed(combat: "ActiveExplorationCombat") -> discord.Embed:
    embed = discord.Embed(
        title="You Are Already Fighting",
        description=(
            f"Your run in **{combat.encounter_title}** has already turned into a live fight.\n"
            f"Channel: <#{combat.channel_id}>"
        ),
        color=discord.Color.red(),
    )
    embed.add_field(
        name="Current State",
        value=(
            f"Enemy: **{combat.enemy_name}**\n"
            f"Round: **{combat.round_number}/4**\n"
            f"Your HP: **{combat.player_hp_current}/{combat.player_hp_max}**\n"
            f"Enemy HP: **{combat.enemy_hp_current}/{combat.enemy_hp_max}**"
        ),
        inline=False,
    )
    if combat.message_id is not None:
        embed.add_field(
            name="Fight Message",
            value=f"Message ID: **{combat.message_id}**",
            inline=False,
        )
    return embed


class ExplorationCombatView(discord.ui.View):
    def __init__(self, bot: "BleachBot") -> None:
        super().__init__(timeout=None)
        self.bot = bot

    async def _handle_action(self, interaction: discord.Interaction, action: str) -> None:
        if interaction.message is None:
            await interaction.response.send_message("That fight is no longer active.", ephemeral=True)
            return

        combat = await get_active_exploration_combat_by_message(self.bot.db_pool, interaction.message.id)
        if combat is None:
            await interaction.response.send_message(
                "That fight has already been settled.",
                ephemeral=True,
            )
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass
            return

        if combat.user_id != interaction.user.id:
            await interaction.response.send_message(
                "That fight belongs to someone else.",
                ephemeral=True,
            )
            return

        result = await advance_exploration_combat(
            self.bot.db_pool,
            message_id=interaction.message.id,
            user_id=interaction.user.id,
            action=action,
        )
        if result.status == "missing":
            await interaction.response.send_message(
                "I could not settle that combat turn right now.",
                ephemeral=True,
            )
            return

        if result.status == "updated" and result.combat is not None:
            await interaction.response.edit_message(
                embed=build_exploration_combat_embed(result.combat),
                view=self,
            )
            return

        if result.status == "resolved" and result.resolution is not None:
            await interaction.response.edit_message(
                embed=build_exploration_result_embed(result.resolution),
                view=None,
            )
            return

        await interaction.response.send_message(
            "I could not settle that combat turn right now.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Attack",
        style=discord.ButtonStyle.danger,
        custom_id="explore_combat:attack",
        row=0,
    )
    async def attack(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_action(interaction, "attack")

    @discord.ui.button(
        label="Guard",
        style=discord.ButtonStyle.primary,
        custom_id="explore_combat:guard",
        row=0,
    )
    async def guard(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_action(interaction, "guard")

    @discord.ui.button(
        label="Focus",
        style=discord.ButtonStyle.success,
        custom_id="explore_combat:focus",
        row=0,
    )
    async def focus(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_action(interaction, "focus")

    @discord.ui.button(
        label="Retreat",
        style=discord.ButtonStyle.secondary,
        custom_id="explore_combat:retreat",
        row=0,
    )
    async def retreat(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_action(interaction, "retreat")
