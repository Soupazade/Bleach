from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord

from src.data.items import get_item_definition
from src.models.quest import QuestCategory, QuestProgressUpdate
from src.services.quest_service import (
    QUEST_CATEGORY_LABELS,
    QUEST_CATEGORY_ORDER,
    PlayerQuestBoard,
    PlayerQuestEntry,
    accept_quest,
    get_player_quest_board,
)
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


QuestBoardScreen = Literal["hub", "detail"]

STATE_EMOJIS = {
    "available": "📜",
    "active": "🟢",
    "completed": "✅",
}


def _format_reward_lines(entry: PlayerQuestEntry) -> str:
    reward = entry.quest.reward
    lines = [f"✨ XP: **{reward.xp}**"]
    if reward.kan:
        lines.append(f"💰 Kan: **{reward.kan}**")
    if reward.stat_points:
        lines.append(f"📈 Stat Points: **{reward.stat_points}**")
    for item in reward.items:
        lines.append(f"🎒 {get_item_definition(item.item_key).name} x**{item.quantity}**")
    return "\n".join(lines)


def _format_granted_reward_lines(update: QuestProgressUpdate) -> str:
    lines = [f"✨ XP Gained: **{update.xp_gained}**"]
    if update.kan_gained:
        lines.append(f"💰 Kan Gained: **{update.kan_gained}**")
    if update.stat_points_gained:
        lines.append(f"📈 Stat Points: **{update.stat_points_gained}**")
    for item in update.granted_items:
        lines.append(f"🎒 {item.item_name} x**{item.quantity}**")
    if update.levels_gained > 0:
        lines.append(f"⬆️ Levels Gained: **{update.levels_gained}**")
    return "\n".join(lines)


def _format_step_progress(entry: PlayerQuestEntry) -> str:
    lines: list[str] = []
    for index, step in enumerate(entry.quest.steps):
        if entry.state == "completed" or index < entry.current_step_index:
            prefix = "✅"
        elif entry.state == "active" and index == entry.current_step_index:
            prefix = "🎯"
        else:
            prefix = "▫️"
        lines.append(f"{prefix} {index + 1}. {step.title}")
    return "\n".join(lines)


def _describe_entry(entry: PlayerQuestEntry) -> str:
    if entry.state == "completed":
        return "Completed"
    if entry.state == "active":
        step = entry.quest.steps[min(entry.current_step_index, len(entry.quest.steps) - 1)]
        return f"Active: {step.title}"[:100]
    return "Available to accept"


def _get_default_quest_key(board: PlayerQuestBoard, category: QuestCategory) -> str | None:
    entries = board.quests_by_category.get(category, [])
    if not entries:
        return None
    active_entry = next((entry for entry in entries if entry.state == "active"), None)
    if active_entry is not None:
        return active_entry.quest.key
    return entries[0].quest.key


def _get_selected_entry(board: PlayerQuestBoard, category: QuestCategory, quest_key: str | None) -> PlayerQuestEntry | None:
    entries = board.quests_by_category.get(category, [])
    if not entries:
        return None
    return next((entry for entry in entries if entry.quest.key == quest_key), entries[0])


def _build_category_summary(board: PlayerQuestBoard) -> str:
    lines: list[str] = []
    for category in QUEST_CATEGORY_ORDER:
        entries = board.quests_by_category.get(category, [])
        active_count = sum(1 for entry in entries if entry.state == "active")
        available_count = sum(1 for entry in entries if entry.state == "available")
        completed_count = sum(1 for entry in entries if entry.state == "completed")
        lines.append(
            f"• **{QUEST_CATEGORY_LABELS[category]}**: {len(entries)} total | "
            f"{active_count} active | {available_count} available | {completed_count} complete"
        )
    return "\n".join(lines)


def build_quest_hub_embed(
    board: PlayerQuestBoard,
    *,
    selected_category: QuestCategory,
    selected_quest_key: str | None,
) -> discord.Embed:
    entries = board.quests_by_category.get(selected_category, [])
    embed = discord.Embed(
        title="🗺️ Quest Board",
        description=(
            "Browse the work available to your soul, pick a quest, and open its briefing before you accept it."
        ),
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="👤 Soul Record",
        value=build_explore_info_lines(
            f"Level: **{board.player.level}**",
            f"Location: **{board.player.location_data.name}**",
            f"Unspent Stat Points: **{board.player.unspent_stat_points}**",
        ),
        inline=False,
    )
    embed.add_field(
        name="📚 Categories",
        value=_build_category_summary(board),
        inline=False,
    )

    if not entries:
        embed.add_field(
            name=f"🧭 {QUEST_CATEGORY_LABELS[selected_category]}",
            value="Nothing is available in this category yet.",
            inline=False,
        )
    else:
        quest_lines = []
        for entry in entries:
            emoji = STATE_EMOJIS.get(entry.state, "📜")
            marker = "👉 " if entry.quest.key == selected_quest_key else ""
            quest_lines.append(f"{marker}{emoji} **{entry.quest.title}**")
            quest_lines.append(f"   {_describe_entry(entry)}")
        embed.add_field(
            name=f"🧭 {QUEST_CATEGORY_LABELS[selected_category]}",
            value="\n".join(quest_lines),
            inline=False,
        )

    add_explore_divider(embed)
    embed.set_footer(text="Pick a category, choose a quest, then open its briefing.")
    return embed


def build_quest_detail_embed(category: QuestCategory, entry: PlayerQuestEntry) -> discord.Embed:
    color = get_explore_color("reward" if entry.state == "completed" else "choice")
    embed = discord.Embed(
        title=f"📖 {QUEST_CATEGORY_LABELS[category][:-1]} | {entry.quest.title}",
        description=entry.quest.short_description,
        color=color,
    )
    status_line = {
        "available": "📜 Available",
        "active": "🟢 Active",
        "completed": "✅ Completed",
    }.get(entry.state, entry.state.title())
    embed.add_field(
        name="📌 Quest Status",
        value=build_explore_info_lines(
            f"Status: {status_line}",
            f"Guide: **{entry.quest.guide_name}**",
            f"Steps: **{len(entry.quest.steps)}**",
        ),
        inline=False,
    )
    embed.add_field(
        name="🧭 Step Path",
        value=_format_step_progress(entry),
        inline=False,
    )

    if entry.state == "completed":
        embed.add_field(
            name="💬 Final Words",
            value=entry.quest.completion_text,
            inline=False,
        )
        embed.add_field(
            name="🎁 Completion Rewards",
            value=_format_reward_lines(entry),
            inline=False,
        )
        add_explore_divider(embed)
        embed.set_footer(text="This quest is already finished.")
        return embed

    current_step_index = 0 if entry.state == "available" else min(entry.current_step_index, len(entry.quest.steps) - 1)
    current_step = entry.quest.steps[current_step_index]
    step_label = "First Step" if entry.state == "available" else f"Current Step {current_step_index + 1}"
    embed.add_field(
        name=f"💬 {step_label}",
        value=current_step.narrative_prompt,
        inline=False,
    )
    embed.add_field(
        name="⚙️ What This Teaches",
        value="\n".join(f"• {line}" for line in current_step.system_explanation),
        inline=False,
    )
    embed.add_field(
        name="🎯 Objective",
        value=current_step.objective,
        inline=False,
    )
    embed.add_field(
        name="🎁 Completion Rewards",
        value=_format_reward_lines(entry),
        inline=False,
    )
    add_explore_divider(embed)
    if entry.state == "available":
        embed.set_footer(text="Accept this quest to make its objectives count.")
    else:
        embed.set_footer(text="Only the active step counts toward quest progress.")
    return embed


def build_quest_update_embed(update: QuestProgressUpdate) -> discord.Embed:
    if update.status == "completed":
        embed = discord.Embed(
            title=f"✅ Quest Complete | {update.quest.title}",
            description=update.quest.completion_text,
            color=get_explore_color("reward"),
        )
        embed.add_field(
            name="🎁 Rewards",
            value=_format_granted_reward_lines(update),
            inline=False,
        )
        embed.add_field(
            name="🧭 Cleared Steps",
            value="\n".join(f"✅ {index + 1}. {step.title}" for index, step in enumerate(update.quest.steps)),
            inline=False,
        )
        add_explore_divider(embed)
        embed.set_footer(text="Kaito is taking you a little more seriously now.")
        return embed

    current_step = update.quest.steps[update.current_step_index]
    embed = discord.Embed(
        title=f"🧭 Quest Updated | {update.quest.title}",
        description="The next part of the road opens up in front of you.",
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="📌 New Active Step",
        value=build_explore_info_lines(
            f"Step: **{update.current_step_index + 1}/{len(update.quest.steps)}**",
            f"Title: **{current_step.title}**",
        ),
        inline=False,
    )
    embed.add_field(
        name="💬 Kaito",
        value=current_step.narrative_prompt,
        inline=False,
    )
    embed.add_field(
        name="⚙️ What This Means",
        value="\n".join(f"• {line}" for line in current_step.system_explanation),
        inline=False,
    )
    embed.add_field(
        name="🎯 Objective",
        value=current_step.objective,
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Only the currently active step gives quest credit.")
    return embed


class QuestCategorySelect(discord.ui.Select["QuestBoardView"]):
    def __init__(self, selected_category: QuestCategory) -> None:
        options = [
            discord.SelectOption(
                label=QUEST_CATEGORY_LABELS[category],
                value=category,
                default=category == selected_category,
            )
            for category in QUEST_CATEGORY_ORDER
        ]
        super().__init__(
            placeholder="Choose a quest category",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.set_category(interaction, self.values[0])


class QuestSelect(discord.ui.Select["QuestBoardView"]):
    def __init__(
        self,
        *,
        board: PlayerQuestBoard,
        selected_category: QuestCategory,
        selected_quest_key: str | None,
    ) -> None:
        entries = board.quests_by_category.get(selected_category, [])
        if entries:
            options = [
                discord.SelectOption(
                    label=entry.quest.title,
                    value=entry.quest.key,
                    description=_describe_entry(entry),
                    default=entry.quest.key == selected_quest_key,
                    emoji=STATE_EMOJIS.get(entry.state, "📜"),
                )
                for entry in entries
            ]
            disabled = False
        else:
            options = [
                discord.SelectOption(
                    label="No quests available",
                    value="empty",
                    description="Nothing is open in this category yet.",
                    emoji="📭",
                )
            ]
            disabled = True

        super().__init__(
            placeholder="Choose a quest to inspect",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None or self.disabled:
            return
        await self.view.show_quest_detail(interaction, self.values[0])


class AcceptQuestButton(discord.ui.Button["QuestBoardView"]):
    def __init__(self, disabled: bool) -> None:
        super().__init__(label="Accept Quest", style=discord.ButtonStyle.success, emoji="✅", disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.accept_selected_quest(interaction)


class BackToHubButton(discord.ui.Button["QuestBoardView"]):
    def __init__(self, *, deny_mode: bool) -> None:
        label = "Deny Quest" if deny_mode else "Back to Board"
        emoji = "❌" if deny_mode else "⬅️"
        super().__init__(label=label, style=discord.ButtonStyle.secondary, emoji=emoji)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.go_to_hub(interaction)


class QuestBoardView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BleachBot",
        owner_id: int,
        board: PlayerQuestBoard,
        selected_category: QuestCategory = "main",
        selected_quest_key: str | None = None,
        screen: QuestBoardScreen = "hub",
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.board = board
        self.selected_category = selected_category
        self.selected_quest_key = selected_quest_key or _get_default_quest_key(board, selected_category)
        self.screen = screen
        self.message: discord.Message | None = None
        self._rebuild_components()

    def _rebuild_components(self) -> None:
        self.clear_items()
        self.add_item(QuestCategorySelect(self.selected_category))
        self.add_item(
            QuestSelect(
                board=self.board,
                selected_category=self.selected_category,
                selected_quest_key=self.selected_quest_key,
            )
        )
        if self.screen == "detail":
            selected_entry = _get_selected_entry(self.board, self.selected_category, self.selected_quest_key)
            is_available = selected_entry is not None and selected_entry.state == "available"
            self.add_item(AcceptQuestButton(disabled=not is_available))
            self.add_item(BackToHubButton(deny_mode=is_available))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "This quest board belongs to another player. Use `/quest` to open your own.",
            ephemeral=True,
        )
        return False

    async def refresh_board(self) -> None:
        board = await get_player_quest_board(self.bot.db_pool, self.owner_id)
        if board is None:
            return
        self.board = board
        available_keys = {
            entry.quest.key
            for entry in self.board.quests_by_category.get(self.selected_category, [])
        }
        if self.selected_quest_key not in available_keys:
            self.selected_quest_key = _get_default_quest_key(self.board, self.selected_category)
        self._rebuild_components()

    def build_current_embed(self) -> discord.Embed:
        if self.screen == "hub":
            return build_quest_hub_embed(
                self.board,
                selected_category=self.selected_category,
                selected_quest_key=self.selected_quest_key,
            )
        selected_entry = _get_selected_entry(self.board, self.selected_category, self.selected_quest_key)
        if selected_entry is None:
            return build_quest_hub_embed(
                self.board,
                selected_category=self.selected_category,
                selected_quest_key=self.selected_quest_key,
            )
        return build_quest_detail_embed(self.selected_category, selected_entry)

    async def set_category(self, interaction: discord.Interaction, category_value: str) -> None:
        self.selected_category = category_value  # type: ignore[assignment]
        self.selected_quest_key = _get_default_quest_key(self.board, self.selected_category)
        self.screen = "hub"
        await self.refresh_board()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    async def show_quest_detail(self, interaction: discord.Interaction, quest_key: str) -> None:
        self.selected_quest_key = quest_key
        self.screen = "detail"
        await self.refresh_board()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    async def accept_selected_quest(self, interaction: discord.Interaction) -> None:
        if self.selected_quest_key is None:
            await interaction.response.send_message("Pick a quest first.", ephemeral=True)
            return
        status = await accept_quest(self.bot.db_pool, interaction.user.id, self.selected_quest_key)
        await self.refresh_board()
        self.screen = "detail"
        embed = self.build_current_embed()
        if status == "accepted":
            embed.add_field(
                name="✅ Accepted",
                value="This quest is now active. Its objectives will start counting immediately.",
                inline=False,
            )
        elif status == "active":
            embed.add_field(
                name="🟢 Already Active",
                value="You already accepted this quest. Keep moving on the current step.",
                inline=False,
            )
        elif status == "completed":
            embed.add_field(
                name="✅ Already Completed",
                value="You already cleared this quest.",
                inline=False,
            )
        elif status == "ineligible":
            embed.add_field(
                name="🔒 Not Eligible",
                value="You do not meet the level requirement for this quest yet.",
                inline=False,
            )
        else:
            embed.add_field(
                name="⚠️ Quest Error",
                value="I couldn't accept that quest right now.",
                inline=False,
            )
        await interaction.response.edit_message(embed=embed, view=self)

    async def go_to_hub(self, interaction: discord.Interaction) -> None:
        self.screen = "hub"
        await self.refresh_board()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
