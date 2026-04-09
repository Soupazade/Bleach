from __future__ import annotations

import discord

from src.models.player import PlayerProfile
from src.services.formulas import (
    calculate_effective_damage_power,
    calculate_effective_defense,
    calculate_effective_hp_max,
    calculate_effective_mana_max,
    calculate_effective_speed,
    calculate_effective_stamina_max,
)
from src.services.player_service import get_player_profile, get_rest_status

PROFILE_PAGE_OPTIONS = (
    {
        "label": "Overview",
        "value": "overview",
        "description": "General character overview",
    },
    {
        "label": "Stats",
        "value": "stats",
        "description": "Core and derived stats",
    },
    {
        "label": "Formulas",
        "value": "formulas",
        "description": "See calculated values",
    },
    {
        "label": "Trait",
        "value": "trait",
        "description": "Inspect your Soul Trait",
    },
    {
        "label": "Progression",
        "value": "progression",
        "description": "Level, rank, and timeline info",
    },
)


def build_profile_embed(
    player: PlayerProfile,
    discord_user: discord.abc.User,
    page_key: str,
) -> discord.Embed:
    trait = player.trait_data
    location = player.location_data
    room_mention = f"<#{location.room_id}>"
    rest_minutes, recovered_stamina = get_rest_status(player)
    status_value = "Resting" if player.is_resting else "Available"

    embed = discord.Embed(
        title=f"{discord_user.display_name}'s Soul Record",
        color=discord.Color.from_rgb(25, 120, 255),
    )
    embed.set_thumbnail(url=discord_user.display_avatar.url)
    embed.set_footer(text="Bleach RPG | Reiryoku Archive")

    if page_key == "stats":
        embed.description = (
            "Your reiatsu is still young, but every battle, event, and step through Rukongai "
            "will shape the stats that define your soul."
        )
        embed.add_field(
            name="Core Stats",
            value=(
                f"Power: **{player.power}**\n"
                f"Defense: **{player.defense}**\n"
                f"Speed: **{player.speed}**\n"
                f"Reiatsu: **{player.reiatsu}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Resources",
            value=(
                f"HP: **{player.hp_current}/{player.hp_max}**\n"
                f"Stamina: **{player.stamina_current}/{player.stamina_max}**\n"
                f"Mana: **{player.mana_current}/{player.mana_max}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Derived",
            value=f"Spiritual Pressure: **{player.spiritual_pressure}**",
            inline=False,
        )
        if player.is_resting:
            embed.add_field(
                name="Rest Status",
                value=(
                    "Status: **Resting**\n"
                    f"Resting Since: **{rest_minutes} minute(s) ago**\n"
                    f"Projected Recovery: **+{recovered_stamina} stamina**"
                ),
                inline=False,
            )
        return embed

    if page_key == "formulas":
        effective_hp = calculate_effective_hp_max(player.hp_max, trait)
        effective_stamina = calculate_effective_stamina_max(player.stamina_max, trait)
        effective_mana = calculate_effective_mana_max(player.mana_max, trait)
        effective_power = calculate_effective_damage_power(player.power, trait)
        effective_defense = calculate_effective_defense(player.defense, trait)
        effective_speed = calculate_effective_speed(player.speed, trait)

        embed.description = (
            "These are the current helper formulas powering your profile. "
            "They keep future combat and progression systems easy to expand."
        )
        embed.add_field(
            name="Spiritual Pressure",
            value=(
                "Power + Defense + Speed + Reiatsu\n"
                f"`{player.power} + {player.defense} + {player.speed} + {player.reiatsu}"
                f" = {player.spiritual_pressure}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Trait-Adjusted Values",
            value=(
                f"Effective Max HP: **{effective_hp}**\n"
                f"Effective Max Stamina: **{effective_stamina}**\n"
                f"Effective Max Mana: **{effective_mana}**\n"
                f"Damage Power: **{effective_power}**\n"
                f"Defense Calc: **{effective_defense}**\n"
                f"Speed Calc: **{effective_speed}**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Passive Hooks",
            value=(
                f"Dodge Bonus: **{trait.bonuses.flat_dodge_pct:.0%}**\n"
                f"Stamina Regen Bonus: **{trait.bonuses.stamina_regen_pct:.0%}**\n"
                f"Event Reward Bonus: **{trait.bonuses.event_reward_pct:.0%}**\n"
                f"Defeat Penalty Reduction: **{trait.bonuses.defeat_penalty_reduction_pct:.0%}**"
            ),
            inline=False,
        )
        return embed

    if page_key == "trait":
        bonus_lines = [
            f"Max HP Bonus: **{trait.bonuses.max_hp_pct:.0%}**",
            f"Max Mana Bonus: **{trait.bonuses.max_mana_pct:.0%}**",
            f"Damage Power Bonus: **{trait.bonuses.damage_power_pct:.0%}**",
            f"Speed Calc Bonus: **{trait.bonuses.dodge_spd_pct:.0%}**",
            f"Defense Calc Bonus: **{trait.bonuses.defense_pct:.0%}**",
            f"Max Stamina Bonus: **{trait.bonuses.max_stamina_pct:.0%}**",
            f"Dodge Chance Bonus: **{trait.bonuses.flat_dodge_pct:.0%}**",
            f"Stamina Regen Bonus: **{trait.bonuses.stamina_regen_pct:.0%}**",
            f"Event Reward Bonus: **{trait.bonuses.event_reward_pct:.0%}**",
            (
                "Defeat Penalty Reduction: "
                f"**{trait.bonuses.defeat_penalty_reduction_pct:.0%}**"
            ),
        ]

        embed.description = (
            "Every soul carries a hidden edge. This trait is stored separately from base stats, "
            "so combat and exploration systems can scale without rewriting the profile model."
        )
        embed.add_field(name="Soul Trait", value=f"**{trait.name}**", inline=False)
        embed.add_field(name="Effect", value=trait.effect, inline=False)
        embed.add_field(name="Stored Bonuses", value="\n".join(bonus_lines), inline=False)
        return embed

    if page_key == "progression":
        embed.description = (
            "This page tracks the long road ahead. Ranks, awakenings, events, and future forms can "
            "all grow from this progression base."
        )
        embed.add_field(
            name="Current Progress",
            value=(
                f"Race: **{player.race}**\n"
                f"Rank: **{player.rank}**\n"
                f"Level: **{player.level}**\n"
                f"XP: **{player.xp}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="World State",
            value=(
                f"Location: **{location.name}**\n"
                f"Room: {room_mention}\n"
                f"Created: {discord.utils.format_dt(player.created_at, 'F')}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Foundation Ready",
            value=(
                "Leveling, rank-ups, combat rewards, shops, quests, and evolution trees can be "
                "attached here without reworking the core player table."
            ),
            inline=False,
        )
        return embed

    embed.description = (
        "A wandering soul steps into the Bleach world. Your record below is the foundation for "
        "everything that comes next."
    )
    embed.add_field(
        name="Identity",
        value=(
            f"Race: **{player.race}**\n"
            f"Rank: **{player.rank}**\n"
            f"Trait: **{trait.name}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Progress",
        value=(
            f"Level: **{player.level}**\n"
            f"XP: **{player.xp}**\n"
            f"Spiritual Pressure: **{player.spiritual_pressure}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Status",
        value=(
            f"Status: **{status_value}**\n"
            f"Resting Since: **{rest_minutes} minute(s) ago**\n"
            f"Projected Recovery: **+{recovered_stamina} stamina**"
            if player.is_resting
            else "Status: **Available**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Location",
        value=f"**{location.name}**\nRoom: {room_mention}",
        inline=False,
    )
    embed.add_field(
        name="Resources",
        value=(
            f"HP: **{player.hp_current}/{player.hp_max}**\n"
            f"Stamina: **{player.stamina_current}/{player.stamina_max}**\n"
            f"Mana: **{player.mana_current}/{player.mana_max}**"
        ),
        inline=False,
    )
    return embed


class ProfilePageSelect(discord.ui.Select["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Choose a profile page",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(**option_data) for option_data in PROFILE_PAGE_OPTIONS],
        )

    def set_active(self, page_key: str) -> None:
        for option in self.options:
            option.default = option.value == page_key

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return

        await self.view.change_page(interaction, self.values[0])


class ProfileView(discord.ui.View):
    def __init__(
        self,
        db_pool,
        owner_id: int,
        player: PlayerProfile,
        discord_user: discord.abc.User,
    ) -> None:
        super().__init__(timeout=180)
        self.db_pool = db_pool
        self.owner_id = owner_id
        self.player = player
        self.discord_user = discord_user
        self.message: discord.Message | None = None
        self.page_key = "overview"
        self.page_select = ProfilePageSelect()
        self.page_select.set_active(self.page_key)
        self.add_item(self.page_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "This Soul Record belongs to another player. Use /profile to open your own.",
            ephemeral=True,
        )
        return False

    async def change_page(self, interaction: discord.Interaction, page_key: str) -> None:
        refreshed_player = await get_player_profile(self.db_pool, self.owner_id)
        if refreshed_player is not None:
            self.player = refreshed_player

        self.page_key = page_key
        self.page_select.set_active(page_key)
        embed = build_profile_embed(self.player, self.discord_user, page_key)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
