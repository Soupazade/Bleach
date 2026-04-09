from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.services.exploration_service import (
    advance_exploration_combat,
    build_exploration_result_embed,
)
from src.services.combat_service import get_active_exploration_combat_by_message
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot
    from src.models.combat import ActiveExplorationCombat


def build_exploration_combat_embed(combat: "ActiveExplorationCombat") -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️ {combat.encounter_title}",
        description=combat.encounter_description,
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Combatants",
        value=build_explore_info_lines(
            "You",
            f"❤️ HP: **{combat.player_hp_current}/{combat.player_hp_max}**",
            f"🔷 Mana: **{combat.player_mana_current}/{combat.player_mana_max}**",
            "",
            combat.enemy_name,
            f"❤️ HP: **{combat.enemy_hp_current}/{combat.enemy_hp_max}**",
        ),
        inline=True,
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"⚔ Round: **{combat.round_number}/4**",
            f"🌀 Focus Bonus: **+{combat.focus_bonus}**",
            f"🗡 Last Exchange: {combat.last_round_summary}",
        ),
        inline=True,
    )
    embed.add_field(
        name="What do you do?",
        value=build_explore_info_lines(
            "⚔ Attack",
            "🛡 Guard",
            "🌀 Focus",
            "🏃 Retreat",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(
        text="Attack presses the fight. Guard softens the next hit. Focus charges the next strike. Retreat gambles on speed."
    )
    return embed


def build_active_combat_embed(combat: "ActiveExplorationCombat") -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ The Fight Is Still Live",
        description=(
            f"Your run in **{combat.encounter_title}** has already turned into a live fight.\n"
            f"Channel: <#{combat.channel_id}>"
        ),
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"⚔ Enemy: **{combat.enemy_name}**",
            f"⏱ Round: **{combat.round_number}/4**",
            f"❤️ Your HP: **{combat.player_hp_current}/{combat.player_hp_max}**",
            f"❤️ Enemy HP: **{combat.enemy_hp_current}/{combat.enemy_hp_max}**",
        ),
        inline=False,
    )
    if combat.message_id is not None:
        embed.add_field(
            name="🕓 Fight Message",
            value=f"Message ID: **{combat.message_id}**",
            inline=False,
        )
    add_explore_divider(embed)
    return embed


def build_settled_combat_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ The Fight Is Already Over",
        description=(
            "That clash has already finished. The old combat panel lingered longer than it should have, "
            "so I closed it instead of leaving a live fight that is not live."
        ),
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            "⚔ Combat: Settled",
            "📘 Check the updated result message above if it landed cleanly.",
            "📘 If not, `/profile` will still reflect the outcome.",
        ),
        inline=False,
    )
    add_explore_divider(embed)
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
            cached_resolution = self.bot.recent_combat_resolutions.get(interaction.message.id)
            if cached_resolution is not None:
                await interaction.response.edit_message(
                    embed=build_exploration_result_embed(cached_resolution),
                    view=None,
                )
                return

            await interaction.response.edit_message(
                embed=build_settled_combat_embed(),
                view=None,
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
                view=ExplorationCombatView(self.bot),
            )
            return

        if result.status == "resolved" and result.resolution is not None:
            self.bot.recent_combat_resolutions[interaction.message.id] = result.resolution
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
