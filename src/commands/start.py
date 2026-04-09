from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.data.game_constants import SOUL_ROLE_ID
from src.models.player import PlayerProfile
from src.services.location_service import format_location_room_reference, resolve_location_role
from src.services.player_service import create_player_profile

if TYPE_CHECKING:
    from src.main import BleachBot


def build_start_embed(
    member: discord.Member,
    profile: PlayerProfile,
    created: bool,
    role_summary: str | None = None,
    role_warning: str | None = None,
) -> discord.Embed:
    trait = profile.trait_data
    location = profile.location_data
    title = "A Soul Awakens in Rukongai" if created else "Your Soul Record Already Exists"
    description = (
        f"{member.mention}, your spirit stirs and your journey begins in the outer streets of Rukongai."
        if created
        else f"{member.mention}, your soul has already entered the record. Use **/profile** to inspect it."
    )

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(25, 120, 255),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="Identity",
        value=f"Race: **{profile.race}**\nRank: **{profile.rank}**",
        inline=True,
    )
    embed.add_field(
        name="Progress",
        value=f"Level: **{profile.level}**\nXP: **{profile.xp}**",
        inline=True,
    )
    embed.add_field(
        name="Opening Resources",
        value=(
            f"HP: **{profile.hp_current}/{profile.hp_max}**\n"
            f"Stamina: **{profile.stamina_current}/{profile.stamina_max}**\n"
            f"Mana: **{profile.mana_current}/{profile.mana_max}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Soul Trait",
        value=f"**{trait.name}**\n{trait.effect}",
        inline=False,
    )
    embed.add_field(
        name="Spawn Location",
        value=f"**{location.name}**\nRoom: {format_location_room_reference(location)}",
        inline=False,
    )

    if role_summary is not None:
        embed.add_field(name="Role Setup", value=role_summary, inline=False)

    if role_warning is not None:
        embed.add_field(name="Role Warning", value=role_warning, inline=False)

    embed.set_footer(text="Use /profile to open your multi-page Soul Record.")
    return embed


async def assign_starting_roles(
    member: discord.Member,
    location,
) -> tuple[str | None, str | None]:
    roles_to_add: list[discord.Role] = []
    pending_role_names: list[str] = []
    warnings: list[str] = []

    soul_role = member.guild.get_role(SOUL_ROLE_ID)
    location_role = resolve_location_role(member.guild, location)

    if soul_role is None:
        warnings.append("Soul role was not found in this guild.")
    elif soul_role not in member.roles:
        roles_to_add.append(soul_role)
        pending_role_names.append(soul_role.name)

    if location_role is None:
        warnings.append("Location role was not found in this guild.")
    elif location_role not in member.roles:
        roles_to_add.append(location_role)
        pending_role_names.append(location_role.name)

    added_role_names: list[str] = []
    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add, reason="Initialized Bleach RPG profile")
            added_role_names = pending_role_names
        except discord.Forbidden:
            warnings.append("I could not assign one or more roles because the bot lacks permission.")
        except discord.HTTPException:
            warnings.append("Discord rejected the role assignment request.")

    if not added_role_names and not warnings:
        return "Soul and location roles were already assigned.", None

    role_summary = None
    if added_role_names:
        role_summary = "Added roles: " + ", ".join(f"**{role_name}**" for role_name in added_role_names)

    warning_text = "\n".join(warnings) if warnings else None
    return role_summary, warning_text


def register_start_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="start", description="Create your Bleach RPG Soul profile.")
    @app_commands.guild_only()
    async def start(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                "The database is not connected right now, so I can't create profiles yet.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            resolved_member = interaction.guild.get_member(interaction.user.id)
            if resolved_member is None:
                await interaction.response.send_message(
                    "I couldn't resolve your server member data. Please try again in the guild.",
                    ephemeral=True,
                )
                return
            member = resolved_member

        profile, created = await create_player_profile(bot.db_pool, member.id)
        if profile is None:
            await interaction.response.send_message(
                "I couldn't load or create your profile right now.",
                ephemeral=True,
            )
            return

        role_summary = None
        role_warning = None
        if created:
            role_summary, role_warning = await assign_starting_roles(
                member,
                profile.location_data,
            )

        embed = build_start_embed(
            member=member,
            profile=profile,
            created=created,
            role_summary=role_summary,
            role_warning=role_warning,
        )
        await interaction.response.send_message(embed=embed)
