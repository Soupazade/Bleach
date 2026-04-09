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

if TYPE_CHECKING:
    from src.main import BleachBot


def build_explore_menu_embed(
    player: PlayerProfile,
) -> discord.Embed:
    location = player.location_data
    location_exploration = get_location_exploration_definition(player.location)

    embed = discord.Embed(
        title=f"Explore | {location_exploration.menu_title}",
        description=location_exploration.menu_description,
        color=discord.Color.from_rgb(92, 122, 168),
    )
    embed.add_field(
        name="Current State",
        value=(
            f"Location: **{location.name}**\n"
            f"Stamina: **{player.stamina_current}/{player.stamina_max}**\n"
            f"Level: **{player.level}**"
        ),
        inline=False,
    )
    embed.set_footer(text=location_exploration.menu_footer)
    return embed


def build_explore_started_embed(player: PlayerProfile, exploration: ActiveExploration) -> discord.Embed:
    location = get_location_definition(exploration.location)
    approach = get_explore_approach(exploration.approach)

    embed = discord.Embed(
        title="Exploration Underway",
        description=(
            f"You begin **{approach.label}** in **{location.name}**.\n"
            f"{approach.intro_text}"
        ),
        color=discord.Color.from_rgb(109, 142, 196),
    )
    embed.add_field(
        name="Timing",
        value=(
            f"Result In: **{approach.duration_label}**\n"
            f"Ends: {discord.utils.format_dt(exploration.end_time, 'R')}"
        ),
        inline=True,
    )
    embed.add_field(
        name="Resources",
        value=f"Stamina After Cost: **{player.stamina_current}/{player.stamina_max}**",
        inline=True,
    )
    embed.set_footer(text="Your result will be posted automatically in this channel.")
    return embed


def build_explore_active_embed(exploration: ActiveExploration) -> discord.Embed:
    location = get_location_definition(exploration.location)
    approach = get_explore_approach(exploration.approach)

    embed = discord.Embed(
        title="Exploration Already Active",
        description="You are already out in the district. Hold your nerve and let the run finish.",
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Current Run",
        value=(
            f"Approach: **{approach.label}**\n"
            f"Location: **{location.name}**\n"
            f"Time Left: **{get_exploration_remaining_time(exploration)}**"
        ),
        inline=False,
    )
    return embed


def build_explore_withdraw_embed() -> discord.Embed:
    return discord.Embed(
        title="You Withdraw",
        description="You hold your position and let the district pass by for now.",
        color=discord.Color.dark_grey(),
    )


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
            ephemeral=True,
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
                ephemeral=True,
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
                embed=build_explore_started_embed(result.player, result.exploration),
                view=None,
            )
            return

        if result.status == "active" and result.exploration is not None:
            await interaction.response.edit_message(
                embed=build_explore_active_embed(result.exploration),
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
                        description="I couldn't resolve your finished exploration right now. Please try `/explore` again.",
                        color=discord.Color.red(),
                    ),
                    view=None,
                )
                return

            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Previous Run Posted",
                    description=(
                        "Your previous exploration had already ended. I posted the result in the channel."
                        if resolution.status == "instant"
                        else "Your previous exploration had already ended. I posted a street decision in the channel."
                    ),
                    color=discord.Color.green(),
                ),
                view=None,
            )
            return

        if result.status == "pending_choice" and result.pending_choice is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Street Decision Waiting",
                    description=(
                        "You still have an unresolved exploration decision waiting in the channel.\n"
                        f"Decision: **{result.pending_choice.event_title}**\n"
                        f"Step: **{result.pending_choice.step_number}/{result.pending_choice.total_steps}**\n"
                        f"Channel: <#{result.pending_choice.session.channel_id}>"
                    ),
                    color=discord.Color.orange(),
                ),
                view=None,
            )
            return

        if result.status == "resting" and result.player is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Rest First",
                    description=build_resting_block_message(
                        result.player,
                        result.rest_minutes,
                        result.rest_recovery,
                    ),
                    color=discord.Color.orange(),
                ),
                view=None,
            )
            return

        if result.status == "insufficient_stamina" and result.player is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Not Enough Stamina",
                    description=(
                        "You do not have enough stamina to begin an exploration.\n"
                        f"Current Stamina: **{result.player.stamina_current}/{result.player.stamina_max}**"
                    ),
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return

        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="No Soul Record Found",
                description="You need to use `/start` before you can explore.",
                color=discord.Color.red(),
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
