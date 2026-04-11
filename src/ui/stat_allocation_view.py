from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.models.player import PlayerProfile
from src.services.formulas import (
    calculate_total_core_stats,
    get_remaining_stat_capacity,
    get_total_stat_cap_for_level,
)
from src.services.player_service import get_player_profile
from src.services.stat_allocation_service import allocate_stat_point
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


STAT_LABELS = {
    "power": "Power",
    "defense": "Defense",
    "speed": "Speed",
    "reiatsu": "Reiatsu",
}


def build_stat_allocation_embed(player: PlayerProfile, *, source_title: str = "Stat Allocation") -> discord.Embed:
    total_cap = get_total_stat_cap_for_level(player.level)
    total_spent = calculate_total_core_stats(
        player.power,
        player.defense,
        player.speed,
        player.reiatsu,
    )
    remaining_capacity = get_remaining_stat_capacity(
        level=player.level,
        power=player.power,
        defense=player.defense,
        speed=player.speed,
        reiatsu=player.reiatsu,
    )
    title = source_title if player.unspent_stat_points > 0 else "Stat Allocation Complete"
    description = (
        "Spend your newly earned stat points now. Each point uses your shared level cap."
        if player.unspent_stat_points > 0
        else "All available stat points have been assigned."
    )
    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color("reward" if player.unspent_stat_points <= 0 else "choice"),
    )
    embed.add_field(
        name="Available",
        value=build_explore_info_lines(
            f"Unspent Points: **{player.unspent_stat_points}**",
            f"Shared Cap Space: **{remaining_capacity}**",
            f"Stat Pool: **{total_spent}/{total_cap}**",
        ),
        inline=False,
    )
    embed.add_field(
        name="Current Stats",
        value=build_explore_info_lines(
            f"Power: **{player.power}**",
            f"Defense: **{player.defense}**",
            f"Speed: **{player.speed}**",
            f"Reiatsu: **{player.reiatsu}**",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="These points count toward your shared level-based stat cap.")
    return embed


class AllocateStatButton(discord.ui.Button["StatAllocationView"]):
    def __init__(self, stat_name: str, label: str) -> None:
        super().__init__(label=f"+1 {label}", style=discord.ButtonStyle.secondary)
        self.stat_name = stat_name

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.allocate(interaction, self.stat_name)


class StatAllocationView(discord.ui.View):
    def __init__(
        self,
        *,
        db_pool,
        owner_id: int,
        player: PlayerProfile,
        source_title: str = "Stat Allocation",
    ) -> None:
        super().__init__(timeout=300)
        self.db_pool = db_pool
        self.owner_id = owner_id
        self.player = player
        self.source_title = source_title
        self.message: discord.Message | None = None
        self._rebuild()

    def _rebuild(self) -> None:
        self.clear_items()
        for stat_name, label in STAT_LABELS.items():
            button = AllocateStatButton(stat_name, label)
            button.disabled = self.player.unspent_stat_points <= 0
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This stat allocation panel belongs to another player.",
            ephemeral=True,
        )
        return False

    async def allocate(self, interaction: discord.Interaction, stat_name: str) -> None:
        result = await allocate_stat_point(
            self.db_pool,
            user_id=interaction.user.id,
            stat_name=stat_name,
            points=1,
        )
        if result.player is None:
            await interaction.response.send_message(
                "I couldn't update your stats right now.",
                ephemeral=True,
            )
            return

        self.player = result.player
        self._rebuild()
        embed = build_stat_allocation_embed(self.player, source_title=self.source_title)
        if result.status == "allocated" and result.stat_name is not None:
            embed.add_field(
                name="Applied",
                value=build_explore_info_lines(
                    f"Spent: **{result.points_spent}** point into **{STAT_LABELS[result.stat_name]}**",
                    f"Points Left: **{result.remaining_points}**",
                ),
                inline=False,
            )
        elif result.status == "cap_reached":
            embed.add_field(
                name="Blocked",
                value="You have no shared stat cap space left for this level.",
                inline=False,
            )
        elif result.status == "no_points":
            embed.add_field(
                name="Blocked",
                value="You do not have any unspent stat points left.",
                inline=False,
            )

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class OpenStatAllocationButton(discord.ui.Button["ProfileStatAccessView"]):
    def __init__(self) -> None:
        super().__init__(label="Allocate Stat Points", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.open_allocation(interaction)


class ProfileStatAccessView(discord.ui.View):
    def __init__(
        self,
        *,
        db_pool,
        owner_id: int,
        player: PlayerProfile,
    ) -> None:
        super().__init__(timeout=180)
        self.db_pool = db_pool
        self.owner_id = owner_id
        self.player = player
        self.message: discord.Message | None = None
        self.add_item(OpenStatAllocationButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "This stat prompt belongs to another player.",
            ephemeral=True,
        )
        return False

    async def open_allocation(self, interaction: discord.Interaction) -> None:
        refreshed_player = await get_player_profile(self.db_pool, self.owner_id)
        if refreshed_player is None:
            await interaction.response.send_message(
                "I couldn't load your profile right now.",
                ephemeral=True,
            )
            return

        allocation_view = StatAllocationView(
            db_pool=self.db_pool,
            owner_id=self.owner_id,
            player=refreshed_player,
            source_title="Allocate Unspent Stat Points",
        )
        await interaction.response.send_message(
            embed=build_stat_allocation_embed(refreshed_player, source_title="Allocate Unspent Stat Points"),
            view=allocation_view,
            ephemeral=True,
        )
        allocation_view.message = await interaction.original_response()


async def send_stat_allocation_prompt(
    interaction: discord.Interaction,
    *,
    db_pool,
    owner_id: int,
    source_title: str,
) -> None:
    refreshed_player = await get_player_profile(db_pool, owner_id)
    if refreshed_player is None or refreshed_player.unspent_stat_points <= 0:
        return

    allocation_view = StatAllocationView(
        db_pool=db_pool,
        owner_id=owner_id,
        player=refreshed_player,
        source_title=source_title,
    )
    message = await interaction.followup.send(
        embed=build_stat_allocation_embed(refreshed_player, source_title=source_title),
        view=allocation_view,
        ephemeral=True,
        wait=True,
    )
    allocation_view.message = message
