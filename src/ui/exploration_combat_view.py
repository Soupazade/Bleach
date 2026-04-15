from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.services.combat.abilities import list_unlocked_player_abilities
from src.services.combat_service import (
    get_active_exploration_combat,
    get_active_exploration_combat_by_message,
    resolve_and_post_combat_action,
)
from src.services.dungeon_service import get_active_dungeon_run
from src.services.combat.types import CombatSession
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot
    from src.models.player import PlayerProfile


BLEACH_QUOTES = (
    '"The difference in ability... what about it?"',
    '"Admiration is the state furthest from understanding."',
    '"If miracles only happen once, what are they called the second time?"',
    '"Fear is necessary for evolution."',
    '"Do not break anyone\'s heart. They only have one."',
    '"A battle is won in the space where resolve does not bend."',
)


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


def _quote_for_combat(combat: CombatSession) -> str:
    return BLEACH_QUOTES[(combat.round_number - 1) % len(BLEACH_QUOTES)]


def _footer_text(combat: CombatSession) -> str:
    return f"{_quote_for_combat(combat)} | Round {combat.round_number} | Fight Log ID {combat.fight_log_id}"


def _format_player_panel(combat: CombatSession) -> str:
    return build_explore_info_lines(
        f"Race: **{combat.player.race}**",
        f"Rank: **{combat.player.rank}**",
        f"Level: **{combat.player.level}**",
        f"HP: **{combat.player.hp_current}/{combat.player.hp_max}**",
        f"Mana: **{combat.player.mana_current}/{combat.player.mana_max}**",
    )


def _format_enemy_panel(combat: CombatSession) -> str:
    enemy = combat.primary_enemy
    return build_explore_info_lines(
        f"Race: **{enemy.race}**",
        f"Rank: **{enemy.rank}**",
        f"Level: **{enemy.level}**",
        f"HP: **{enemy.hp_current}/{enemy.hp_max}**",
        f"Mana: **{enemy.mana_current}/{enemy.mana_max}**",
    )


def build_exploration_combat_embed(
    combat: CombatSession,
    discord_user: discord.abc.User | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️ {combat.encounter_title}",
        description=combat.encounter_description,
        color=get_explore_color("combat"),
    )
    _apply_combat_identity(embed, discord_user)
    player_name = discord_user.display_name if discord_user is not None else "You"
    embed.add_field(name=f"🪽 {player_name}", value=_format_player_panel(combat), inline=True)
    embed.add_field(name=f"☠️ {combat.enemy_name}", value=_format_enemy_panel(combat), inline=True)
    embed.add_field(
        name="📜 Turn Log",
        value=combat.last_round_summary or "**Your Turn**\n- Waiting on your move.\n\n**Enemy Turn**\n- The enemy is reading you.",
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text=_footer_text(combat))
    return embed


def build_active_combat_embed(
    combat: CombatSession,
    discord_user: discord.abc.User | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ A Fight Is Already Live",
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
            f"Level: **{combat.player.level}**",
            f"HP: **{combat.player.hp_current}/{combat.player.hp_max}**",
            f"Mana: **{combat.player.mana_current}/{combat.player.mana_max}**",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text=_footer_text(combat))
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
    final_title = "🏆 Victory"
    if outcome == "retreated":
        final_title = "🏃 Retreat"
    elif outcome == "defeat":
        final_title = "☠️ Defeat"

    embed = discord.Embed(
        title=final_title,
        description=description,
        color=get_explore_color(color_key),
    )
    embed.add_field(
        name="Aftermath",
        value=build_explore_info_lines(
            f"Fight: **{title}**",
            f"HP After: **{player.hp_current}/{player.hp_max}**",
            f"Mana After: **{player.mana_current}/{player.mana_max}**",
            f"Location: **{player.location_data.name}**",
        ),
        inline=False,
    )
    if outcome == "defeat":
        embed.add_field(
            name="Blackout",
            value="You black out, wake in **Rukongai Streets**, and carry **Wounded** for **30 minutes**.",
            inline=False,
        )
    add_explore_divider(embed)
    embed.set_footer(text=_footer_text(combat))
    return embed


class AbilitySelect(discord.ui.Select["ExplorationCombatView"]):
    def __init__(self, combat: CombatSession) -> None:
        ready_abilities = [
            ability
            for ability in list_unlocked_player_abilities(combat.player.level)
            if combat.player.cooldowns.get(ability.key, 0) <= 0
        ]
        if not ready_abilities:
            options = [
                discord.SelectOption(
                    label="No abilities ready",
                    value="locked",
                    description="Wait out cooldowns or unlock more techniques.",
                )
            ]
            disabled = True
        else:
            options = [
                discord.SelectOption(
                    label=ability.name,
                    value=ability.key,
                    description=f"Cost {ability.mana_cost} mana | CD {ability.cooldown_turns}T"[:100],
                )
                for ability in ready_abilities
            ]
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
            active_combat = await get_active_exploration_combat(self.bot.db_pool, interaction.user.id)
            if active_combat is not None:
                await interaction.response.send_message(
                    "That panel is out of date. Use your newest combat message to keep fighting.",
                    ephemeral=True,
                )
                return
            active_dungeon = await get_active_dungeon_run(self.bot.db_pool, interaction.user.id)
            if active_dungeon is not None:
                from src.services.dungeon_service import bind_dungeon_message
                from src.services.player_service import get_player_profile
                from src.ui.dungeon_view import DungeonView, build_dungeon_room_embed

                player = await get_player_profile(self.bot.db_pool, interaction.user.id)
                if player is not None:
                    await interaction.response.send_message(
                        "That fight has already been resolved. Your dungeon has moved on to the next room.",
                        ephemeral=True,
                    )
                    try:
                        await interaction.message.edit(
                            content=f"<@{interaction.user.id}>",
                            embed=build_dungeon_room_embed(player, active_dungeon),
                            view=DungeonView(self.bot, active_dungeon),
                        )
                        await bind_dungeon_message(
                            self.bot.db_pool,
                            user_id=interaction.user.id,
                            message_id=interaction.message.id,
                        )
                    except discord.HTTPException:
                        pass
                    return
            await interaction.response.send_message("That fight is already settled.", ephemeral=True)
            return

        if combat.user_id != interaction.user.id:
            await interaction.response.send_message("That fight belongs to someone else.", ephemeral=True)
            return

        await interaction.response.defer()
        result = await resolve_and_post_combat_action(
            self.bot,
            message_id=interaction.message.id,
            user_id=interaction.user.id,
            action=action,  # type: ignore[arg-type]
            ability_key=ability_key,
            old_message=interaction.message,
        )
        if result.status == "blocked" and result.message is not None:
            await interaction.followup.send(result.message, ephemeral=True)

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

    @discord.ui.button(
        label="Items",
        style=discord.ButtonStyle.secondary,
        custom_id="combat:bandage",
        row=0,
    )
    async def items(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.handle_action(interaction, "bandage")
