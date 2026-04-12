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
    reset_quest,
)
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


QuestBoardScreen = Literal["hub", "category", "detail"]

CATEGORY_META: dict[QuestCategory, dict[str, str]] = {
    "main": {
        "emoji": "📘",
        "title": "Main Quests",
        "tagline": "The road that shapes your place in the world.",
    },
    "side": {
        "emoji": "📗",
        "title": "Side Quests",
        "tagline": "Smaller jobs, rough favors, and trouble worth your time.",
    },
    "daily": {
        "emoji": "📒",
        "title": "Daily Quests",
        "tagline": "Work that returns with the next hard day.",
    },
    "repeatable": {
        "emoji": "📙",
        "title": "Repeatable Quests",
        "tagline": "Reliable grinds for souls who still need more.",
    },
}

STATE_META = {
    "available": {"emoji": "📜", "label": "Available"},
    "active": {"emoji": "🟢", "label": "In Progress"},
    "completed": {"emoji": "✅", "label": "Completed"},
}

BLEACH_QUOTES = (
    '"If you are going to survive, move like your soul means it."',
    '"The streets remember weakness faster than mercy."',
    '"Every step in Rukongai costs something."',
)

DIFFICULTY_META = {
    "tutorial": "🟢 Tutorial",
    "easy": "🟢 Easy",
    "normal": "🟡 Standard",
    "hard": "🟠 Dangerous",
    "brutal": "🔴 Deadly",
}


def _state_text(entry: PlayerQuestEntry) -> str:
    return STATE_META.get(entry.state, {"emoji": "📜", "label": entry.state.title()})["label"]


def _format_reward_lines(entry: PlayerQuestEntry) -> str:
    reward = entry.quest.reward
    lines = [f"✨ XP: **{reward.xp}**"]
    if reward.kan:
        lines.append(f"💰 Kan: **{reward.kan}**")
    if reward.reputation:
        lines.append(f"🤝 Rukongai Rep: **+{reward.reputation}**")
    if reward.stat_points:
        lines.append(f"📈 Stat Points: **{reward.stat_points}**")
    for item in reward.items:
        lines.append(f"🎒 {get_item_definition(item.item_key).name} x**{item.quantity}**")
    return "\n".join(lines)


def _format_granted_reward_lines(update: QuestProgressUpdate) -> str:
    lines = [f"✨ XP Gained: **{update.xp_gained}**"]
    if update.kan_gained:
        lines.append(f"💰 Kan Gained: **{update.kan_gained}**")
    if update.reputation_gained:
        lines.append(f"🤝 Rukongai Rep: **{update.reputation_gained:+d}**")
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


def _format_difficulty_text(difficulty: str) -> str:
    return DIFFICULTY_META.get(difficulty.lower(), f"⚪ {difficulty}")


def _get_briefing_step(entry: PlayerQuestEntry):
    if not entry.quest.steps:
        return None
    if entry.state == "available":
        return entry.quest.steps[0], 0
    index = min(entry.current_step_index, len(entry.quest.steps) - 1)
    return entry.quest.steps[index], index


def _get_default_quest_key(board: PlayerQuestBoard, category: QuestCategory) -> str | None:
    entries = board.quests_by_category.get(category, [])
    if not entries:
        return None
    active_entry = next((entry for entry in entries if entry.state == "active"), None)
    if active_entry is not None:
        return active_entry.quest.key
    return entries[0].quest.key


def _get_selected_entry(
    board: PlayerQuestBoard,
    category: QuestCategory,
    quest_key: str | None,
) -> PlayerQuestEntry | None:
    entries = board.quests_by_category.get(category, [])
    if not entries:
        return None
    return next((entry for entry in entries if entry.quest.key == quest_key), entries[0])


def build_quest_hub_embed(board: PlayerQuestBoard) -> discord.Embed:
    embed = discord.Embed(
        title="🗂️ Soul Assignment Ledger",
        description=(
            "Pinned notices, worn paper, and half-torn orders crowd the board like scars on old wood.\n"
            "Choose a ledger and see which road through Soul Society is open to you."
        ),
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="🧭 Quest Ledgers",
        value="\n".join(
            f"{CATEGORY_META[category]['emoji']} **{CATEGORY_META[category]['title']}**\n"
            f"{CATEGORY_META[category]['tagline']}"
            for category in QUEST_CATEGORY_ORDER
        ),
        inline=False,
    )
    embed.add_field(
        name="📜 Soul Society Saying",
        value=build_explore_info_lines(
            f"Current Level: **{board.player.level}**",
            BLEACH_QUOTES[0],
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Choose a ledger below, then inspect a posting to open its full briefing.")
    return embed


def build_category_embed(board: PlayerQuestBoard, category: QuestCategory) -> discord.Embed:
    meta = CATEGORY_META[category]
    entries = board.quests_by_category.get(category, [])
    embed = discord.Embed(
        title=f"{meta['emoji']} {meta['title']}",
        description=meta["tagline"],
        color=get_explore_color("choice"),
    )

    if not entries:
        embed.add_field(
            name="📭 Nothing Posted",
            value="There are no quests waiting in this section right now.",
            inline=False,
        )
    else:
        lines: list[str] = []
        for entry in entries:
            state = STATE_META.get(entry.state, {"emoji": "📜", "label": entry.state.title()})
            lines.append(
                f"{state['emoji']} **{entry.quest.title}**\n"
                f"Req. Level: **{entry.quest.min_level}** | Difficulty: **{entry.quest.difficulty}** | Status: **{state['label']}**\n"
                "-------"
            )
        embed.add_field(
            name="📜 Posted Quests",
            value="\n\n".join(lines),
            inline=False,
        )
    add_explore_divider(embed)
    embed.set_footer(text="Choose a quest below, or press the briefing button to open the mission file.")
    return embed


def build_quest_detail_embed(category: QuestCategory, entry: PlayerQuestEntry) -> discord.Embed:
    meta = CATEGORY_META[category]
    state = STATE_META.get(entry.state, {"emoji": "📜", "label": entry.state.title()})
    color_key = "reward" if entry.state == "completed" else "choice"
    briefing_step = _get_briefing_step(entry)
    embed = discord.Embed(
        title=f"{meta['emoji']} Quest Briefing | {entry.quest.title}",
        description=entry.quest.short_description,
        color=get_explore_color(color_key),
    )
    embed.add_field(
        name="📌 Mission Details",
        value=build_explore_info_lines(
            f"Status: {state['emoji']} **{state['label']}**",
            f"Requirement: **Level {entry.quest.min_level}+**",
            f"Difficulty: **{_format_difficulty_text(entry.quest.difficulty)}**",
            f"Guide: **{entry.quest.guide_name}**",
            f"Total Steps: **{len(entry.quest.steps)}**",
        ),
        inline=False,
    )
    embed.add_field(
        name="🌆 Lore",
        value=entry.quest.lore_summary or "No lore has been posted for this assignment yet.",
        inline=False,
    )
    embed.add_field(
        name="🎯 Mission Objective",
        value=entry.quest.briefing_objective or entry.quest.short_description,
        inline=False,
    )
    embed.add_field(
        name="🧭 Route Through Rukongai",
        value=_format_step_progress(entry),
        inline=False,
    )

    if entry.state == "completed":
        embed.add_field(
            name="💬 Closing Words",
            value=entry.quest.completion_text,
            inline=False,
        )
        embed.add_field(
            name="🎁 Rewards",
            value=_format_reward_lines(entry),
            inline=False,
        )
        add_explore_divider(embed)
        embed.set_footer(text='Completed. "Once a road is walked, it stays under your feet."')
        return embed

    if briefing_step is None:
        add_explore_divider(embed)
        embed.set_footer(text="This quest has no posted steps yet.")
        return embed

    current_step, current_step_index = briefing_step
    embed.add_field(
        name="📍 Current Assignment" if entry.state == "active" else "📍 First Assignment",
        value=build_explore_info_lines(
            f"Step: **{current_step_index + 1}/{len(entry.quest.steps)}**",
            f"Title: **{current_step.title}**",
        ),
        inline=False,
    )
    embed.add_field(
        name=f"💬 {entry.quest.guide_name}",
        value=current_step.narrative_prompt,
        inline=False,
    )
    embed.add_field(
        name="⚙️ What This Step Teaches",
        value="\n".join(f"• {line}" for line in current_step.system_explanation),
        inline=False,
    )
    embed.add_field(
        name="🎯 Immediate Objective",
        value=current_step.objective,
        inline=False,
    )
    embed.add_field(
        name="🎁 Completion Rewards",
        value=_format_reward_lines(entry),
        inline=False,
    )
    if entry.state == "available":
        embed.add_field(
            name="✅ Accepting This Quest",
            value=(
                "Press **Accept Quest** below to post this mission to your active log. "
                "Only actions taken after acceptance will count toward progress."
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="🔄 Cancel / Reset",
            value=(
                "If this quest gets stuck or you want a clean retry, press **Cancel / Reset Quest** below. "
                "That removes unfinished progress and places the mission back on the board so you can accept it again."
            ),
            inline=False,
        )
    add_explore_divider(embed)
    if entry.state == "available":
        embed.set_footer(text='Accept to begin. "A posted order is just paper until someone bleeds for it."')
    else:
        embed.set_footer(text='Unfinished quests can be cancelled and accepted again from this briefing.')
    return embed


def build_quest_update_embed(update: QuestProgressUpdate) -> discord.Embed:
    if update.status == "completed":
        embed = discord.Embed(
            title=f"✅ Quest Complete | {update.quest.title}",
            description=update.quest.completion_text,
            color=get_explore_color("reward"),
        )
        embed.add_field(
            name="🎁 Rewards Claimed",
            value=_format_granted_reward_lines(update),
            inline=False,
        )
        embed.add_field(
            name="🧭 Cleared Steps",
            value="\n".join(f"✅ {index + 1}. {step.title}" for index, step in enumerate(update.quest.steps)),
            inline=False,
        )
        add_explore_divider(embed)
        embed.set_footer(text='Kaito has seen enough to stop doubting your first steps.')
        return embed

    current_step = update.quest.steps[update.current_step_index]
    embed = discord.Embed(
        title=f"🧭 Quest Updated | {update.quest.title}",
        description="The next piece of the road opens in front of you.",
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
        name="🎯 Objective",
        value=current_step.objective,
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text='Only the active step counts. Keep your footing and move.')
    return embed


class QuestCategorySelect(discord.ui.Select["QuestBoardView"]):
    def __init__(self, selected_category: QuestCategory | None) -> None:
        options = [
            discord.SelectOption(
                label=QUEST_CATEGORY_LABELS[category],
                value=category,
                emoji=CATEGORY_META[category]["emoji"],
                default=category == selected_category,
            )
            for category in QUEST_CATEGORY_ORDER
        ]
        super().__init__(
            placeholder="Choose a quest board",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.open_category(interaction, self.values[0])


class QuestSelect(discord.ui.Select["QuestBoardView"]):
    def __init__(self, *, entries: list[PlayerQuestEntry], selected_quest_key: str | None) -> None:
        options = [
            discord.SelectOption(
                label=entry.quest.title,
                value=entry.quest.key,
                description=f"Req Lv {entry.quest.min_level} | {_state_text(entry)}"[:100],
                default=entry.quest.key == selected_quest_key,
                emoji=STATE_META.get(entry.state, {"emoji": "📜"})["emoji"],
            )
            for entry in entries
        ]
        super().__init__(
            placeholder="Choose a quest to inspect" if selected_quest_key is None else "Switch quest briefing",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.open_detail(interaction, self.values[0])


class AcceptQuestButton(discord.ui.Button["QuestBoardView"]):
    def __init__(self) -> None:
        super().__init__(label="Accept Quest", style=discord.ButtonStyle.success, emoji="✅")

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.accept_selected_quest(interaction)


class ResetQuestButton(discord.ui.Button["QuestBoardView"]):
    def __init__(self) -> None:
        super().__init__(label="Cancel / Reset Quest", style=discord.ButtonStyle.danger, emoji="🔄")

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.reset_selected_quest(interaction)


class BackButton(discord.ui.Button["QuestBoardView"]):
    def __init__(self, *, label: str = "Back", emoji: str = "⬅️") -> None:
        super().__init__(label=label, style=discord.ButtonStyle.secondary, emoji=emoji)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.go_back(interaction)


class OpenQuestBriefingButton(discord.ui.Button["QuestBoardView"]):
    def __init__(self, quest_key: str, quest_title: str) -> None:
        super().__init__(
            label=f"Open {quest_title}"[:80],
            style=discord.ButtonStyle.primary,
            emoji="📜",
        )
        self.quest_key = quest_key

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.open_detail(interaction, self.quest_key)


class QuestBoardView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BleachBot",
        owner_id: int,
        board: PlayerQuestBoard,
        selected_category: QuestCategory | None = None,
        selected_quest_key: str | None = None,
        screen: QuestBoardScreen = "hub",
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.board = board
        self.selected_category = selected_category
        self.selected_quest_key = selected_quest_key
        self.screen = screen
        self.message: discord.Message | None = None
        self._rebuild_components()

    def _rebuild_components(self) -> None:
        self.clear_items()
        self.add_item(QuestCategorySelect(self.selected_category))

        if self.screen in {"category", "detail"} and self.selected_category is not None:
            entries = self.board.quests_by_category.get(self.selected_category, [])
            if entries:
                if self.screen == "detail" and self.selected_quest_key is None:
                    self.selected_quest_key = _get_default_quest_key(self.board, self.selected_category)
                self.add_item(
                    QuestSelect(
                        entries=entries,
                        selected_quest_key=self.selected_quest_key,
                    )
                )

        if self.screen == "category":
            entries = self.board.quests_by_category.get(self.selected_category, []) if self.selected_category is not None else []
            if entries:
                target_entry = next(
                    (entry for entry in entries if entry.quest.key == self.selected_quest_key),
                    next((entry for entry in entries if entry.state == "active"), entries[0]),
                )
                self.add_item(OpenQuestBriefingButton(target_entry.quest.key, target_entry.quest.title))
            self.add_item(BackButton(label="Back to Boards"))
        elif self.screen == "detail":
            entry = _get_selected_entry(self.board, self.selected_category, self.selected_quest_key) if self.selected_category else None
            if entry is not None and entry.state == "available":
                self.add_item(AcceptQuestButton())
                self.add_item(BackButton(label="Cancel", emoji="❌"))
            elif entry is not None and entry.state == "active":
                self.add_item(ResetQuestButton())
                self.add_item(BackButton(label="Back to Quests"))
            else:
                self.add_item(BackButton(label="Back to Quests"))

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
        if self.selected_category is not None:
            available_keys = {
                entry.quest.key
                for entry in self.board.quests_by_category.get(self.selected_category, [])
            }
            if self.selected_quest_key is not None and self.selected_quest_key not in available_keys:
                self.selected_quest_key = _get_default_quest_key(self.board, self.selected_category)
        self._rebuild_components()

    def build_current_embed(self) -> discord.Embed:
        if self.screen == "hub":
            return build_quest_hub_embed(self.board)
        if self.selected_category is None:
            return build_quest_hub_embed(self.board)
        if self.screen == "category":
            return build_category_embed(self.board, self.selected_category)
        entry = _get_selected_entry(self.board, self.selected_category, self.selected_quest_key)
        if entry is None:
            return build_category_embed(self.board, self.selected_category)
        return build_quest_detail_embed(self.selected_category, entry)

    async def open_category(self, interaction: discord.Interaction, category_value: str) -> None:
        self.selected_category = category_value  # type: ignore[assignment]
        self.selected_quest_key = None
        self.screen = "category"
        await self.refresh_board()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    async def open_detail(self, interaction: discord.Interaction, quest_key: str) -> None:
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
                value="The quest is now live. Its objectives will count from this point on.",
                inline=False,
            )
        elif status == "active":
            embed.add_field(
                name="🟢 Already Active",
                value="This quest is already in progress.",
                inline=False,
            )
        elif status == "completed":
            embed.add_field(
                name="✅ Already Completed",
                value="You already finished this quest.",
                inline=False,
            )
        elif status == "ineligible":
            embed.add_field(
                name="🔒 Locked",
                value="You do not meet the level requirement yet.",
                inline=False,
            )
        else:
            embed.add_field(
                name="⚠️ Error",
                value="I couldn't accept that quest right now.",
                inline=False,
            )
        await interaction.response.edit_message(embed=embed, view=self)

    async def reset_selected_quest(self, interaction: discord.Interaction) -> None:
        if self.selected_quest_key is None or self.selected_category is None:
            await interaction.response.send_message("Pick a quest first.", ephemeral=True)
            return
        status = await reset_quest(self.bot.db_pool, interaction.user.id, self.selected_quest_key)
        await self.refresh_board()
        self.screen = "detail"
        embed = self.build_current_embed()
        if status == "reset":
            embed.add_field(
                name="🔄 Quest Reset",
                value="Your unfinished progress was cleared. This mission is posted again and can be accepted fresh right now.",
                inline=False,
            )
        elif status == "completed":
            embed.add_field(
                name="✅ Already Completed",
                value="Completed quests cannot be reset this way.",
                inline=False,
            )
        else:
            embed.add_field(
                name="⚠️ Reset Failed",
                value="I couldn't reset that quest right now.",
                inline=False,
            )
        await interaction.response.edit_message(embed=embed, view=self)

    async def go_back(self, interaction: discord.Interaction) -> None:
        if self.screen == "detail":
            self.screen = "category"
        else:
            self.screen = "hub"
            self.selected_category = None
            self.selected_quest_key = None
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
