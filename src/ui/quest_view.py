from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.data.items import get_item_definition
from src.models.quest import QuestCategory, QuestProgressUpdate
from src.services.quest_service import (
    QUEST_CATEGORY_LABELS,
    QUEST_CATEGORY_ORDER,
    PlayerQuestBoard,
    PlayerQuestEntry,
    get_player_quest_board,
)
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


def _format_step_progress(entry: PlayerQuestEntry) -> str:
    lines: list[str] = []
    for index, step in enumerate(entry.quest.steps):
        if entry.state == "completed" or index < entry.current_step_index:
            prefix = "[Done]"
        elif entry.state == "active" and index == entry.current_step_index:
            prefix = "[Active]"
        else:
            prefix = "[Next]"
        lines.append(f"{prefix} {index + 1}. {step.title}")
    return "\n".join(lines)


def _format_reward_lines(entry: PlayerQuestEntry) -> str:
    reward = entry.quest.reward
    lines = [f"XP: {reward.xp}"]
    if reward.kan:
        lines.append(f"Kan: {reward.kan}")
    if reward.stat_points:
        lines.append(f"Stat Points: {reward.stat_points}")
    for item in reward.items:
        lines.append(f"{item.quantity}x {get_item_definition(item.item_key).name}")
    return "\n".join(lines)


def _format_granted_reward_lines(update: QuestProgressUpdate) -> str:
    lines = [f"XP: {update.xp_gained}"]
    if update.kan_gained:
        lines.append(f"Kan: {update.kan_gained}")
    if update.stat_points_gained:
        lines.append(f"Stat Points: {update.stat_points_gained}")
    for item in update.granted_items:
        lines.append(f"{item.quantity}x {item.item_name}")
    if update.levels_gained > 0:
        lines.append(f"Levels Gained: {update.levels_gained}")
    return "\n".join(lines)


def _build_empty_category_embed(category: QuestCategory) -> discord.Embed:
    embed = discord.Embed(
        title=f"{QUEST_CATEGORY_LABELS[category]}",
        description=f"There are no eligible {QUEST_CATEGORY_LABELS[category].lower()} for you yet.",
        color=get_explore_color("flavor"),
    )
    add_explore_divider(embed)
    return embed


def build_quest_update_embed(update: QuestProgressUpdate) -> discord.Embed:
    if update.status == "completed":
        embed = discord.Embed(
            title=f"Quest Complete | {update.quest.title}",
            description=update.quest.completion_text,
            color=get_explore_color("reward"),
        )
        embed.add_field(
            name="Rewards",
            value=_format_granted_reward_lines(update),
            inline=False,
        )
        embed.add_field(
            name="Progress",
            value="\n".join(f"[Done] {index + 1}. {step.title}" for index, step in enumerate(update.quest.steps)),
            inline=False,
        )
        add_explore_divider(embed)
        embed.set_footer(text="Kaito has nothing else to add for now.")
        return embed

    current_step = update.quest.steps[update.current_step_index]
    embed = discord.Embed(
        title=f"Quest Updated | {update.quest.title}",
        description=f"{update.quest.guide_name} watches you a little more closely now.",
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="Current Step",
        value=build_explore_info_lines(
            f"Step: {update.current_step_index + 1}/{len(update.quest.steps)}",
            f"Title: {current_step.title}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Kaito",
        value=current_step.narrative_prompt,
        inline=False,
    )
    embed.add_field(
        name="How This Works",
        value="\n".join(current_step.system_explanation),
        inline=False,
    )
    embed.add_field(
        name="Objective",
        value=current_step.objective,
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Only the active quest step gives credit.")
    return embed


def build_quest_embed(category: QuestCategory, entry: PlayerQuestEntry) -> discord.Embed:
    color = get_explore_color("reward" if entry.state == "completed" else "explore")
    embed = discord.Embed(
        title=f"{QUEST_CATEGORY_LABELS[category][:-1]} | {entry.quest.title}",
        description=entry.quest.short_description,
        color=color,
    )

    if entry.state == "completed":
        embed.add_field(
            name="Quest Status",
            value=build_explore_info_lines(
                "Status: Completed",
                f"Guide: {entry.quest.guide_name}",
                f"Steps Cleared: {len(entry.quest.steps)}/{len(entry.quest.steps)}",
            ),
            inline=False,
        )
        embed.add_field(
            name="Kaito",
            value=entry.quest.completion_text,
            inline=False,
        )
        embed.add_field(
            name="Rewards",
            value=_format_reward_lines(entry),
            inline=False,
        )
        embed.add_field(
            name="Progress",
            value=_format_step_progress(entry),
            inline=False,
        )
        add_explore_divider(embed)
        embed.set_footer(text="This quest is complete.")
        return embed

    current_step = entry.quest.steps[min(entry.current_step_index, len(entry.quest.steps) - 1)]
    embed.add_field(
        name="Quest Status",
        value=build_explore_info_lines(
            f"Status: {entry.state.title()}",
            f"Guide: {entry.quest.guide_name}",
            f"Current Step: {entry.current_step_index + 1}/{len(entry.quest.steps)}",
        ),
        inline=False,
    )
    embed.add_field(
        name=current_step.title,
        value=current_step.narrative_prompt,
        inline=False,
    )
    embed.add_field(
        name="How This Works",
        value="\n".join(current_step.system_explanation),
        inline=False,
    )
    embed.add_field(
        name="Objective",
        value=current_step.objective,
        inline=False,
    )
    embed.add_field(
        name="Progress",
        value=_format_step_progress(entry),
        inline=False,
    )
    embed.add_field(
        name="Completion Reward",
        value=_format_reward_lines(entry),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Quest progress updates automatically when the active objective is completed.")
    return embed


def _get_default_quest_key(board: PlayerQuestBoard, category: QuestCategory) -> str | None:
    entries = board.quests_by_category.get(category, [])
    if not entries:
        return None

    active_entry = next((entry for entry in entries if entry.state == "active"), None)
    if active_entry is not None:
        return active_entry.quest.key
    return entries[0].quest.key


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
                )
            ]
            disabled = True

        super().__init__(
            placeholder="Choose a quest",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None or self.disabled:
            return
        await self.view.set_quest(interaction, self.values[0])


def _describe_entry(entry: PlayerQuestEntry) -> str:
    if entry.state == "completed":
        return "Completed"
    if entry.state == "active":
        step = entry.quest.steps[min(entry.current_step_index, len(entry.quest.steps) - 1)]
        return f"Active: {step.title}"[:100]
    return "Available"


class QuestBoardView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BleachBot",
        owner_id: int,
        board: PlayerQuestBoard,
        selected_category: QuestCategory = "main",
        selected_quest_key: str | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.board = board
        self.selected_category = selected_category
        self.selected_quest_key = selected_quest_key or _get_default_quest_key(board, selected_category)
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
        entries = self.board.quests_by_category.get(self.selected_category, [])
        if not entries:
            return _build_empty_category_embed(self.selected_category)

        selected_entry = next(
            (entry for entry in entries if entry.quest.key == self.selected_quest_key),
            entries[0],
        )
        return build_quest_embed(self.selected_category, selected_entry)

    async def set_category(self, interaction: discord.Interaction, category_value: str) -> None:
        self.selected_category = category_value  # type: ignore[assignment]
        self.selected_quest_key = _get_default_quest_key(self.board, self.selected_category)
        await self.refresh_board()
        await interaction.response.edit_message(
            embed=self.build_current_embed(),
            view=self,
        )

    async def set_quest(self, interaction: discord.Interaction, quest_key: str) -> None:
        self.selected_quest_key = quest_key
        await self.refresh_board()
        await interaction.response.edit_message(
            embed=self.build_current_embed(),
            view=self,
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
