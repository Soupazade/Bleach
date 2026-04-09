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
    get_location_reputation_label,
    get_location_reputation_title,
)

if TYPE_CHECKING:
    from src.main import BleachBot


def build_explore_menu_embed(
    player: PlayerProfile,
) -> discord.Embed:
    location = player.location_data
    location_exploration = get_location_exploration_definition(player.location)
    reputation_label = get_location_reputation_label(player.location)
    reputation_title = get_location_reputation_title(player, player.location)

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
            f"Level: **{player.level}**\n"
            f"{reputation_label}: **{reputation_title}**"
        ),
        inline=False,
    )
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
    reputation_label = get_location_reputation_label(exploration.location)
    reputation_title = get_location_reputation_title(player, exploration.location)
    stamina_modifier = stamina_cost - base_stamina_cost

    embed = discord.Embed(
        title="You Slip Into the District",
        description=(
            f"You make your move in **{location.name}**.\n"
            f"{approach.intro_text}"
        ),
        color=discord.Color.from_rgb(109, 142, 196),
    )
    embed.add_field(
        name="Timing",
        value=(
            f"Approach: **{approach.label}**\n"
            f"It Wraps In: **{approach.duration_label}**\n"
            f"Ends: {discord.utils.format_dt(exploration.end_time, 'R')}"
        ),
        inline=True,
    )
    embed.add_field(
        name="Resources",
        value=(
            f"Stamina Cost: {format_reputation_stamina_text(stamina_cost, stamina_modifier, reputation_title)}\n"
            f"Stamina After Cost: **{player.stamina_current}/{player.stamina_max}**\n"
            f"{reputation_label}: **{reputation_title}**"
        ),
        inline=True,
    )
    embed.set_footer(text="If the streets answer, the result will land here.")
    return embed


def build_explore_active_embed(player: PlayerProfile, exploration: ActiveExploration) -> discord.Embed:
    location = get_location_definition(exploration.location)
    approach = get_explore_approach(exploration.approach)
    reputation_label = get_location_reputation_label(exploration.location)
    reputation_title = get_location_reputation_title(player, exploration.location)

    embed = discord.Embed(
        title="You Are Already Out There",
        description="You have already thrown your lot in with the street. Let that run play out first.",
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Current Run",
        value=(
            f"Approach: **{approach.label}**\n"
            f"Location: **{location.name}**\n"
            f"Time Left: **{get_exploration_remaining_time(exploration)}**\n"
            f"{reputation_label}: **{reputation_title}**"
        ),
        inline=False,
    )
    return embed


def build_explore_withdraw_embed() -> discord.Embed:
    return discord.Embed(
        title="You Stay Put",
        description="You stay where you are and let the night move without you for now.",
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
                embed=discord.Embed(
                    title="Previous Run Posted",
                    description=(
                        "That run had already finished. I posted the outcome in the channel."
                        if resolution.status == "instant"
                        else (
                            "That run had already finished. I posted the next street call in the channel."
                            if resolution.status == "choice_prompt"
                            else "That run had already finished. I posted the fight in the channel."
                        )
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
                        "The streets are still waiting on your last call.\n"
                        f"Moment: **{result.pending_choice.event_title}**\n"
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
            reputation_title = get_location_reputation_title(result.player, result.player.location)
            stamina_modifier = result.stamina_cost - result.base_stamina_cost
            self.stop()
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Not Enough Stamina",
                    description=(
                        "You do not have the stamina to step back into the streets.\n"
                        f"Current Stamina: **{result.player.stamina_current}/{result.player.stamina_max}**\n"
                        f"Required Cost: {format_reputation_stamina_text(result.stamina_cost, stamina_modifier, reputation_title)}"
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
                description="You need to use `/start` before the streets will know your name.",
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
