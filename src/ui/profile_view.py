from __future__ import annotations

import discord

from src.models.effects import PlayerEffect
from src.models.player import PlayerProfile
from src.services.effect_service import list_active_player_effects, summarize_active_effects
from src.services.formulas import (
    calculate_effective_damage_power,
    calculate_effective_defense,
    calculate_effective_hp_max,
    calculate_effective_mana_max,
    calculate_effective_speed,
    calculate_effective_stamina_max,
    calculate_total_core_stats,
    get_remaining_stat_capacity,
    get_total_stat_cap_for_level,
    get_xp_required_for_level,
    is_at_level_cap,
)
from src.services.location_service import format_location_room_reference
from src.services.player_service import get_player_profile, get_rest_status
from src.services.reputation_service import get_location_reputation_label, get_location_reputation_title
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

PROFILE_PAGE_OPTIONS = (
    {
        "label": "Overview",
        "value": "overview",
        "description": "General character overview",
        "emoji": "📘",
    },
    {
        "label": "Stats",
        "value": "stats",
        "description": "Core and derived stats",
        "emoji": "📈",
    },
    {
        "label": "Formulas",
        "value": "formulas",
        "description": "See calculated values",
        "emoji": "📙",
    },
    {
        "label": "Trait",
        "value": "trait",
        "description": "Inspect your Soul Trait",
        "emoji": "🎭",
    },
    {
        "label": "Progression",
        "value": "progression",
        "description": "Level, rank, and timeline info",
        "emoji": "📜",
    },
)

PROFILE_PAGE_META = {
    "overview": {
        "title": "📘 Soul Record — Overview",
        "color": "explore",
        "footer": "The archive remembers the shape of your soul.",
    },
    "stats": {
        "title": "📈 Soul Record — Stats",
        "color": "explore",
        "footer": "Every scar, sprint, and clash leaves weight on the soul.",
    },
    "formulas": {
        "title": "📙 Soul Record — Formulas",
        "color": "flavor",
        "footer": "Simple readings now. Room to grow later.",
    },
    "trait": {
        "title": "🎭 Soul Trait — Hidden Edge",
        "color": "special",
        "footer": "Some edges are born with the soul before a blade is ever drawn.",
    },
    "progression": {
        "title": "📜 Soul Record — Progression",
        "color": "explore",
        "footer": "Rukongai remembers who rises and who disappears.",
    },
}


def _build_profile_embed_shell(
    *,
    page_key: str,
    discord_user: discord.abc.User,
    description: str,
) -> discord.Embed:
    page_meta = PROFILE_PAGE_META[page_key]
    embed = discord.Embed(
        title=page_meta["title"],
        description=description,
        color=get_explore_color(page_meta["color"]),
    )
    embed.set_author(
        name=discord_user.display_name,
        icon_url=discord_user.display_avatar.url,
    )
    embed.set_thumbnail(url=discord_user.display_avatar.url)
    embed.set_footer(text=page_meta["footer"])
    return embed


def _add_status_field(embed: discord.Embed, player: PlayerProfile) -> None:
    rest_status = get_rest_status(player)

    if player.is_resting:
        embed.add_field(
            name="Status Effect",
            value=build_explore_info_lines(
                "✨ Status: Resting",
                f"⏱ Resting Since: {rest_status.resting_minutes} minute(s) ago",
                (
                    "⚡ Projected Recovery: "
                    f"+{rest_status.recovered_stamina} stamina, +{rest_status.recovered_hp} HP"
                ),
            ),
            inline=False,
        )

    if player.has_minor_setback:
        embed.add_field(
            name="Status Effect",
            value=build_explore_info_lines(
                "✨ Minor Setback",
                (
                    f"Aftermath: {player.setback_source}"
                    if player.setback_source
                    else "Aftermath: A rough clash is still hanging on you."
                ),
                "The next systems can hook into this later.",
            ),
            inline=False,
        )


def _add_active_effects_field(embed: discord.Embed, active_effects: list[PlayerEffect]) -> None:
    if not active_effects:
        return

    embed.add_field(
        name="Status Effect",
        value="\n".join(summarize_active_effects(active_effects)),
        inline=False,
    )


def build_profile_missing_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📘 No Soul Record Found",
        description="The archive has nothing on you yet. Use `/start` and let the district learn your name.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    embed.set_footer(text="Every soul starts somewhere.")
    return embed


def build_profile_unavailable_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📘 Soul Record Unavailable",
        description="The archive is quiet right now. The database connection needs a moment before profiles can open again.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    embed.set_footer(text="Try again when the records settle.")
    return embed


def build_profile_embed(
    player: PlayerProfile,
    discord_user: discord.abc.User,
    page_key: str,
    *,
    active_effects: list[PlayerEffect] | None = None,
) -> discord.Embed:
    trait = player.trait_data
    location = player.location_data
    room_mention = format_location_room_reference(location)
    rest_status = get_rest_status(player)
    status_value = "Resting" if player.is_resting else "Available"
    reputation_label = get_location_reputation_label(player.location)
    reputation_title = get_location_reputation_title(player, player.location)

    if page_key == "stats":
        total_stat_cap = get_total_stat_cap_for_level(player.level)
        total_stats_spent = calculate_total_core_stats(
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
        embed = _build_profile_embed_shell(
            page_key=page_key,
            discord_user=discord_user,
            description=(
                "Nothing in Rukongai comes easy. Every point you place into your build is part of one shared pool, "
                "so what you sharpen says as much about you as what you leave behind."
            ),
        )
        embed.add_field(
            name="Current State",
            value=build_explore_info_lines(
                f"📈 Level: {player.level}",
                f"🎭 Trait: {trait.name}",
                f"📍 Location: {location.name}",
                f"{'✨ Status: Resting' if player.is_resting else '✨ Status: Ready'}",
            ),
            inline=True,
        )
        embed.add_field(
            name="Core Stats",
            value=build_explore_info_lines(
                f"Power: **{player.power}**",
                f"Defense: **{player.defense}**",
                f"Speed: **{player.speed}**",
                f"Reiatsu: **{player.reiatsu}**",
            ),
            inline=True,
        )
        embed.add_field(
            name="Resources",
            value=build_explore_info_lines(
                f"❤️ HP: {player.hp_current}/{player.hp_max}",
                f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
                f"🔷 Mana: {player.mana_current}/{player.mana_max}",
                f"💰 Kan: {player.kan}",
                f"📈 Spiritual Pressure: {player.spiritual_pressure}",
            ),
            inline=False,
        )
        add_explore_divider(embed)
        embed.add_field(
            name="Current Cap",
            value=build_explore_info_lines(
                f"Total Stat Pool: **{total_stats_spent}/{total_stat_cap}**",
                f"Remaining Points: **{remaining_capacity}**",
                "Cap Rule: **Level x 10 total across all four stats**",
            ),
            inline=False,
        )
        embed.add_field(
            name="What Shapes Your Edge",
            value=build_explore_info_lines(
                f"🎭 {reputation_label}: {reputation_title}",
                "Your base stats stay clean.",
                "Trait bonuses and future systems layer on top of them.",
            ),
            inline=False,
        )
        _add_status_field(embed, player)
        _add_active_effects_field(embed, active_effects or [])
        return embed

    if page_key == "formulas":
        effective_hp = calculate_effective_hp_max(player.hp_max, trait)
        effective_stamina = calculate_effective_stamina_max(player.stamina_max, trait)
        effective_mana = calculate_effective_mana_max(player.mana_max, trait)
        effective_power = calculate_effective_damage_power(player.power, trait)
        effective_defense = calculate_effective_defense(player.defense, trait)
        effective_speed = calculate_effective_speed(player.speed, trait)

        embed = _build_profile_embed_shell(
            page_key=page_key,
            discord_user=discord_user,
            description=(
                "These readings sit under the hood of your sheet. They are simple on purpose, "
                "so combat, Kido, Zanpakuto growth, and future systems can plug in cleanly."
            ),
        )
        embed.add_field(
            name="Current Readings",
            value=build_explore_info_lines(
                "📈 Spiritual Pressure",
                "Power + Defense + Speed + Reiatsu",
                (
                    f"`{player.power} + {player.defense} + {player.speed} + {player.reiatsu}"
                    f" = {player.spiritual_pressure}`"
                ),
            ),
            inline=False,
        )
        embed.add_field(
            name="Trait-Adjusted Values",
            value=build_explore_info_lines(
                f"❤️ Effective Max HP: {effective_hp}",
                f"⚡ Effective Max Stamina: {effective_stamina}",
                f"🔷 Effective Max Mana: {effective_mana}",
                f"🧭 Damage Power: {effective_power}",
                f"🧭 Defense Calc: {effective_defense}",
                f"🧭 Speed Calc: {effective_speed}",
            ),
            inline=False,
        )
        embed.add_field(
            name="Passive Hooks",
            value=build_explore_info_lines(
                f"🧭 Dodge Bonus: {trait.bonuses.flat_dodge_pct:.0%}",
                f"⚡ Stamina Regen Bonus: {trait.bonuses.stamina_regen_pct:.0%}",
                f"🎯 Event Reward Bonus: {trait.bonuses.event_reward_pct:.0%}",
                (
                    "✨ Defeat Penalty Reduction: "
                    f"{trait.bonuses.defeat_penalty_reduction_pct:.0%}"
                ),
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

        embed = _build_profile_embed_shell(
            page_key=page_key,
            discord_user=discord_user,
            description=(
                "Some souls bend before they break. Some cut cleaner than they should. This is the "
                "edge your soul was carrying before you even knew its name."
            ),
        )
        embed.add_field(
            name="Current State",
            value=build_explore_info_lines(
                f"🎭 Trait: {trait.name}",
                f"📍 Location: {location.name}",
                f"🎭 {reputation_label}: {reputation_title}",
            ),
            inline=False,
        )
        add_explore_divider(embed)
        embed.add_field(name="Effect", value=trait.effect, inline=False)
        embed.add_field(
            name="Stored Bonuses",
            value="\n".join(bonus_lines),
            inline=False,
        )
        _add_status_field(embed, player)
        _add_active_effects_field(embed, active_effects or [])
        return embed

    if page_key == "progression":
        xp_to_next = max(0, get_xp_required_for_level(player.level) - player.xp)
        xp_line = f"🎯 XP: {player.xp}"
        next_level_line = f"📈 To Next Level: {xp_to_next}"
        if is_at_level_cap(player.level):
            xp_line = "🎯 XP: MAXED"
            next_level_line = "📈 To Next Level: MAX"
        embed = _build_profile_embed_shell(
            page_key=page_key,
            discord_user=discord_user,
            description=(
                "Rukongai is only the beginning. This page tracks how far you have come, how close "
                "the next step is, and how much weight your name carries where you stand."
            ),
        )
        embed.add_field(
            name="Current State",
            value=build_explore_info_lines(
                f"📈 Level: {player.level}",
                xp_line,
                next_level_line,
                f"💰 Kan: {player.kan}",
                f"🧭 Spiritual Pressure: {player.spiritual_pressure}",
            ),
            inline=True,
        )
        embed.add_field(
            name="World State",
            value=build_explore_info_lines(
                f"📍 Location: {location.name}",
                f"🎭 {reputation_label}: {reputation_title}",
                f"📘 Race: {player.race}",
                f"📜 Rank: {player.rank}",
            ),
            inline=True,
        )
        add_explore_divider(embed)
        embed.add_field(
            name="What Comes Next",
            value=build_explore_info_lines(
                f"🕓 Soul Record Opened: {discord.utils.format_dt(player.created_at, 'R')}",
                f"📍 Current Room: {room_mention}",
                "Training, travel, shops, awakenings, and later forms can build on this clean progression base.",
            ),
            inline=False,
        )
        _add_status_field(embed, player)
        _add_active_effects_field(embed, active_effects or [])
        return embed

    embed = _build_profile_embed_shell(
        page_key="overview",
        discord_user=discord_user,
        description=(
            "A soul does not get much for free in Rukongai. This record tracks what you have endured, "
            "what the district knows about you, and what kind of pressure your name carries now."
        ),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📘 Race: {player.race}",
            f"📜 Rank: {player.rank}",
            f"📈 Level: {player.level}",
            f"🎭 Trait: {trait.name}",
        ),
        inline=True,
    )
    embed.add_field(
        name="Resources",
        value=build_explore_info_lines(
            f"❤️ HP: {player.hp_current}/{player.hp_max}",
            f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
            f"🔷 Mana: {player.mana_current}/{player.mana_max}",
            f"💰 Kan: {player.kan}",
            f"🧭 Spiritual Pressure: {player.spiritual_pressure}",
        ),
        inline=True,
    )
    add_explore_divider(embed)
    embed.add_field(
        name="World State",
        value=build_explore_info_lines(
            f"📍 Location: {location.name}",
            f"🕓 Room: {room_mention}",
            f"🎭 {reputation_label}: {reputation_title}",
            f"✨ Status: {status_value}",
        ),
        inline=False,
    )
    if player.is_resting:
        embed.add_field(
            name="Status Effect",
            value=build_explore_info_lines(
                "✨ Resting",
                f"⏱ Resting Since: {rest_status.resting_minutes} minute(s) ago",
                (
                    "⚡ Projected Recovery: "
                    f"+{rest_status.recovered_stamina} stamina, +{rest_status.recovered_hp} HP"
                ),
            ),
            inline=False,
        )
    if player.has_minor_setback:
        embed.add_field(
            name="Status Effect",
            value=build_explore_info_lines(
                "✨ Minor Setback",
                (
                    f"Aftermath: {player.setback_source}"
                    if player.setback_source
                    else "Aftermath: A hard loss is still hanging on you."
                ),
            ),
            inline=False,
        )
    _add_active_effects_field(embed, active_effects or [])
    return embed


class ProfilePageSelect(discord.ui.Select["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Choose a page in your Soul Record",
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
        active_effects: list[PlayerEffect],
        *,
        initial_page: str = "overview",
    ) -> None:
        super().__init__(timeout=180)
        self.db_pool = db_pool
        self.owner_id = owner_id
        self.player = player
        self.discord_user = discord_user
        self.active_effects = active_effects
        self.message: discord.Message | None = None
        self.page_key = initial_page
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

        self.active_effects = await list_active_player_effects(self.db_pool, self.owner_id)

        self.page_key = page_key
        self.page_select.set_active(page_key)
        embed = build_profile_embed(
            self.player,
            self.discord_user,
            page_key,
            active_effects=self.active_effects,
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
