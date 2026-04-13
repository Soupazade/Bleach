from __future__ import annotations

from collections.abc import Iterable

import discord

from src.data.locations import LOCATIONS, LocationDefinition


def _normalize_location_token(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _iter_location_role_aliases(location: LocationDefinition) -> tuple[str, ...]:
    aliases: list[str] = []
    for candidate in (
        location.role_name,
        location.name,
        location.room_name.replace("-", " ").replace("_", " ") if location.room_name is not None else None,
    ):
        if candidate is None:
            continue
        if candidate not in aliases:
            aliases.append(candidate)
    return tuple(aliases)


def _iter_location_role_alias_keys(location: LocationDefinition) -> tuple[str, ...]:
    alias_keys: list[str] = []
    for alias in _iter_location_role_aliases(location):
        normalized = _normalize_location_token(alias)
        if normalized and normalized not in alias_keys:
            alias_keys.append(normalized)
    return tuple(alias_keys)


def format_location_room_reference(location: LocationDefinition) -> str:
    if location.room_id is not None:
        return f"<#{location.room_id}>"
    if location.room_name is not None:
        return f"`#{location.room_name}`"
    return f"**{location.name}**"


def get_location_role_names() -> set[str]:
    return {
        alias
        for location in LOCATIONS.values()
        for alias in _iter_location_role_aliases(location)
    }


def role_matches_location(
    role: discord.Role,
    location: LocationDefinition,
) -> bool:
    if location.role_id is not None and role.id == location.role_id:
        return True

    normalized_role_name = _normalize_location_token(role.name)
    return normalized_role_name in _iter_location_role_alias_keys(location)


def role_matches_any_location(role: discord.Role) -> bool:
    return any(role_matches_location(role, location) for location in LOCATIONS.values())


def find_matching_location_roles(
    roles: Iterable[discord.Role],
    location: LocationDefinition,
) -> list[discord.Role]:
    return [role for role in roles if role_matches_location(role, location)]


def find_any_location_roles(roles: Iterable[discord.Role]) -> list[discord.Role]:
    return [role for role in roles if role_matches_any_location(role)]


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

    for role_name in _iter_location_role_aliases(location):
        role = discord.utils.get(guild.roles, name=role_name)
        if role is not None:
            return role

    matches = find_matching_location_roles(guild.roles, location)
    if not matches:
        return None

    return max(matches, key=lambda role: (role.position, role.id))
