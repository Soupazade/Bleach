from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.data.dungeons import get_dungeon_definition
from src.models.dungeon import ActiveDungeonRun, DungeonProgressState
from src.models.player import PlayerProfile
from src.services.combat_service import schedule_combat_task
from src.services.dungeon_service import (
    DungeonAdvanceResult,
    abandon_dungeon_run,
    advance_dungeon_room,
    get_active_dungeon_run_by_message,
    get_dungeon_definition_for_run,
    get_dungeon_room,
    get_room_options,
)
from src.ui.exploration_combat_view import ExplorationCombatView, build_exploration_combat_embed
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, format_option_preview, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


BUTTON_STYLE_MAP = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}


def _format_map(run: ActiveDungeonRun) -> str:
    dungeon = get_dungeon_definition_for_run(run)
    lines: list[str] = []
    for index, room in enumerate(dungeon.rooms):
        if index < run.current_room_index:
            prefix = "✅"
        elif index == run.current_room_index:
            prefix = "🟨"
        else:
            prefix = "⬛"
        lines.append(f"{prefix} Room {index + 1}: **{room.map_label}**")
    return "\n".join(lines)


def _format_loot(progress: DungeonProgressState) -> str:
    if not progress.items:
        return "Nothing secured yet."
    return "\n".join(f"- {item.quantity}x {item.item_name}" for item in progress.items)


def _format_history(progress: DungeonProgressState) -> str:
    if not progress.history:
        return "The hideout is still holding its breath."
    return "\n".join(f"- {entry}" for entry in progress.history[-3:])


def build_dungeon_room_embed(player: PlayerProfile, run: ActiveDungeonRun) -> discord.Embed:
    dungeon = get_dungeon_definition_for_run(run)
    room = get_dungeon_room(run)
    options = get_room_options(room)
    color_key = "choice" if room.kind == "choice" else "combat"
    if room.kind == "boss":
        color_key = "special"

    embed = discord.Embed(
        title=f"🕳️ {dungeon.title}",
        description=f"**{room.title}**\n{room.description}",
        color=get_explore_color(color_key),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Location: **{player.location_data.name}**",
            f"⚡ Stamina: **{player.stamina_current}/{player.stamina_max}**",
            f"🪶 HP: **{player.hp_current}/{player.hp_max}**",
            f"📈 Level: **{player.level}**",
        ),
        inline=True,
    )
    embed.add_field(
        name="Hideout Map",
        value=_format_map(run),
        inline=True,
    )
    if options:
        embed.add_field(
            name="What do you do?",
            value="\n".join(format_option_preview(option.label, option.style) for option in options),
            inline=False,
        )
    embed.add_field(
        name="Run Rewards",
        value=build_explore_info_lines(
            f"XP Banked: **{run.progress.total_xp}**",
            f"Kan Banked: **{run.progress.total_kan}**",
            f"Reputation: **{run.progress.total_reputation:+d}**",
            f"Loot:\n{_format_loot(run.progress)}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Recent Movement",
        value=_format_history(run.progress),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text=dungeon.subtitle)
    return embed


def build_dungeon_started_embed(player: PlayerProfile, run: ActiveDungeonRun, *, stamina_cost: int) -> discord.Embed:
    dungeon = get_dungeon_definition_for_run(run)
    embed = discord.Embed(
        title=f"🕳️ {dungeon.intro_title}",
        description=dungeon.intro_description,
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="Commitment",
        value=build_explore_info_lines(
            f"Location: **{player.location_data.name}**",
            f"Stamina Cost: **{stamina_cost}**",
            f"After Entry: **{player.stamina_current}/{player.stamina_max} stamina**",
        ),
        inline=False,
    )
    embed.add_field(
        name="Route",
        value=_format_map(run),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="The Outskirts are waiting to see whether you come back out stronger or just quieter.")
    return embed


def build_dungeon_blocked_embed(title: str, description: str, *, kind: str = "combat") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color(kind),
    )
    add_explore_divider(embed)
    return embed


def build_dungeon_abandoned_embed(run: ActiveDungeonRun | None) -> discord.Embed:
    dungeon_title = "The Briar Den"
    if run is not None:
        dungeon_title = get_dungeon_definition_for_run(run).title
    embed = discord.Embed(
        title=f"🕳️ {dungeon_title}",
        description="You pull out of the hideout before it can ask any more of you. The Outskirts keep their shadows for now.",
        color=get_explore_color("flavor"),
    )
    add_explore_divider(embed)
    return embed


def build_dungeon_completion_embed(
    player: PlayerProfile,
    *,
    dungeon_key: str,
    progress: DungeonProgressState,
) -> discord.Embed:
    dungeon = get_dungeon_definition(dungeon_key)
    embed = discord.Embed(
        title=f"🏆 {dungeon.completion_title}",
        description=dungeon.completion_description,
        color=get_explore_color("reward"),
    )
    embed.add_field(
        name="Run Summary",
        value=build_explore_info_lines(
            f"XP Gained: **{progress.total_xp}**",
            f"Kan Gained: **{progress.total_kan}**",
            f"Reputation: **{progress.total_reputation:+d}**",
            f"HP After: **{player.hp_current}/{player.hp_max}**",
            f"Mana After: **{player.mana_current}/{player.mana_max}**",
        ),
        inline=False,
    )
    embed.add_field(name="Loot", value=_format_loot(progress), inline=False)
    embed.add_field(name="Trail Left Behind", value=_format_history(progress), inline=False)
    add_explore_divider(embed)
    embed.set_footer(text=dungeon.subtitle)
    return embed


def build_dungeon_failure_embed(
    player: PlayerProfile,
    *,
    dungeon_key: str,
    progress: DungeonProgressState,
    outcome: str,
) -> discord.Embed:
    dungeon = get_dungeon_definition(dungeon_key)
    description = "The hideout throws you back out before the work is done. The Outskirts keep what they can."
    if outcome == "retreated":
        description = "You pull out before the hideout can close its hand the rest of the way."
    elif outcome == "defeat":
        description = "The hideout wins this round, and you leave it paying for the lesson."
    embed = discord.Embed(
        title=f"☠️ {dungeon.title}",
        description=description,
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Run Summary",
        value=build_explore_info_lines(
            f"XP Kept: **{progress.total_xp}**",
            f"Kan Kept: **{progress.total_kan}**",
            f"Reputation: **{progress.total_reputation:+d}**",
            f"HP After: **{player.hp_current}/{player.hp_max}**",
            f"Location: **{player.location_data.name}**",
        ),
        inline=False,
    )
    embed.add_field(name="Loot", value=_format_loot(progress), inline=False)
    embed.add_field(name="Trail Left Behind", value=_format_history(progress), inline=False)
    add_explore_divider(embed)
    embed.set_footer(text=dungeon.subtitle)
    return embed


class DungeonView(discord.ui.View):
    def __init__(self, bot: "BleachBot", run: ActiveDungeonRun | None = None) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self._configure_buttons(run)

    def _configure_buttons(self, run: ActiveDungeonRun | None) -> None:
        options = ()
        if run is not None:
            options = get_room_options(get_dungeon_room(run))

        buttons = (self.choice_one, self.choice_two)
        for index, button in enumerate(buttons):
            if index < len(options):
                option = options[index]
                button.label = option.label
                button.style = BUTTON_STYLE_MAP[option.style]
                button.disabled = False
            else:
                button.label = "Unavailable"
                button.style = discord.ButtonStyle.secondary
                button.disabled = True

    async def _handle_choice(self, interaction: discord.Interaction, option_slot: int) -> None:
        if interaction.message is None:
            await interaction.response.send_message("That hideout run is no longer active.", ephemeral=True)
            return

        run = await get_active_dungeon_run_by_message(self.bot.db_pool, interaction.message.id)
        if run is None:
            await interaction.response.send_message("That hideout run has already been settled.", ephemeral=True)
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass
            return

        if run.user_id != interaction.user.id:
            await interaction.response.send_message("That dungeon run belongs to someone else.", ephemeral=True)
            return

        result = await advance_dungeon_room(
            self.bot.db_pool,
            message_id=interaction.message.id,
            user_id=interaction.user.id,
            option_slot=option_slot,
        )
        await self._apply_result(interaction, result)

    async def _apply_result(
        self,
        interaction: discord.Interaction,
        result: DungeonAdvanceResult,
    ) -> None:
        if result.status == "blocked":
            await interaction.response.send_message(result.message or "That move is blocked.", ephemeral=True)
            return
        if result.status == "updated" and result.player is not None and result.run is not None:
            await interaction.response.edit_message(
                embed=build_dungeon_room_embed(result.player, result.run),
                view=DungeonView(self.bot, result.run),
            )
            return
        if result.status == "combat" and result.combat is not None:
            schedule_combat_task(self.bot, result.combat)
            await interaction.response.edit_message(
                embed=build_exploration_combat_embed(result.combat, interaction.user),
                view=ExplorationCombatView(self.bot, result.combat),
            )
            return
        if result.status == "abandoned":
            await interaction.response.edit_message(
                embed=build_dungeon_abandoned_embed(result.run),
                view=None,
            )
            return
        await interaction.response.send_message("I could not settle that dungeon step right now.", ephemeral=True)

    @discord.ui.button(
        label="Choice One",
        style=discord.ButtonStyle.primary,
        custom_id="dungeon:choice_one",
        row=0,
    )
    async def choice_one(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_choice(interaction, 1)

    @discord.ui.button(
        label="Choice Two",
        style=discord.ButtonStyle.secondary,
        custom_id="dungeon:choice_two",
        row=0,
    )
    async def choice_two(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_choice(interaction, 2)

    @discord.ui.button(
        label="Withdraw",
        style=discord.ButtonStyle.secondary,
        custom_id="dungeon:withdraw",
        row=1,
    )
    async def withdraw(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.message is None:
            await interaction.response.send_message("That hideout run is no longer active.", ephemeral=True)
            return
        result = await abandon_dungeon_run(
            self.bot.db_pool,
            user_id=interaction.user.id,
            message_id=interaction.message.id,
        )
        await self._apply_result(interaction, result)
