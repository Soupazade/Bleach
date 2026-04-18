from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.data.exploration import (
    ExploreDurationDefinition,
    ExploreFocusDefinition,
    build_explore_approach_key,
    get_explore_approach,
    get_location_exploration_definition,
    list_explore_durations,
    list_explore_focuses_for_location,
)
from src.data.locations import get_location_definition
from src.models.exploration import ActiveExploration
from src.models.player import PlayerProfile
from src.services.location_service import format_location_room_reference
from src.services.exploration_service import (
    get_exploration_remaining_time,
    resolve_and_post_exploration,
    schedule_exploration_task,
    start_exploration,
)
from src.services.player_service import build_resting_block_message, get_rest_status
from src.services.reputation_service import (
    format_reputation_stamina_text,
    get_location_reputation_title,
)
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines
from src.ui.explore_embed_style import get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


def build_explore_menu_embed(
    player: PlayerProfile,
    *,
    selected_focus: ExploreFocusDefinition | None = None,
) -> discord.Embed:
    location = player.location_data
    location_exploration = get_location_exploration_definition(player.location)
    reputation_title = get_location_reputation_title(player, player.location)

    embed = discord.Embed(
        title=f"🧭 {location_exploration.menu_title} — Exploration",
        description=location_exploration.menu_description,
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Location: {location.name}",
            f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
            f"📈 Level: {player.level}",
            f"🎭 Reputation: {reputation_title}",
        ),
        inline=False,
    )

    if selected_focus is None:
        focus_lines = []
        for focus in list_explore_focuses_for_location(player.location):
            focus_lines.append(
                f"{focus.emoji} **{focus.label}**\n{focus.description}"
            )
        embed.add_field(
            name="🧭 Explore Types",
            value="\n\n".join(focus_lines),
            inline=False,
        )
    else:
        embed.add_field(
            name=f"{selected_focus.emoji} Selected Focus",
            value=build_explore_info_lines(
                f"**{selected_focus.label}**",
                selected_focus.description,
                "Choose a duration below to decide how long you stay out in the district.",
            ),
            inline=False,
        )

    duration_lines = [
        f"{duration.emoji} **{duration.label}**\n{duration.description}"
        for duration in list_explore_durations()
    ]
    embed.add_field(
        name="⏱ Time Commitment",
        value="\n\n".join(duration_lines),
        inline=False,
    )
    add_explore_divider(embed)
    if selected_focus is None:
        embed.set_footer(text="Choose an explore type first, then choose how long you are willing to stay out.")
    else:
        embed.set_footer(text=location_exploration.menu_footer)
    return embed


def build_explore_started_embed(
    player: PlayerProfile,
    exploration: ActiveExploration,
    *,
    stamina_cost: int,
    base_stamina_cost: int,
    duration_minutes: int,
    base_duration_minutes: int,
    wounded_penalty: bool,
) -> discord.Embed:
    location = get_location_definition(exploration.location)
    approach = get_explore_approach(exploration.approach)
    reputation_title = get_location_reputation_title(player, exploration.location)
    stamina_modifier = stamina_cost - base_stamina_cost

    embed = discord.Embed(
        title="🧭 You Step Into the District",
        description=approach.intro_text,
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Timing",
        value=build_explore_info_lines(
            f"{approach.focus_emoji} Focus: {approach.label}",
            f"{approach.duration_emoji} Duration: {approach.duration_minutes} minutes",
            f"🕓 Ends: {discord.utils.format_dt(exploration.end_time, 'R')}",
        ),
        inline=True,
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"⚡ Stamina Cost: {format_reputation_stamina_text(stamina_cost, stamina_modifier, reputation_title)}",
            f"⚡ After Action: **{player.stamina_current}/{player.stamina_max}**",
            f"🎭 Reputation: {reputation_title}",
        ),
        inline=True,
    )
    add_explore_divider(embed)
    embed.set_footer(text="If the streets answer, it happens here.")
    return embed


def build_explore_active_embed(player: PlayerProfile, exploration: ActiveExploration) -> discord.Embed:
    location = get_location_definition(exploration.location)
    approach = get_explore_approach(exploration.approach)
    reputation_title = get_location_reputation_title(player, exploration.location)

    embed = discord.Embed(
        title="🧭 You Are Already Out There",
        description="You have already thrown your lot in with the street. Let that run play out first.",
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Location: {location.name}",
            f"{approach.focus_emoji} Focus: {approach.label}",
            f"{approach.duration_emoji} Duration: {approach.duration_minutes} minutes",
            f"⏱ Time Left: {get_exploration_remaining_time(exploration)}",
            f"🎭 Reputation: {reputation_title}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_explore_withdraw_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🧭 You Stay Put",
        description="You stay where you are and let the night move without you for now.",
        color=get_explore_color("flavor"),
    )
    add_explore_divider(embed)
    return embed


def build_explore_pending_embed(
    event_title: str,
    step_number: int,
    total_steps: int,
    channel_id: int,
) -> discord.Embed:
    embed = discord.Embed(
        title="🟨 A Street Decision Is Waiting",
        description="The district is still waiting on your last call.",
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"Moment: **{event_title}**",
            f"Step: **{step_number}/{total_steps}**",
            f"Channel: <#{channel_id}>",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_explore_resolution_posted_embed(status: str) -> discord.Embed:
    description = "Your previous exploration had already finished, so I posted the outcome in the channel."
    color = get_explore_color("explore")
    if status == "choice_prompt":
        description = "Your previous exploration had already finished, so I posted the next street decision in the channel."
        color = get_explore_color("choice")
    elif status == "combat_prompt":
        description = "Your previous exploration had already finished, so I posted the combat encounter in the channel."
        color = get_explore_color("combat")

    embed = discord.Embed(
        title="🧭 Previous Exploration Posted",
        description=description,
        color=color,
    )
    add_explore_divider(embed)
    return embed


def build_explore_resting_embed(rest_message: str) -> discord.Embed:
    embed = discord.Embed(
        title="🧭 You Are Resting",
        description=rest_message,
        color=get_explore_color("explore"),
    )
    add_explore_divider(embed)
    return embed


def build_explore_insufficient_stamina_embed(
    *,
    current_stamina: int,
    stamina_max: int,
    required_cost_text: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="🧭 Not Enough Stamina",
        description="You do not have enough left in you to step back into the streets.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"Current: **{current_stamina}/{stamina_max}**",
            f"Required: {required_cost_text}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_explore_missing_profile_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🧭 No Soul Record Found",
        description="You need to use `/start` before the streets will know your name.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    return embed


def build_explore_wrong_location_embed(player: PlayerProfile) -> discord.Embed:
    location = player.location_data
    embed = discord.Embed(
        title="🧭 Wrong District",
        description=(
            "The streets do not answer from the wrong corner of the world. "
            "If you want to explore, step into the district where your soul is actually standing."
        ),
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Your Location: {location.name}",
            f"🕓 Correct Room: {format_location_room_reference(location)}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Explore where your feet actually are.")
    return embed


def build_explore_training_yard_embed(player: PlayerProfile) -> discord.Embed:
    location = player.location_data
    embed = discord.Embed(
        title="🧭 The Yard Is for Training",
        description=(
            "There is nothing to explore here. The training yard is for pushing your body, your reiatsu, and your nerve until something gives."
        ),
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Location: {location.name}",
            f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
            "🏋 Try: `/train`",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="If you want growth here, earn it in the yard.")
    return embed


class ExploreFocusSelect(discord.ui.Select["ExploreView"]):
    def __init__(self, *, player: PlayerProfile, selected_focus_key: str | None) -> None:
        super().__init__(
            placeholder="Choose your explore type",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=focus.label,
                    value=focus.key,
                    description=focus.menu_description[:100],
                    emoji=focus.emoji,
                    default=focus.key == selected_focus_key,
                )
                for focus in list_explore_focuses_for_location(player.location)
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.set_focus(interaction, self.values[0])


class ExploreDurationSelect(discord.ui.Select["ExploreView"]):
    def __init__(self, *, selected_focus_key: str | None) -> None:
        super().__init__(
            placeholder="Choose your duration",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=duration.label,
                    value=duration.key,
                    description=duration.description[:100],
                    emoji=duration.emoji,
                )
                for duration in list_explore_durations()
            ],
            disabled=selected_focus_key is None,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.start_selected_exploration(interaction, self.values[0])


class ExploreWithdrawButton(discord.ui.Button["ExploreView"]):
    def __init__(self) -> None:
        super().__init__(label="Withdraw", style=discord.ButtonStyle.secondary, emoji="⬅️")

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        self.view.stop()
        await interaction.response.edit_message(embed=build_explore_withdraw_embed(), view=None)


class ExploreView(discord.ui.View):
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
        self.selected_focus_key: str | None = None
        self.message: discord.Message | None = None
        self._rebuild_components()

    def _get_selected_focus(self) -> ExploreFocusDefinition | None:
        if self.selected_focus_key is None:
            return None
        return next(
            (focus for focus in list_explore_focuses_for_location(self.player.location) if focus.key == self.selected_focus_key),
            None,
        )

    def _rebuild_components(self) -> None:
        self.clear_items()
        self.add_item(ExploreFocusSelect(player=self.player, selected_focus_key=self.selected_focus_key))
        self.add_item(ExploreDurationSelect(selected_focus_key=self.selected_focus_key))
        self.add_item(ExploreWithdrawButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This exploration menu belongs to another player. Use `/explore` to open your own.",
        )
        return False

    async def set_focus(self, interaction: discord.Interaction, focus_key: str) -> None:
        self.selected_focus_key = focus_key
        self._rebuild_components()
        await interaction.response.edit_message(
            embed=build_explore_menu_embed(self.player, selected_focus=self._get_selected_focus()),
            view=self,
        )

    async def start_selected_exploration(self, interaction: discord.Interaction, duration_key: str) -> None:
        if self.selected_focus_key is None:
            await interaction.response.send_message("Choose an explore type first.", ephemeral=True)
            return
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "I couldn't determine which channel to post the exploration result in.",
            )
            return

        approach_key = build_explore_approach_key(
            self.player.location,
            self.selected_focus_key,
            duration_key,
        )

        result = await start_exploration(
            self.bot.db_pool,
            interaction.user.id,
            interaction.channel_id,
            approach_key,
        )

        if result.status == "started" and result.player is not None and result.exploration is not None:
            schedule_exploration_task(self.bot, result.exploration)
            self.stop()
            started_embed = build_explore_started_embed(
                result.player,
                result.exploration,
                stamina_cost=result.stamina_cost,
                base_stamina_cost=result.base_stamina_cost,
                duration_minutes=result.duration_minutes,
                base_duration_minutes=result.base_duration_minutes,
                wounded_penalty=result.wounded_penalty,
            )
            await interaction.response.edit_message(
                embed=started_embed,
                view=None,
            )
            original_message = await interaction.original_response()
            if original_message.flags.ephemeral and interaction.channel is not None and hasattr(interaction.channel, "send"):
                public_message = await interaction.channel.send(
                    content=f"<@{interaction.user.id}>",
                    embed=started_embed,
                )
                self.bot.exploration_message_refs[interaction.user.id] = public_message.id
            else:
                self.bot.exploration_message_refs[interaction.user.id] = original_message.id

            return

        if result.status == "active" and result.player is not None and result.exploration is not None:
            await interaction.response.edit_message(
                embed=build_explore_active_embed(result.player, result.exploration),
                view=None,
            )
            return

        if result.status == "finished" and result.exploration is not None:
            resolution = await resolve_and_post_exploration(self.bot, interaction.user.id)
            self.stop()
            if resolution is None:
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="Resolution Failed",
                        description="The run ended, but I could not pull the result together just yet. Try `/explore` again in a moment.",
                        color=discord.Color.red(),
                    ),
                    view=None,
                )
                return

            await interaction.response.edit_message(
                embed=build_explore_resolution_posted_embed(resolution.status),
                view=None,
            )
            return

        if result.status == "active_work" and result.player is not None and result.work is not None:
            from src.services.work_service import resolve_and_post_work
            from src.ui.work_view import build_work_active_embed, build_work_resolution_posted_embed

            self.stop()
            if result.work.end_time > discord.utils.utcnow():
                await interaction.response.edit_message(
                    embed=build_work_active_embed(result.player, result.work),
                    view=None,
                )
                return

            resolution = await resolve_and_post_work(self.bot, interaction.user.id)
            await interaction.response.edit_message(
                embed=build_work_resolution_posted_embed() if resolution is not None else discord.Embed(
                    title="Resolution Failed",
                    description="That shift should have been over, but I could not settle it cleanly just yet. Try `/explore` again in a moment.",
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return

        if result.status == "pending_choice" and result.pending_choice is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=build_explore_pending_embed(
                    result.pending_choice.event_title,
                    result.pending_choice.step_number,
                    result.pending_choice.total_steps,
                    result.pending_choice.session.channel_id,
                ),
                view=None,
            )
            return

        if result.status == "resting" and result.player is not None:
            rest_status = get_rest_status(result.player)
            self.stop()
            await interaction.response.edit_message(
                embed=build_explore_resting_embed(
                    build_resting_block_message(result.player, rest_status)
                ),
                view=None,
            )
            return

        if result.status == "insufficient_stamina" and result.player is not None:
            reputation_title = get_location_reputation_title(result.player, result.player.location)
            stamina_modifier = result.stamina_cost - result.base_stamina_cost
            self.stop()
            await interaction.response.edit_message(
                embed=build_explore_insufficient_stamina_embed(
                    current_stamina=result.player.stamina_current,
                    stamina_max=result.player.stamina_max,
                    required_cost_text=format_reputation_stamina_text(
                        result.stamina_cost,
                        stamina_modifier,
                        reputation_title,
                    ),
                ),
                view=None,
            )
            return

        self.stop()
        await interaction.response.edit_message(
            embed=build_explore_missing_profile_embed(),
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
