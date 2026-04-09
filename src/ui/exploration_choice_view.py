from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.data.exploration import get_explore_approach
from src.services.exploration_service import (
    ExplorationDecisionPrompt,
    advance_exploration_choice,
    build_exploration_result_embed,
    get_pending_exploration_choice_by_message,
)

if TYPE_CHECKING:
    from src.main import BleachBot


BUTTON_STYLE_MAP = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}


def build_exploration_choice_embed(prompt: ExplorationDecisionPrompt) -> discord.Embed:
    exploration = prompt.session.to_active_exploration()
    approach = get_explore_approach(prompt.session.approach)
    color = discord.Color.from_rgb(88, 112, 168)
    footer_text = "Choose quickly. The streets do not wait."
    if prompt.prompt_kind == "special_offer":
        color = discord.Color.dark_orange()
        footer_text = "Engaging costs an extra 10 stamina."
    elif prompt.prompt_kind == "special_event":
        color = discord.Color.red()
        footer_text = "The opportunity turned dangerous fast."

    embed = discord.Embed(
        title=prompt.event_title,
        description=prompt.description,
        color=color,
    )
    embed.add_field(
        name="Decision",
        value=(
            f"Step: **{prompt.step_number}/{prompt.total_steps}**\n"
            f"Moment: **{prompt.step_title}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Street Run",
        value=(
            f"Approach: **{approach.label}**\n"
            f"Started: {discord.utils.format_dt(exploration.start_time, 'R')}"
        ),
        inline=True,
    )
    embed.set_footer(text=footer_text)
    return embed


class ExplorationChoiceView(discord.ui.View):
    def __init__(
        self,
        bot: "BleachBot",
        prompt: ExplorationDecisionPrompt | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.prompt = prompt
        self._configure_buttons(prompt)

    def _configure_buttons(self, prompt: ExplorationDecisionPrompt | None) -> None:
        buttons = (self.choice_one, self.choice_two, self.choice_three)
        if prompt is None:
            for button in buttons:
                button.disabled = False
            return

        for index, button in enumerate(buttons):
            if index < len(prompt.options):
                option = prompt.options[index]
                button.label = option.label
                button.style = BUTTON_STYLE_MAP[option.style]
                button.disabled = False
            else:
                button.label = "Unavailable"
                button.style = discord.ButtonStyle.secondary
                button.disabled = True

    async def _handle_choice(self, interaction: discord.Interaction, option_slot: int) -> None:
        if interaction.message is None:
            await interaction.response.send_message("That street decision is no longer active.", ephemeral=True)
            return

        message_session = await get_pending_exploration_choice_by_message(self.bot.db_pool, interaction.message.id)
        if message_session is None:
            await interaction.response.send_message(
                "That street decision is no longer active.",
                ephemeral=True,
            )
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass
            return

        if message_session.user_id != interaction.user.id:
            await interaction.response.send_message(
                "This street decision belongs to another player.",
                ephemeral=True,
            )
            return

        result = await advance_exploration_choice(
            self.bot.db_pool,
            message_id=interaction.message.id,
            user_id=interaction.user.id,
            option_slot=option_slot,
        )
        if result.status == "missing":
            await interaction.response.send_message(
                "That street decision could not be resolved right now.",
                ephemeral=True,
            )
            return

        if result.status == "advanced" and result.prompt is not None:
            await interaction.response.edit_message(
                embed=build_exploration_choice_embed(result.prompt),
                view=ExplorationChoiceView(self.bot, result.prompt),
            )
            return

        if result.status == "insufficient_stamina":
            await interaction.response.send_message(
                f"You need **{result.required_stamina} stamina** available to engage this special opportunity.",
                ephemeral=True,
            )
            return

        if result.status == "resolved" and result.resolution is not None:
            await interaction.response.edit_message(
                embed=build_exploration_result_embed(result.resolution),
                view=None,
            )
            return

        await interaction.response.send_message(
            "That street decision could not be resolved right now.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Choice One",
        style=discord.ButtonStyle.primary,
        custom_id="explore_choice:1",
        row=0,
    )
    async def choice_one(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_choice(interaction, 1)

    @discord.ui.button(
        label="Choice Two",
        style=discord.ButtonStyle.secondary,
        custom_id="explore_choice:2",
        row=0,
    )
    async def choice_two(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_choice(interaction, 2)

    @discord.ui.button(
        label="Choice Three",
        style=discord.ButtonStyle.secondary,
        custom_id="explore_choice:3",
        row=0,
    )
    async def choice_three(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_choice(interaction, 3)
