from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.data.locations import get_location_definition
from src.data.travel import TravelRouteDefinition, get_available_travel_routes, get_travel_route
from src.models.player import PlayerProfile
from src.models.travel import ActiveTravel
from src.services.location_service import format_location_room_reference
from src.services.player_service import build_resting_block_message, get_rest_status
from src.services.reputation_service import format_reputation_stamina_text, get_location_reputation_title
from src.services.travel_service import (
    TravelResolution,
    get_travel_remaining_time,
    resolve_and_post_travel,
    schedule_travel_task,
    start_travel,
)
from src.services.exploration_service import resolve_and_post_exploration
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color
from src.ui.explore_view import (
    build_explore_active_embed,
    build_explore_resolution_posted_embed,
)

if TYPE_CHECKING:
    from src.main import BleachBot


def build_travel_menu_embed(player: PlayerProfile) -> discord.Embed:
    location = player.location_data
    reputation_title = get_location_reputation_title(player, player.location)

    embed = discord.Embed(
        title=f"🧭 {location.name} — Travel",
        description=(
            "The district sprawls farther than a hungry soul ever wants to walk. "
            "Pick your next stretch and move before the day turns on you."
        ),
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
        value="Choose where you want to move next.",
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Every road in Rukongai takes something with it.")
    return embed


def build_travel_started_embed(
    player: PlayerProfile,
    travel: ActiveTravel,
    *,
    base_stamina_cost: int,
) -> discord.Embed:
    source = get_location_definition(travel.source_location)
    destination = get_location_definition(travel.destination_location)
    reputation_title = get_location_reputation_title(player, travel.source_location)
    stamina_modifier = travel.stamina_cost - base_stamina_cost
    duration_minutes = max(1, int((travel.end_time - travel.start_time).total_seconds() // 60))

    embed = discord.Embed(
        title="🧭 You Take the Road",
        description=(
            f"You leave **{source.name}** behind and head for **{destination.name}**. "
            "The walk is not long, but nothing in Rukongai is ever free."
        ),
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Timing",
        value=build_explore_info_lines(
            f"🧭 To: {destination.name}",
            f"⏱ Duration: {duration_minutes} minute{'s' if duration_minutes != 1 else ''}",
            f"🕓 Ends: {discord.utils.format_dt(travel.end_time, 'R')}",
        ),
        inline=True,
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"⚡ Stamina Cost: {format_reputation_stamina_text(travel.stamina_cost, stamina_modifier, reputation_title)}",
            f"⚡ After Travel: **{player.stamina_current}/{player.stamina_max}**",
            f"🎭 Reputation: {reputation_title}",
        ),
        inline=True,
    )
    add_explore_divider(embed)
    embed.set_footer(text="When the road ends, your arrival lands in the district.")
    return embed


def build_travel_active_embed(player: PlayerProfile, travel: ActiveTravel) -> discord.Embed:
    source = get_location_definition(travel.source_location)
    destination = get_location_definition(travel.destination_location)

    embed = discord.Embed(
        title="🧭 You Are Already Moving",
        description="Your feet are already carrying you through the district. Let the road finish what it started.",
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Timing",
        value=build_explore_info_lines(
            f"📍 From: {source.name}",
            f"🧭 To: {destination.name}",
            f"⏱ Time Left: {get_travel_remaining_time(travel)}",
            f"🕓 Ends: {discord.utils.format_dt(travel.end_time, 'R')}",
        ),
        inline=True,
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"⚡ Travel Cost: **{travel.stamina_cost}**",
            f"⚡ Current Stamina: **{player.stamina_current}/{player.stamina_max}**",
            f"🎭 Reputation: {get_location_reputation_title(player, player.location)}",
        ),
        inline=True,
    )
    add_explore_divider(embed)
    embed.set_footer(text="You can act again when the road gives you back to the district.")
    return embed


def build_travel_arrived_embed(resolution: TravelResolution) -> discord.Embed:
    source = get_location_definition(resolution.travel.source_location)
    destination = resolution.player.location_data
    duration_minutes = max(1, int((resolution.travel.end_time - resolution.travel.start_time).total_seconds() // 60))
    embed = discord.Embed(
        title=f"🧭 Arrival — {destination.name}",
        description=(
            f"You come out of **{source.name}** and into **{destination.name}** with the dust of the road still on you. "
            "New lanes. New risks. New chances."
        ),
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="This Move",
        value=build_explore_info_lines(
            f"📍 From: {source.name}",
            f"🧭 To: {destination.name}",
            f"⏱ Duration: {duration_minutes} minute{'s' if duration_minutes != 1 else ''}",
            f"⚡ Stamina Spent: **{resolution.travel.stamina_cost}**",
        ),
        inline=True,
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Location: {destination.name}",
            f"⚡ Stamina: **{resolution.player.stamina_current}/{resolution.player.stamina_max}**",
            f"🎭 Reputation: {get_location_reputation_title(resolution.player, resolution.player.location)}",
        ),
        inline=True,
    )
    if resolution.role_summary is not None:
        embed.add_field(name="Role Update", value=resolution.role_summary, inline=False)
    if resolution.role_warning is not None:
        embed.add_field(name="Role Warning", value=resolution.role_warning, inline=False)
    add_explore_divider(embed)
    embed.set_footer(text="The next part of the district is waiting on you.")
    return embed


def build_travel_resolution_posted_embed(resolution: TravelResolution | None = None) -> discord.Embed:
    description = "Your travel had already finished, so I posted the arrival in the destination district."
    if resolution is not None:
        description = (
            f"Your travel had already finished. You are now in **{resolution.destination_name}**.\n"
            f"Head to {format_location_room_reference(resolution.player.location_data)} to keep moving there."
        )

    embed = discord.Embed(
        title="\U0001f9ed Previous Travel Posted",
        description=description,
        color=get_explore_color("explore"),
    )
    if resolution is not None:
        embed.add_field(
            name="Current State",
            value=build_explore_info_lines(
                f"\U0001f4cd Location: {resolution.destination_name}",
                f"\U0001f553 Correct Room: {format_location_room_reference(resolution.player.location_data)}",
                f"\u26a1 Stamina: **{resolution.player.stamina_current}/{resolution.player.stamina_max}**",
            ),
            inline=False,
        )
    add_explore_divider(embed)
    return embed



def build_travel_wrong_location_embed(player: PlayerProfile) -> discord.Embed:
    location = player.location_data
    embed = discord.Embed(
        title="🧭 Wrong District",
        description=(
            "Your location is already set somewhere else. "
            "Go to the correct room first, then use `/travel` from there."
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
    return embed


def build_travel_blocked_embed(title: str, description: str, *, kind: str = "combat") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color(kind),
    )
    add_explore_divider(embed)
    return embed


def build_travel_resting_embed(rest_message: str) -> discord.Embed:
    return build_travel_blocked_embed("🧭 You Are Resting", rest_message, kind="explore")


def build_travel_insufficient_stamina_embed(
    current_stamina: int,
    stamina_max: int,
    required_cost_text: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="🧭 Not Enough Stamina",
        description="You do not have enough left in you to make that trip right now.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"⚡ Current Stamina: **{current_stamina}/{stamina_max}**",
            f"⚡ Travel Cost: {required_cost_text}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_travel_missing_profile_embed() -> discord.Embed:
    return build_travel_blocked_embed(
        "🧭 No Soul Record Found",
        "You need to use `/start` before you can move through Rukongai.",
    )


class TravelSelect(discord.ui.Select["TravelView"]):
    def __init__(self, routes: tuple[TravelRouteDefinition, ...]) -> None:
        super().__init__(
            placeholder="Choose where to go next",
            min_values=1,
            max_values=1,
            options=[
                *[
                    discord.SelectOption(
                        label=route.dropdown_label,
                        value=route.destination,
                        description=route.description[:100],
                    )
                    for route in routes
                ],
                discord.SelectOption(
                    label="Stay Here",
                    value="stay_put",
                    description="Hold your ground and save your strength.",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return

        await self.view.handle_selection(interaction, self.values[0])


class TravelView(discord.ui.View):
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
        self.routes = get_available_travel_routes(player.location)
        self.message: discord.Message | None = None
        self.add_item(TravelSelect(self.routes))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This travel menu belongs to another player. Use `/travel` to open your own.",
            ephemeral=True,
        )
        return False

    async def handle_selection(self, interaction: discord.Interaction, selected_value: str) -> None:
        if selected_value == "stay_put":
            self.stop()
            await interaction.response.edit_message(
                embed=build_travel_blocked_embed(
                    "🧭 You Hold Your Ground",
                    "You stay where you are and let the district move without you for now.",
                    kind="flavor",
                ),
                view=None,
            )
            return

        if interaction.channel_id is None:
            await interaction.response.send_message(
                "I couldn't determine which channel to post the travel result in.",
            )
            return

        result = await start_travel(
            self.bot.db_pool,
            interaction.user.id,
            interaction.channel_id,
            selected_value,
        )

        if result.status == "started" and result.player is not None and result.travel is not None:
            route = get_travel_route(result.travel.source_location, result.travel.destination_location)
            schedule_travel_task(self.bot, result.travel)
            self.stop()
            await interaction.response.edit_message(
                embed=build_travel_started_embed(
                    result.player,
                    result.travel,
                    base_stamina_cost=route.stamina_cost,
                ),
                view=None,
            )
            return

        if result.status == "active_travel" and result.player is not None and result.travel is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=build_travel_active_embed(result.player, result.travel),
                view=None,
            )
            return

        if result.status == "finished" and result.travel is not None:
            self.stop()
            resolution = await resolve_and_post_travel(self.bot, interaction.user.id)
            if resolution is None:
                await interaction.response.edit_message(
                    embed=build_travel_blocked_embed(
                        "🧭 Travel Resolution Failed",
                        "The trip ended, but I could not settle the arrival cleanly just yet. Try `/travel` again in a moment.",
                    ),
                    view=None,
                )
                return

            await interaction.response.edit_message(
                embed=build_travel_resolution_posted_embed(resolution),
                view=None,
            )
            return

        if result.status == "resting" and result.player is not None:
            rest_status = get_rest_status(result.player)
            self.stop()
            await interaction.response.edit_message(
                embed=build_travel_resting_embed(
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
                embed=build_travel_insufficient_stamina_embed(
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
            if result.exploration.end_time > discord.utils.utcnow():
                await interaction.response.edit_message(
                    embed=build_explore_active_embed(result.player, result.exploration),
                    view=None,
                )
                return

            resolution = await resolve_and_post_exploration(self.bot, interaction.user.id)
            if resolution is not None:
                await interaction.response.edit_message(
                    embed=build_explore_resolution_posted_embed(resolution.status),
                    view=None,
                )
                return

            await interaction.response.edit_message(
                embed=build_travel_blocked_embed(
                    "🧭 Previous Exploration Is Still Tangled",
                    "That run should have been over, but I could not settle it cleanly just yet. Give it another moment.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "pending_choice":
            self.stop()
            await interaction.response.edit_message(
                embed=build_travel_blocked_embed(
                    "🧭 A Street Decision Is Still Waiting",
                    "Finish the choice still hanging over your last run before you try to move on.",
                    kind="choice",
                ),
                view=None,
            )
            return

        if result.status == "active_combat" and result.player is not None:
            self.stop()
            await interaction.response.edit_message(
                embed=build_travel_blocked_embed(
                    "🧭 A Fight Is Already On You",
                    "Finish the live fight first. The road can wait until the danger in front of you is settled.",
                    kind="combat",
                ),
                view=None,
            )
            return

        if result.status == "invalid_route":
            self.stop()
            await interaction.response.edit_message(
                embed=build_travel_blocked_embed(
                    "🧭 That Road Is Not Open",
                    "There is no direct route from this district to that destination yet.",
                    kind="combat",
                ),
                view=None,
            )
            return

        self.stop()
        await interaction.response.edit_message(
            embed=build_travel_missing_profile_embed(),
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

