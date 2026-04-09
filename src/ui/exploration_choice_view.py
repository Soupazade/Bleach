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
from src.ui.explore_embed_style import (
    add_explore_divider,
    build_explore_info_lines,
    format_option_preview,
    get_explore_color,
)
from src.ui.exploration_combat_view import ExplorationCombatView, build_exploration_combat_embed

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
    color = get_explore_color("choice")
    footer_text = "Choose fast. Rukongai never waits for anyone."
    title_prefix = "🟨"
    if prompt.prompt_kind == "special_offer":
        color = get_explore_color("special")
        title_prefix = "🟪"
        if prompt.stamina_cost > 0:
            footer_text = (
                f"Engaging costs an extra {prompt.stamina_cost} stamina "
                f"({prompt.stamina_cost_modifier:+d} from {prompt.reputation_title} reputation)."
                if prompt.stamina_cost_modifier != 0
                else f"Engaging costs an extra {prompt.stamina_cost} stamina."
            )
        else:
            footer_text = "Engaging costs extra stamina."
    elif prompt.prompt_kind == "special_event":
        color = get_explore_color("special")
        title_prefix = "🟪"
        footer_text = "The opening turned ugly fast."
    elif prompt.prompt_kind == "npc_event":
        color = get_explore_color("choice")
        title_prefix = "🟨"
        footer_text = "In Rukongai, the same faces find you again."

    embed = discord.Embed(
        title=f"{title_prefix} {prompt.event_title}",
        description=prompt.description,
        color=color,
    )
    embed.add_field(
        name="What do you do?",
        value="\n".join(
            format_option_preview(option.label, option.style)
            for option in prompt.options
        ),
        inline=False,
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"🧭 Moment: **{prompt.step_title}**",
            f"⏱ Step: **{prompt.step_number}/{prompt.total_steps}**",
        ),
        inline=True,
    )
    embed.add_field(
        name="Timing",
        value=build_explore_info_lines(
            f"🧭 Approach: **{approach.label}**",
            f"🕓 Started: {discord.utils.format_dt(exploration.start_time, 'R')}",
        ),
        inline=True,
    )
    add_explore_divider(embed)
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
                "That moment in the street has already passed.",
                ephemeral=True,
            )
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass
            return

        if message_session.user_id != interaction.user.id:
            await interaction.response.send_message(
                "That choice belongs to someone else.",
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
                "I could not settle that street choice right now.",
                ephemeral=True,
            )
            return

        if result.status == "advanced" and result.prompt is not None:
            await interaction.response.edit_message(
                embed=build_exploration_choice_embed(result.prompt),
                view=ExplorationChoiceView(self.bot, result.prompt),
            )
            return

        if result.status == "combat" and result.combat is not None:
            await interaction.response.edit_message(
                embed=build_exploration_combat_embed(result.combat),
                view=ExplorationCombatView(self.bot),
            )
            return

        if result.status == "insufficient_stamina":
            await interaction.response.send_message(
                f"You need **{result.required_stamina} stamina** left in you to chase this opening.",
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
            "I could not settle that street choice right now.",
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
