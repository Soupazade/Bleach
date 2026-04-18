from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

from src.data.locations import get_location_definition
from src.data.training import (
    ALL_STATS_KEY,
    TRAINING_YARD_LOCATION_KEY,
    get_training_duration,
    get_training_duration_options,
    get_training_focus,
    get_training_full_reward,
    is_valid_training_selection,
)
from src.models.player import PlayerProfile
from src.models.training import ActiveTraining
from src.services.combat_service import get_active_exploration_combat
from src.services.location_service import format_location_room_reference
from src.services.player_service import build_resting_block_message, get_rest_status
from src.services.quest_service import record_quest_action
from src.services.reputation_service import (
    format_reputation_stamina_text,
    get_location_reputation_title,
)
from src.services.training_service import (
    TrainingResolution,
    format_training_reward_lines,
    get_active_training,
    get_training_focus_label,
    get_training_progress_snapshot,
    get_training_remaining_time,
    get_training_stamina_text,
    resolve_and_post_training,
    resolve_training,
    schedule_training_task,
    start_training,
)
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color
from src.ui.exploration_combat_view import build_active_combat_embed
from src.ui.explore_view import build_explore_resolution_posted_embed
from src.ui.quest_view import build_quest_update_embed
from src.ui.stat_allocation_view import send_stat_allocation_prompt
from src.ui.travel_view import build_travel_active_embed, build_travel_resolution_posted_embed

if TYPE_CHECKING:
    from src.main import BleachBot


def _format_training_current_totals(player: PlayerProfile) -> str:
    return build_explore_info_lines(
        f"📈 Power: {player.power}",
        f"📈 Defense: {player.defense}",
        f"📈 Speed: {player.speed}",
        f"📈 Reiatsu: {player.reiatsu}",
    )


def _format_duration_option_description(
    focus_key: str,
    duration_minutes: int,
) -> str:
    reward = get_training_full_reward(focus_key, duration_minutes)
    if focus_key == ALL_STATS_KEY:
        reward_text = "+1 all stats"
    else:
        stat_name, stat_gain = next(iter(reward.items()))
        reward_text = f"+{stat_gain} {get_training_focus_label(stat_name)}"

    duration = get_training_duration(duration_minutes)
    return f"Gain: {reward_text} | Cost: {duration.stamina_cost}"


def build_training_menu_embed(
    player: PlayerProfile,
    *,
    selected_focus: str | None = None,
    selected_duration: int | None = None,
) -> discord.Embed:
    location = player.location_data
    reputation_title = get_location_reputation_title(player, player.location)
    focus_text = "Choose a focus below."
    duration_text = "Choose how long you want to train."
    reward_text = "A full plan will show up once both choices are locked in."
    cost_text = "Stamina cost will appear once your session is set."
    description = (
        "Pick your focus, lock in the length of the session, and then commit. "
        "The yard only respects choices you actually follow through on."
    )
    if selected_focus is not None:
        focus_text = get_training_focus_label(selected_focus)
    if selected_focus is not None and selected_duration is not None:
        reward_text = format_training_reward_lines(
            get_training_full_reward(selected_focus, selected_duration)
        )
        duration_text = f"{selected_duration} minutes"
        stamina_cost, stamina_modifier, reputation_title = get_training_stamina_text(
            player,
            selected_duration,
        )
        cost_text = format_reputation_stamina_text(
            stamina_cost,
            stamina_modifier,
            reputation_title,
        )
        description = "Your plan is set. One more press and the training begins for real."
    embed = discord.Embed(
        title=f"\U0001f3cb {location.name} \u2014 Training Setup",
        description=description,
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"\U0001f4cd Location: {location.name}",
            f"\u26a1 Stamina: {player.stamina_current}/{player.stamina_max}",
            f"\U0001f4c8 Level: {player.level}",
            f"\U0001f3ad Reputation: {reputation_title}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Selected Plan",
        value=build_explore_info_lines(
            f"\u2705 Focus: {focus_text}" if selected_focus is not None else f"\u2b1c Focus: {focus_text}",
            f"\u2705 Duration: {duration_text}" if selected_duration is not None else f"\u2b1c Duration: {duration_text}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Projected Gains",
        value=build_explore_info_lines(
            f"\U0001f4c8 Reward: {reward_text}",
            f"\u26a1 Cost: {cost_text}",
        ),
        inline=False,
    )
    if selected_focus is not None and selected_duration is not None:
        embed.add_field(
            name="Ready",
            value="Press **Start Training** to lock in this session and spend the stamina now.",
            inline=False,
        )
    add_explore_divider(embed)
    embed.set_footer(text="Make the choice first. The pain comes after.")
    return embed


def build_training_started_embed(
    player: PlayerProfile,
    training: ActiveTraining,
    *,
    base_stamina_cost: int,
) -> discord.Embed:
    reputation_title = get_location_reputation_title(player, player.location)
    stamina_modifier = training.stamina_cost - base_stamina_cost
    embed = discord.Embed(
        title="\u2705 Training Underway \u2014 Rukongai Training Yard",
        description=(
            "The plan is locked in. Stamina is spent, the session is live, and now the yard gets to see whether you meant it."
        ),
        color=get_explore_color("reward"),
    )
    embed.add_field(
        name="Locked In",
        value=build_explore_info_lines(
            f"\U0001f3af Focus: {get_training_focus_label(training.stat_target)}",
            f"\u23f1 Duration: {training.duration_minutes} minutes",
            f"\U0001f4c8 Reward: {format_training_reward_lines(get_training_full_reward(training.stat_target, training.duration_minutes))}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Cost",
        value=build_explore_info_lines(
            f"\u26a1 Stamina Cost: {format_reputation_stamina_text(training.stamina_cost, stamina_modifier, reputation_title)}",
            f"\u26a1 Stamina After Cost: {player.stamina_current}/{player.stamina_max}",
        ),
        inline=True,
    )
    embed.add_field(
        name="Status",
        value=build_explore_info_lines(
            "\u2705 Training is active now.",
            "\u23f3 The completion result will post here when the session ends.",
            "\u26a1 Passive stamina regeneration is paused until then.",
        ),
        inline=True,
    )
    add_explore_divider(embed)
    embed.set_footer(text="The session has started. The yard is watching now.")
    return embed


def build_training_active_embed(player: PlayerProfile, training: ActiveTraining) -> discord.Embed:
    progress = get_training_progress_snapshot(training)
    embed = discord.Embed(
        title="⚠ Training Already In Progress",
        description="You are already in the middle of a training session.",
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="Current Session",
        value=build_explore_info_lines(
            f"🎯 Focus: {get_training_focus_label(training.stat_target)}",
            f"⏱ Total Duration: {training.duration_minutes} minutes",
            f"⏳ Time Elapsed: {progress.elapsed_minutes} minutes",
            f"⏳ Time Remaining: {progress.remaining_text}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Current Earned Progress",
        value=build_explore_info_lines(
            f"📈 Earned So Far:\n{format_training_reward_lines(progress.earned_reward)}",
            f"⚠ If Stopped Now:\n{format_training_reward_lines(progress.early_stop_reward)}",
            f"⏱ Milestones: {progress.milestones_completed}/{training.duration_minutes // 15}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Decision",
        value="Do you want to continue training or stop early?",
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Discipline holds. Cutting early gives only part of what you earned.")
    return embed


def build_training_complete_embed(resolution: TrainingResolution) -> discord.Embed:
    title = "✅ Training Complete"
    description = "You push through the session and come out stronger than you were before."
    if resolution.was_early_stop:
        title = "⚠ Training Stopped Early"
        description = "You cut the session short before the full gains could settle in."

    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color("reward" if not resolution.was_early_stop else "choice"),
    )
    embed.add_field(
        name="Results",
        value=format_training_reward_lines(resolution.reward),
        inline=False,
    )
    embed.add_field(
        name="Current Totals",
        value=_format_training_current_totals(resolution.player),
        inline=False,
    )
    embed.add_field(
        name="This Session",
        value=build_explore_info_lines(
            f"⏱ Time Trained: {resolution.elapsed_minutes} minutes",
            f"⚡ Stamina Spent: {resolution.training.stamina_cost}",
            f"🎯 Focus: {get_training_focus_label(resolution.training.stat_target)}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Strength that lasts is always paid for up front.")
    return embed


def build_training_resolution_posted_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🏋 Previous Training Posted",
        description="That session had already ended, so I posted the result in the training channel.",
        color=get_explore_color("explore"),
    )
    add_explore_divider(embed)
    return embed


def build_training_blocked_embed(title: str, description: str, *, kind: str = "combat") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color(kind),
    )
    add_explore_divider(embed)
    return embed


def build_training_location_required_embed(player: PlayerProfile) -> discord.Embed:
    training_yard = get_location_definition(TRAINING_YARD_LOCATION_KEY)
    embed = discord.Embed(
        title="🏋 You Need the Training Yard",
        description="This kind of work belongs in the yard, not out in the streets.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Your Location: {player.location_data.name}",
            f"🕓 Training Room: {format_location_room_reference(training_yard)}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_training_wrong_room_embed() -> discord.Embed:
    training_yard = get_location_definition(TRAINING_YARD_LOCATION_KEY)
    embed = discord.Embed(
        title="🏋 Wrong Room",
        description="If you are going to put real work in, do it in the training yard itself.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Required Location: {training_yard.name}",
            f"🕓 Correct Room: {format_location_room_reference(training_yard)}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_training_resting_embed(rest_message: str) -> discord.Embed:
    return build_training_blocked_embed("🏋 You Are Resting", rest_message, kind="explore")


def build_training_wounded_embed() -> discord.Embed:
    return build_training_blocked_embed(
        "Training Is Blocked | Wounded",
        "You are still carrying the aftermath of a blackout. Let the wound settle before you step back into the yard.",
        kind="combat",
    )


def build_training_insufficient_stamina_embed(
    current_stamina: int,
    stamina_max: int,
    required_cost_text: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="🏋 Not Enough Stamina",
        description="You do not have enough left in you to get through that session.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"⚡ Current Stamina: {current_stamina}/{stamina_max}",
            f"⚡ Training Cost: {required_cost_text}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_training_missing_profile_embed() -> discord.Embed:
    return build_training_blocked_embed(
        "🏋 No Soul Record Found",
        "You need to use `/start` before you can train.",
    )


class TrainingFocusSelect(discord.ui.Select["TrainingSetupView"]):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Power", value="power", description="Build raw striking power."),
            discord.SelectOption(label="Defense", value="defense", description="Harden yourself against punishment."),
            discord.SelectOption(label="Speed", value="speed", description="Sharpen movement and reactions."),
            discord.SelectOption(label="Reiatsu", value="reiatsu", description="Pull harder on spiritual force."),
            discord.SelectOption(label="All Stats", value=ALL_STATS_KEY, description="A long balanced session across the board."),
        ]
        super().__init__(
            placeholder="Choose a training focus",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.set_focus(interaction, self.values[0])


class TrainingDurationSelect(discord.ui.Select["TrainingSetupView"]):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Choose a duration",
            min_values=1,
            max_values=1,
            options=[],
            disabled=True,
        )

    def refresh_options(self, focus_key: str | None) -> None:
        self.disabled = focus_key is None
        if focus_key is None:
            self.options = [
                discord.SelectOption(
                    label="Choose a focus first",
                    value="locked",
                    description="Pick what you want to train before setting the duration.",
                )
            ]
            return

        self.options = [
            discord.SelectOption(
                label=f"{duration.minutes} minutes",
                value=str(duration.minutes),
                description=_format_duration_option_description(
                    focus_key,
                    duration.minutes,
                ),
            )
            for duration in get_training_duration_options(focus_key)
        ]

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.set_duration(interaction, int(self.values[0]))


class StartTrainingButton(discord.ui.Button["TrainingSetupView"]):
    def __init__(self) -> None:
        super().__init__(
            label="Start Training",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.start_selected_training(interaction)


class TrainingSetupView(discord.ui.View):
    def __init__(
        self,
        bot: "BleachBot",
        owner_id: int,
        player: PlayerProfile,
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.player = player
        self.selected_focus: str | None = None
        self.selected_duration: int | None = None
        self.message: discord.Message | None = None
        self.focus_select = TrainingFocusSelect()
        self.duration_select = TrainingDurationSelect()
        self.start_button = StartTrainingButton()
        self.duration_select.refresh_options(None)
        self.add_item(self.focus_select)
        self.add_item(self.duration_select)
        self.add_item(self.start_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This training setup belongs to another player. Use `/train` to open your own.",
            ephemeral=True,
        )
        return False

    def _refresh_controls(self) -> None:
        self.duration_select.refresh_options(self.selected_focus)
        if self.selected_focus is not None and self.selected_duration is not None:
            if not is_valid_training_selection(self.selected_focus, self.selected_duration):
                self.selected_duration = None

        is_ready = (
            self.selected_focus is not None
            and self.selected_duration is not None
            and is_valid_training_selection(self.selected_focus, self.selected_duration)
        )
        self.start_button.disabled = not is_ready
        self.start_button.style = (
            discord.ButtonStyle.success if is_ready else discord.ButtonStyle.secondary
        )
        self.focus_select.placeholder = (
            f"Focus: {get_training_focus_label(self.selected_focus)}"
            if self.selected_focus is not None
            else "Choose a training focus"
        )
        self.duration_select.placeholder = (
            f"Duration: {self.selected_duration} minutes"
            if self.selected_duration is not None
            else "Choose a duration"
        )
        self.start_button.label = (
            f"Start {self.selected_duration}m {get_training_focus_label(self.selected_focus)}"
            if is_ready
            else "Start Training"
        )

    async def set_focus(self, interaction: discord.Interaction, focus_key: str) -> None:
        self.selected_focus = focus_key
        if self.selected_duration is not None and not is_valid_training_selection(
            focus_key,
            self.selected_duration,
        ):
            self.selected_duration = None

        self._refresh_controls()
        await interaction.response.edit_message(
            embed=build_training_menu_embed(
                self.player,
                selected_focus=self.selected_focus,
                selected_duration=self.selected_duration,
            ),
            view=self,
        )

    async def set_duration(self, interaction: discord.Interaction, duration_minutes: int) -> None:
        self.selected_duration = duration_minutes
        self._refresh_controls()
        await interaction.response.edit_message(
            embed=build_training_menu_embed(
                self.player,
                selected_focus=self.selected_focus,
                selected_duration=self.selected_duration,
            ),
            view=self,
        )

    async def start_selected_training(self, interaction: discord.Interaction) -> None:
        if self.selected_focus is None or self.selected_duration is None:
            await interaction.response.send_message(
                "Choose both a focus and a duration first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        result = await start_training(
            self.bot.db_pool,
            interaction.user.id,
            interaction.channel_id,
            self.selected_focus,
            self.selected_duration,
        )

        if result.status == "started" and result.player is not None and result.training is not None:
            self.stop()
            schedule_training_task(self.bot, result.training)
            await interaction.message.edit(
                embed=build_training_started_embed(
                    result.player,
                    result.training,
                    base_stamina_cost=get_training_duration(result.training.duration_minutes).stamina_cost,
                ),
                view=None,
            )
            quest_updates = await record_quest_action(
                self.bot.db_pool,
                interaction.user.id,
                "training_started",
            )
            for update in quest_updates:
                await interaction.followup.send(
                    embed=build_quest_update_embed(update),
                    ephemeral=True,
                )
                if update.status == "completed" and update.stat_points_gained > 0:
                    await send_stat_allocation_prompt(
                        interaction,
                        db_pool=self.bot.db_pool,
                        owner_id=interaction.user.id,
                        source_title="Tutorial Reward | Allocate Your 5 Stat Points",
                    )
            return

        if result.status == "active_training" and result.player is not None and result.training is not None:
            self.stop()
            interrupt_view = TrainingInterruptView(
                bot=self.bot,
                owner_id=self.owner_id,
                player=result.player,
                training=result.training,
            )
            await interaction.message.edit(
                embed=build_training_active_embed(result.player, result.training),
                view=interrupt_view,
            )
            interrupt_view.message = interaction.message
            return

        if result.status == "finished":
            self.stop()
            resolution = await resolve_and_post_training(self.bot, interaction.user.id)
            await interaction.message.edit(
                embed=build_training_resolution_posted_embed() if resolution is not None else build_training_blocked_embed(
                    "🏋 Training Resolution Failed",
                    "The session should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "active_work" and result.player is not None and result.work is not None:
            from src.services.work_service import resolve_and_post_work
            from src.ui.work_view import build_work_active_embed, build_work_resolution_posted_embed

            self.stop()
            if result.work.end_time > datetime.now(timezone.utc):
                await interaction.message.edit(
                    embed=build_work_active_embed(result.player, result.work),
                    view=None,
                )
                return

            resolution = await resolve_and_post_work(self.bot, interaction.user.id)
            await interaction.message.edit(
                embed=build_work_resolution_posted_embed() if resolution is not None else build_training_blocked_embed(
                    "Work Resolution Failed",
                    "That shift should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "resting" and result.player is not None:
            rest_status = get_rest_status(result.player)
            self.stop()
            await interaction.message.edit(
                embed=build_training_resting_embed(
                    build_resting_block_message(result.player, rest_status)
                ),
                view=None,
            )
            return

        if result.status == "wounded":
            self.stop()
            await interaction.message.edit(
                embed=build_training_wounded_embed(),
                view=None,
            )
            return

        if result.status == "insufficient_stamina" and result.player is not None:
            _, stamina_modifier, reputation_title = get_training_stamina_text(
                result.player,
                self.selected_duration,
            )
            self.stop()
            await interaction.message.edit(
                embed=build_training_insufficient_stamina_embed(
                    result.player.stamina_current,
                    result.player.stamina_max,
                    format_reputation_stamina_text(result.stamina_cost, stamina_modifier, reputation_title),
                ),
                view=None,
            )
            return

        if result.status == "active_exploration" and result.player is not None and result.exploration is not None:
            self.stop()
            if result.exploration.end_time > datetime.now(timezone.utc):
                await interaction.message.edit(
                    embed=build_training_blocked_embed(
                        "🏋 You Are Already Out There",
                        "Finish the exploration you already committed to before you try to train.",
                        kind="explore",
                    ),
                    view=None,
                )
                return

            from src.services.exploration_service import resolve_and_post_exploration

            resolution = await resolve_and_post_exploration(self.bot, interaction.user.id)
            await interaction.message.edit(
                embed=build_explore_resolution_posted_embed(resolution.status) if resolution is not None else build_training_blocked_embed(
                    "🏋 Previous Exploration Is Still Tangled",
                    "That run should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "active_travel" and result.player is not None and result.travel is not None:
            self.stop()
            if result.travel.end_time > datetime.now(timezone.utc):
                await interaction.message.edit(
                    embed=build_travel_active_embed(result.player, result.travel),
                    view=None,
                )
                return

            from src.services.travel_service import resolve_and_post_travel

            resolution = await resolve_and_post_travel(self.bot, interaction.user.id)
            await interaction.message.edit(
                embed=build_travel_resolution_posted_embed(resolution) if resolution is not None else build_training_blocked_embed(
                    "🏋 Travel Resolution Failed",
                    "The trip ended, but I could not settle the arrival cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "pending_choice":
            self.stop()
            await interaction.message.edit(
                embed=build_training_blocked_embed(
                    "🏋 A Street Decision Is Still Waiting",
                    "Settle the choice still hanging over your last run before you try to train.",
                    kind="choice",
                ),
                view=None,
            )
            return

        if result.status == "active_combat" and result.player is not None:
            self.stop()
            active_combat = await get_active_exploration_combat(self.bot.db_pool, interaction.user.id)
            await interaction.message.edit(
                embed=build_active_combat_embed(active_combat, interaction.user) if active_combat is not None else build_training_blocked_embed(
                    "🏋 A Fight Is Already On You",
                    "Finish the live fight before you try to focus on training.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "invalid_selection":
            self.stop()
            await interaction.message.edit(
                embed=build_training_blocked_embed(
                    "🏋 Invalid Training Plan",
                    "That focus and duration do not fit together. All Stats is only available for a 60 minute session.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "wrong_location" and result.player is not None:
            self.stop()
            await interaction.message.edit(
                embed=build_training_location_required_embed(result.player),
                view=None,
            )
            return

        self.stop()
        await interaction.message.edit(
            embed=build_training_missing_profile_embed(),
            view=None,
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ContinueTrainingButton(discord.ui.Button["TrainingInterruptView"]):
    def __init__(self) -> None:
        super().__init__(label="Continue Training", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.continue_training(interaction)


class StopEarlyButton(discord.ui.Button["TrainingInterruptView"]):
    def __init__(self) -> None:
        super().__init__(label="Stop Early", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.stop_early(interaction)


class TrainingInterruptView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BleachBot",
        owner_id: int,
        player: PlayerProfile,
        training: ActiveTraining,
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.player = player
        self.training = training
        self.message: discord.Message | None = None
        self.add_item(ContinueTrainingButton())
        self.add_item(StopEarlyButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This training prompt belongs to another player. Use `/train` to check your own session.",
            ephemeral=True,
        )
        return False

    async def continue_training(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        current_training = await get_active_training(self.bot.db_pool, interaction.user.id)
        if current_training is None:
            self.stop()
            await interaction.message.edit(
                embed=build_training_resolution_posted_embed(),
                view=None,
            )
            return
        if current_training.end_time <= datetime.now(timezone.utc):
            tracked_task = self.bot.training_tasks.pop(interaction.user.id, None)
            if tracked_task is not None:
                tracked_task.cancel()
            self.stop()
            resolution = await resolve_and_post_training(self.bot, interaction.user.id)
            await interaction.message.edit(
                embed=build_training_resolution_posted_embed() if resolution is not None else build_training_blocked_embed(
                    "Training Resolution Failed",
                    "The session should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return
        self.stop()
        await interaction.message.edit(
            embed=build_training_active_embed(self.player, current_training),
            view=None,
        )
    async def stop_early(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        current_training = await get_active_training(self.bot.db_pool, interaction.user.id)
        if current_training is None:
            self.stop()
            await interaction.message.edit(
                embed=build_training_resolution_posted_embed(),
                view=None,
            )
            return
        if current_training.end_time <= datetime.now(timezone.utc):
            tracked_task = self.bot.training_tasks.pop(interaction.user.id, None)
            if tracked_task is not None:
                tracked_task.cancel()
            self.stop()
            resolution = await resolve_and_post_training(self.bot, interaction.user.id)
            await interaction.message.edit(
                embed=build_training_resolution_posted_embed() if resolution is not None else build_training_blocked_embed(
                    "Training Resolution Failed",
                    "The session should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return
        tracked_task = self.bot.training_tasks.pop(interaction.user.id, None)
        if tracked_task is not None:
            tracked_task.cancel()
        resolution = await resolve_training(
            self.bot.db_pool,
            interaction.user.id,
            early_stop=True,
        )
        self.stop()
        await interaction.message.edit(
            embed=build_training_complete_embed(resolution) if resolution is not None else build_training_blocked_embed(
                "Early Stop Failed",
                "I could not settle that training session cleanly just yet.",
                kind="combat",
            ),
            view=None,
        )
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
