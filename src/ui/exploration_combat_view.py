from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.services.combat.abilities import list_unlocked_player_abilities
from src.services.combat_service import (
    get_active_exploration_combat_by_message,
    resolve_and_post_combat_action,
)
from src.services.combat.types import CombatSession
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot
    from src.models.player import PlayerProfile


def _apply_combat_identity(
    embed: discord.Embed,
    discord_user: discord.abc.User | None,
) -> None:
    if discord_user is None:
        return
    embed.set_author(
        name=discord_user.display_name,
        icon_url=discord_user.display_avatar.url,
    )
    embed.set_thumbnail(url=discord_user.display_avatar.url)


def _format_enemy_lines(combat: CombatSession) -> str:
    return "\n".join(
        build_explore_info_lines(
            f"Name: **{enemy.name}**",
            f"Level: **{enemy.level}**",
            f"HP: **{enemy.hp_current}/{enemy.hp_max}**",
            f"Power: **{enemy.power}** | Defense: **{enemy.defense}** | Speed: **{enemy.speed}** | Reiatsu: **{enemy.reiatsu}**",
        )
        for enemy in combat.enemies
        if enemy.is_alive
    )


def _format_ability_lines(combat: CombatSession) -> str:
    abilities = list_unlocked_player_abilities(combat.player.level)
    if not abilities:
        return "No unlocked abilities yet. Reach **level 2** to unlock **Heavy Strike**."
    lines: list[str] = []
    for ability in abilities:
        cooldown = combat.player.cooldowns.get(ability.key, 0)
        cooldown_text = f"CD: {cooldown}T" if cooldown > 0 else "Ready"
        lines.append(
            f"**{ability.name}** | Cost: **{ability.mana_cost}** | {cooldown_text} | Unlock: **Lv {ability.unlock_level}**"
        )
    return "\n".join(lines)


def build_exploration_combat_embed(
    combat: CombatSession,
    discord_user: discord.abc.User | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔ {combat.encounter_title}",
        description=combat.encounter_description,
        color=get_explore_color("combat"),
    )
    _apply_combat_identity(embed, discord_user)
    player_name = discord_user.display_name if discord_user is not None else "You"
    embed.add_field(
        name=player_name,
        value=build_explore_info_lines(
            f"Race: **{combat.player.race}**",
            f"Rank: **{combat.player.rank}**",
            f"Level: **{combat.player.level}**",
            f"HP: **{combat.player.hp_current}/{combat.player.hp_max}**",
            f"Mana: **{combat.player.mana_current}/{combat.player.mana_max}**",
            f"Power: **{combat.player.power}** | Defense: **{combat.player.defense}** | Speed: **{combat.player.speed}** | Reiatsu: **{combat.player.reiatsu}**",
        ),
        inline=False,
    )
    embed.add_field(
        name="Enemies",
        value=_format_enemy_lines(combat),
        inline=False,
    )
    embed.add_field(
        name="Battle State",
        value=build_explore_info_lines(
            f"Fight Log ID: **{combat.fight_log_id}**",
            f"Round: **{combat.round_number}**",
            f"AFK Skips: **{combat.afk_skips}/3**",
            f"Turn Ends: {discord.utils.format_dt(combat.turn_deadline_at, 'R')}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Abilities",
        value=_format_ability_lines(combat),
        inline=False,
    )
    embed.add_field(
        name="Turn Log",
        value=combat.last_round_summary or "The next exchange is still waiting on your move.",
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Strike is reliable. Guard softens the hit and can counter. Retreat gambles on speed. Abilities spend mana.")
    return embed


def build_active_combat_embed(
    combat: CombatSession,
    discord_user: discord.abc.User | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title="⚔ A Fight Is Already Live",
        description=(
            f"You are already in combat against **{combat.enemy_name}**.\n"
            f"Channel: <#{combat.channel_id}>"
        ),
        color=get_explore_color("combat"),
    )
    _apply_combat_identity(embed, discord_user)
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"Race: **{combat.player.race}**",
            f"Rank: **{combat.player.rank}**",
            f"Level: **{combat.player.level}**",
            f"HP: **{combat.player.hp_current}/{combat.player.hp_max}**",
            f"Mana: **{combat.player.mana_current}/{combat.player.mana_max}**",
            f"Round: **{combat.round_number}**",
            f"Fight Log ID: **{combat.fight_log_id}**",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_fight_result_embed(
    *,
    combat: CombatSession,
    player: "PlayerProfile",
    outcome: str,
    title: str,
    description: str,
) -> discord.Embed:
    color_key = "reward" if outcome == "victory" else "combat"
    final_title = "⚔ Victory" if outcome == "victory" else "⚔ Defeat"
    if outcome == "retreated":
        final_title = "⚔ Retreat"
    if outcome == "afk_defeat":
        final_title = "⚔ Defeat - AFK"
    embed = discord.Embed(
        title=final_title,
        description=description,
        color=get_explore_color(color_key),
    )
    embed.add_field(
        name="Result",
        value=build_explore_info_lines(
            f"Fight: **{title}**",
            f"Fight Log ID: **{combat.fight_log_id}**",
            f"HP After: **{player.hp_current}/{player.hp_max}**",
            f"Mana After: **{player.mana_current}/{player.mana_max}**",
            f"Location: **{player.location_data.name}**",
        ),
        inline=False,
    )
    if outcome in {"defeat", "afk_defeat"}:
        embed.add_field(
            name="Aftermath",
            value="You black out, wake in **Rukongai Streets**, and carry **Wounded** for **30 minutes**.",
            inline=False,
        )
    add_explore_divider(embed)
    return embed


class AbilitySelect(discord.ui.Select["ExplorationCombatView"]):
    def __init__(self, combat: CombatSession) -> None:
        abilities = list_unlocked_player_abilities(combat.player.level)
        if not abilities:
            options = [
                discord.SelectOption(
                    label="No unlocked abilities",
                    value="locked",
                    description="Reach level 2 to start testing abilities.",
                )
            ]
            disabled = True
        else:
            options = []
            for ability in abilities:
                cooldown = combat.player.cooldowns.get(ability.key, 0)
                description = f"Cost {ability.mana_cost} mana | CD {ability.cooldown_turns}T"
                if cooldown > 0:
                    description = f"Cooling down: {cooldown}T left"
                options.append(
                    discord.SelectOption(
                        label=ability.name,
                        value=ability.key,
                        description=description[:100],
                    )
                )
            disabled = False

        super().__init__(
            placeholder="Choose an ability",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="combat:ability_select",
            disabled=disabled,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None or self.values[0] == "locked":
            return
        await self.view.handle_action(interaction, "ability", ability_key=self.values[0])


class ExplorationCombatView(discord.ui.View):
    def __init__(self, bot: "BleachBot", combat: CombatSession) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.combat = combat
        self.add_item(AbilitySelect(combat))

    async def handle_action(
        self,
        interaction: discord.Interaction,
        action: str,
        *,
        ability_key: str | None = None,
    ) -> None:
        if interaction.message is None:
            await interaction.response.send_message("That fight is no longer active.", ephemeral=True)
            return

        combat = await get_active_exploration_combat_by_message(self.bot.db_pool, interaction.message.id)
        if combat is None:
            await interaction.response.send_message("That fight is already settled.", ephemeral=True)
            return

        if combat.user_id != interaction.user.id:
            await interaction.response.send_message("That fight belongs to someone else.", ephemeral=True)
            return

        await interaction.response.defer()
        await resolve_and_post_combat_action(
            self.bot,
            message_id=interaction.message.id,
            user_id=interaction.user.id,
            action=action,  # type: ignore[arg-type]
            ability_key=ability_key,
            old_message=interaction.message,
        )

    @discord.ui.button(
        label="Strike",
        style=discord.ButtonStyle.danger,
        custom_id="combat:strike",
        row=0,
    )
    async def strike(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.handle_action(interaction, "strike")

    @discord.ui.button(
        label="Guard",
        style=discord.ButtonStyle.primary,
        custom_id="combat:guard",
        row=0,
    )
    async def guard(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.handle_action(interaction, "guard")

    @discord.ui.button(
        label="Retreat",
        style=discord.ButtonStyle.secondary,
        custom_id="combat:retreat",
        row=0,
    )
    async def retreat(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.handle_action(interaction, "retreat")
