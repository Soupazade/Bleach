from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

from src.data.locations import RUKONGAI_MARKET, RUKONGAI_STREETS, get_location_definition
from src.data.work import WorkDefinition, get_work_definition, get_work_options_for_location
from src.models.player import PlayerProfile
from src.models.work import ActiveWork
from src.services.combat_service import get_active_exploration_combat
from src.services.location_service import format_location_room_reference
from src.services.player_service import build_resting_block_message, get_rest_status
from src.services.reputation_service import (
    format_reputation_stamina_text,
    get_location_reputation_title,
)
from src.services.work_service import (
    StartWorkResult,
    WorkResolution,
    calculate_work_payout,
    get_active_work,
    get_work_remaining_time,
    get_work_stamina_text,
    resolve_and_post_work,
    schedule_work_task,
    start_work,
)
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color
from src.ui.exploration_combat_view import build_active_combat_embed
from src.ui.explore_view import build_explore_resolution_posted_embed
from src.ui.train_view import build_training_blocked_embed
from src.ui.travel_view import build_travel_active_embed, build_travel_resolution_posted_embed

if TYPE_CHECKING:
    from src.main import BleachBot


def _work_preview_lines(player: PlayerProfile, options: tuple[WorkDefinition, ...]) -> str:
    reputation_value = player.rukongai_rep
    lines: list[str] = []
    for option in options:
        projected_min = option.kan_min
        projected_max = option.kan_max
        if option.alignment == "legit":
            projected_bonus = max(0, reputation_value // 25)
        elif option.alignment == "shady":
            projected_bonus = max(0, abs(min(reputation_value, 0)) // 12)
        elif option.key == "streets_beg_cookfires":
            projected_bonus = max(0, abs(reputation_value) // 30)
        else:
            projected_bonus = 0
        projected_min += projected_bonus
        projected_max += projected_bonus
        lines.append(
            f"**{option.label}** [{option.duration_minutes}m] {option.menu_description}\n"
            f"Pay: {projected_min}-{projected_max} kan | Cost: {option.stamina_cost} stamina"
        )
    return "\n\n".join(lines)


def build_work_menu_embed(player: PlayerProfile) -> discord.Embed:
    location = player.location_data
    reputation_title = get_location_reputation_title(player, player.location)
    options = get_work_options_for_location(player.location)
    embed = discord.Embed(
        title=f"Work - {location.name}",
        description=(
            "Pick the kind of job you can stomach, spend the stamina, and wait out the shift. "
            "In Rukongai, honest work pays badly and dirty work pays in ways that keep following you."
        ),
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"Location: {location.name}",
            f"Stamina: {player.stamina_current}/{player.stamina_max}",
            f"Kan: {player.kan}",
            f"Reputation: {reputation_title}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Available Work",
        value=_work_preview_lines(player, options) if options else "There is no honest or crooked work here right now.",
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Good names get safer work. Bad names get better offers.")
    return embed


def build_work_started_embed(
    player: PlayerProfile,
    work: ActiveWork,
    *,
    base_stamina_cost: int,
) -> discord.Embed:
    job = get_work_definition(work.work_key)
    reputation_title = get_location_reputation_title(player, player.location)
    stamina_modifier = work.stamina_cost - base_stamina_cost
    embed = discord.Embed(
        title="Work Underway",
        description=job.intro_text,
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="Shift",
        value=build_explore_info_lines(
            f"Job: {job.label}",
            f"Duration: {job.duration_minutes} minutes",
            f"Ends: {discord.utils.format_dt(work.end_time, 'R')}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Cost",
        value=build_explore_info_lines(
            f"Stamina Cost: {format_reputation_stamina_text(work.stamina_cost, stamina_modifier, reputation_title)}",
            f"After Cost: {player.stamina_current}/{player.stamina_max} stamina",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="The shift is live now. The pay comes after.")
    return embed


def build_work_active_embed(player: PlayerProfile, work: ActiveWork) -> discord.Embed:
    job = get_work_definition(work.work_key)
    embed = discord.Embed(
        title="Work Already In Progress",
        description="You are already out earning what you can from this district.",
        color=get_explore_color("choice"),
    )
    embed.add_field(
        name="Current Shift",
        value=build_explore_info_lines(
            f"Job: {job.label}",
            f"Location: {get_location_definition(work.location).name}",
            f"Time Remaining: {get_work_remaining_time(work)}",
            f"Ends: {discord.utils.format_dt(work.end_time, 'R')}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_work_complete_embed(resolution: WorkResolution) -> discord.Embed:
    modifier_text = ""
    if resolution.payout_modifier > 0:
        modifier_text = f" ({resolution.payout_modifier:+d} from reputation fit)"
    embed = discord.Embed(
        title=f"Work Complete - {resolution.job.completion_title}",
        description=resolution.job.completion_description,
        color=get_explore_color("reward"),
    )
    embed.add_field(
        name="Pay",
        value=build_explore_info_lines(
            f"Kan Earned: {resolution.kan_earned}{modifier_text}",
            f"Reputation Shift: {resolution.reputation_change:+d}",
            f"Current Kan: {resolution.player.kan}",
        ),
        inline=False,
    )
    embed.add_field(
        name="After Shift",
        value=build_explore_info_lines(
            f"Location: {resolution.player.location_data.name}",
            f"Stamina: {resolution.player.stamina_current}/{resolution.player.stamina_max}",
            f"Job: {resolution.job.label}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Some pay weighs more than it looks.")
    return embed


def build_work_resolution_posted_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Previous Shift Posted",
        description="That job had already finished, so I posted the payout in the channel.",
        color=get_explore_color("explore"),
    )
    add_explore_divider(embed)
    return embed


def build_work_blocked_embed(title: str, description: str, *, kind: str = "combat") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color(kind),
    )
    add_explore_divider(embed)
    return embed


def build_work_location_required_embed(player: PlayerProfile) -> discord.Embed:
    embed = discord.Embed(
        title="You Need The Streets Or Market",
        description="This kind of scraping work only turns up in the Rukongai Streets or Rukongai Market.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"Your Location: {player.location_data.name}",
            f"Work Rooms: {format_location_room_reference(RUKONGAI_STREETS)} and {format_location_room_reference(RUKONGAI_MARKET)}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_work_wrong_room_embed(player: PlayerProfile) -> discord.Embed:
    embed = discord.Embed(
        title="Wrong Room",
        description="If you want work here, you need to stand in the district where your hands are actually getting dirty.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"Required Location: {player.location_data.name}",
            f"Correct Room: {format_location_room_reference(player.location_data)}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_work_resting_embed(rest_message: str) -> discord.Embed:
    return build_work_blocked_embed("You Are Resting", rest_message, kind="explore")


def build_work_insufficient_stamina_embed(
    *,
    current_stamina: int,
    stamina_max: int,
    required_cost_text: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="Not Enough Stamina",
        description="You do not have enough left in you to finish that shift.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"Current: {current_stamina}/{stamina_max}",
            f"Required: {required_cost_text}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_work_missing_profile_embed() -> discord.Embed:
    return build_work_blocked_embed(
        "No Soul Record Found",
        "You need to use `/start` before you can try to earn kan.",
    )


class WorkSelect(discord.ui.Select["WorkView"]):
    def __init__(self, player: PlayerProfile) -> None:
        options = [
            discord.SelectOption(
                label=job.label,
                value=job.key,
                description=f"{job.duration_minutes}m | {job.menu_description}"[:100],
            )
            for job in get_work_options_for_location(player.location)
        ]
        super().__init__(
            placeholder="Choose a job",
            min_values=1,
            max_values=1,
            options=options or [
                discord.SelectOption(
                    label="No work available",
                    value="locked",
                    description="There are no shifts here right now.",
                )
            ],
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None or self.values[0] == "locked":
            return
        await self.view.start_selected_work(interaction, self.values[0])


class WorkWithdrawButton(discord.ui.Button["WorkView"]):
    def __init__(self) -> None:
        super().__init__(label="Walk Away", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        self.view.stop()
        await interaction.response.edit_message(
            embed=build_work_blocked_embed(
                "You Stay Unpaid",
                "You let the district keep its little jobs for somebody else tonight.",
                kind="flavor",
            ),
            view=None,
        )


class WorkView(discord.ui.View):
    def __init__(self, bot: "BleachBot", owner_id: int, player: PlayerProfile) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.player = player
        self.message: discord.Message | None = None
        self.add_item(WorkSelect(player))
        self.add_item(WorkWithdrawButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This work menu belongs to another player. Use `/work` to open your own.",
            ephemeral=True,
        )
        return False

    async def start_selected_work(self, interaction: discord.Interaction, work_key: str) -> None:
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "I could not determine which channel to anchor the shift in.",
                ephemeral=True,
            )
            return

        result = await start_work(
            self.bot.db_pool,
            user_id=interaction.user.id,
            channel_id=interaction.channel_id,
            work_key=work_key,
        )
        await self._handle_start_result(interaction, result, work_key)

    async def _handle_start_result(
        self,
        interaction: discord.Interaction,
        result: StartWorkResult,
        work_key: str,
    ) -> None:
        if result.status == "started" and result.player is not None and result.work is not None:
            self.stop()
            schedule_work_task(self.bot, result.work)
            await interaction.response.edit_message(
                embed=build_work_started_embed(
                    result.player,
                    result.work,
                    base_stamina_cost=get_work_definition(work_key).stamina_cost,
                ),
                view=None,
            )
            return

        if result.status == "active_work" and result.player is not None and result.work is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=build_work_active_embed(result.player, result.work),
                view=None,
            )
            return

        if result.status == "finished":
            self.stop()
            resolution = await resolve_and_post_work(self.bot, interaction.user.id)
            await interaction.response.edit_message(
                embed=build_work_resolution_posted_embed() if resolution is not None else build_work_blocked_embed(
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
            await interaction.response.edit_message(
                embed=build_work_resting_embed(
                    build_resting_block_message(result.player, rest_status)
                ),
                view=None,
            )
            return

        if result.status == "insufficient_stamina" and result.player is not None:
            _, stamina_modifier, reputation_title = get_work_stamina_text(result.player, work_key)
            self.stop()
            await interaction.response.edit_message(
                embed=build_work_insufficient_stamina_embed(
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

        if result.status == "active_exploration" and result.player is not None and result.exploration is not None:
            self.stop()
            if result.exploration.end_time > datetime.now(timezone.utc):
                await interaction.response.edit_message(
                    embed=build_training_blocked_embed(
                        "You Are Already Out There",
                        "Finish the exploration you already committed to before you try to work.",
                        kind="explore",
                    ),
                    view=None,
                )
                return

            from src.services.exploration_service import resolve_and_post_exploration

            resolution = await resolve_and_post_exploration(self.bot, interaction.user.id)
            await interaction.response.edit_message(
                embed=build_explore_resolution_posted_embed(resolution.status) if resolution is not None else build_work_blocked_embed(
                    "Previous Exploration Is Still Tangled",
                    "That run should have been over, but I could not settle it cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "active_travel" and result.player is not None and result.travel is not None:
            self.stop()
            if result.travel.end_time > datetime.now(timezone.utc):
                await interaction.response.edit_message(
                    embed=build_travel_active_embed(result.player, result.travel),
                    view=None,
                )
                return

            from src.services.travel_service import resolve_and_post_travel

            resolution = await resolve_and_post_travel(self.bot, interaction.user.id)
            await interaction.response.edit_message(
                embed=build_travel_resolution_posted_embed(resolution) if resolution is not None else build_work_blocked_embed(
                    "Travel Resolution Failed",
                    "The trip ended, but I could not settle the arrival cleanly just yet.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "active_training" and result.player is not None and result.training is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=build_work_blocked_embed(
                    "Training Is Already Running",
                    "Finish the training session you already committed to before you try to take a shift.",
                    kind="choice",
                ),
                view=None,
            )
            return

        if result.status == "pending_choice":
            self.stop()
            await interaction.response.edit_message(
                embed=build_work_blocked_embed(
                    "A Street Decision Is Still Waiting",
                    "Settle the choice hanging over your last run before you try to work.",
                    kind="choice",
                ),
                view=None,
            )
            return

        if result.status == "active_dungeon":
            self.stop()
            await interaction.response.edit_message(
                embed=build_work_blocked_embed(
                    "The District Already Has You",
                    "Finish the dungeon run you are already inside before you try to take a shift.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "active_combat" and result.player is not None:
            self.stop()
            active_combat = await get_active_exploration_combat(self.bot.db_pool, interaction.user.id)
            await interaction.response.edit_message(
                embed=build_active_combat_embed(active_combat, interaction.user) if active_combat is not None else build_work_blocked_embed(
                    "A Fight Is Already On You",
                    "Finish the live fight before you try to work.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "wrong_location" and result.player is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=build_work_location_required_embed(result.player),
                view=None,
            )
            return

        if result.status == "invalid_work":
            self.stop()
            await interaction.response.edit_message(
                embed=build_work_blocked_embed(
                    "Invalid Shift",
                    "That job is no longer available here.",
                    kind="combat",
                ),
                view=None,
            )
            return

        self.stop()
        await interaction.response.edit_message(
            embed=build_work_missing_profile_embed(),
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
