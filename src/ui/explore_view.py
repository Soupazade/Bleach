from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.data.exploration import ExploreApproachDefinition, get_explore_approach, get_location_exploration_definition
from src.data.locations import get_location_definition
from src.models.exploration import ActiveExploration
from src.models.player import PlayerProfile
from src.services.exploration_service import (
    get_exploration_remaining_time,
    resolve_and_post_exploration,
    schedule_exploration_task,
    start_exploration,
)
from src.services.player_service import build_resting_block_message
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
    embed.add_field(
        name="What do you do?",
        value="Choose your move in the district.",
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text=location_exploration.menu_footer)
    return embed


def build_explore_started_embed(
    player: PlayerProfile,
    exploration: ActiveExploration,
    *,
    stamina_cost: int,
    base_stamina_cost: int,
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
            f"🧭 Approach: {approach.label}",
            f"⏱ Duration: {approach.duration_minutes} minutes",
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
            f"🧭 Approach: {approach.label}",
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
            f"🕓 Correct Room: <#{location.room_id}>",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Explore where your feet actually are.")
    return embed


class ExploreSelect(discord.ui.Select["ExploreView"]):
    def __init__(self, approaches: tuple[ExploreApproachDefinition, ...]) -> None:
        super().__init__(
            placeholder="Choose your move in the district",
            min_values=1,
            max_values=1,
            options=[
                *[
                    discord.SelectOption(
                        label=approach.dropdown_label,
                        value=approach.key,
                        description=approach.menu_description[:100],
                    )
                    for approach in approaches
                ],
                discord.SelectOption(
                    label="Withdraw",
                    value="withdraw",
                    description="Step back and wait for a better opening.",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return

        await self.view.handle_selection(interaction, self.values[0])


class ExploreView(discord.ui.View):
    def __init__(
        self,
        bot: "BleachBot",
        owner_id: int,
        player: PlayerProfile,
        approaches: tuple[ExploreApproachDefinition, ...],
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.player = player
        self.approaches = approaches
        self.message: discord.Message | None = None
        self.add_item(ExploreSelect(approaches))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This exploration menu belongs to another player. Use `/explore` to open your own.",
        )
        return False

    async def handle_selection(self, interaction: discord.Interaction, selected_value: str) -> None:
        if selected_value == "withdraw":
            self.stop()
            await interaction.response.edit_message(embed=build_explore_withdraw_embed(), view=None)
            return

        if interaction.channel_id is None:
            await interaction.response.send_message(
                "I couldn't determine which channel to post the exploration result in.",
            )
            return

        result = await start_exploration(
            self.bot.db_pool,
            interaction.user.id,
            interaction.channel_id,
            selected_value,
        )

        if result.status == "started" and result.player is not None and result.exploration is not None:
            schedule_exploration_task(self.bot, result.exploration)
            self.stop()
            await interaction.response.edit_message(
                embed=build_explore_started_embed(
                    result.player,
                    result.exploration,
                    stamina_cost=result.stamina_cost,
                    base_stamina_cost=result.base_stamina_cost,
                ),
                view=None,
            )
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
            self.stop()
            await interaction.response.edit_message(
                embed=build_explore_resting_embed(
                    build_resting_block_message(
                        result.player,
                        result.rest_minutes,
                        result.rest_recovery,
                    )
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
