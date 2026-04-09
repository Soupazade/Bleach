from __future__ import annotations

import discord

from src.data.locations import LOCATIONS, LocationDefinition


def format_location_room_reference(location: LocationDefinition) -> str:
    if location.room_id is not None:
        return f"<#{location.room_id}>"
    if location.room_name is not None:
        return f"`#{location.room_name}`"
    return f"**{location.name}**"


def get_location_role_names() -> set[str]:
    return {
        location.role_name or location.name
        for location in LOCATIONS.values()
    }


def channel_matches_location(
    location: LocationDefinition,
    channel: discord.abc.GuildChannel | discord.Thread | None,
) -> bool:
    if channel is None:
        return False

    if location.room_id is not None and channel.id == location.room_id:
        return True

    return location.room_name is not None and channel.name == location.room_name


def resolve_location_channel(
    guild: discord.Guild,
    location: LocationDefinition,
) -> discord.abc.GuildChannel | discord.Thread | None:
    if location.room_id is not None:
        channel = guild.get_channel(location.room_id)
        if channel is not None:
            return channel

    if location.room_name is None:
        return None

    for channel in guild.channels:
        if channel.name == location.room_name:
            return channel

    for thread in guild.threads:
        if thread.name == location.room_name:
            return thread

    return None


def resolve_location_role(
    guild: discord.Guild,
    location: LocationDefinition,
) -> discord.Role | None:
    if location.role_id is not None:
        role = guild.get_role(location.role_id)
        if role is not None:
            return role

    role_name = location.role_name or location.name
    return discord.utils.get(guild.roles, name=role_name)
