from __future__ import annotations

import discord

from src.data.game_constants import SOUL_ROLE_ID
from src.data.locations import LOCATIONS, LocationDefinition
from src.services.location_service import get_location_role_names, resolve_location_role


def get_location_role_ids() -> set[int]:
    return {
        location.role_id
        for location in LOCATIONS.values()
        if location.role_id is not None
    }


async def sync_member_location_role(
    member: discord.Member,
    target_location: LocationDefinition,
    *,
    reason: str,
) -> tuple[str | None, str | None]:
    location_role_ids = get_location_role_ids()
    location_role_names = get_location_role_names()
    target_role = resolve_location_role(member.guild, target_location)
    target_role_id = target_role.id if target_role is not None else target_location.role_id
    target_role_name = target_role.name if target_role is not None else (target_location.role_name or target_location.name)
    roles_to_remove = [
        role
        for role in member.roles
        if (role.id in location_role_ids or role.name in location_role_names)
        and role.id != target_role_id
        and role.name != target_role_name
    ]
    roles_to_add: list[discord.Role] = []
    warnings: list[str] = []
    summaries: list[str] = []

    if target_role is None:
        warnings.append("Target location role was not found in this guild.")
    elif target_role not in member.roles:
        roles_to_add.append(target_role)

    if roles_to_remove:
        try:
            await member.remove_roles(*roles_to_remove, reason=reason)
            summaries.append(
                "Removed location roles: " + ", ".join(f"**{role.name}**" for role in roles_to_remove)
            )
        except discord.Forbidden:
            warnings.append("I could not remove old location roles because the bot lacks permission.")
        except discord.HTTPException:
            warnings.append("Discord rejected the location role removal request.")

    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add, reason=reason)
            summaries.append(
                "Added location role: " + ", ".join(f"**{role.name}**" for role in roles_to_add)
            )
        except discord.Forbidden:
            warnings.append("I could not add the new location role because the bot lacks permission.")
        except discord.HTTPException:
            warnings.append("Discord rejected the location role update request.")

    return "\n".join(summaries) if summaries else None, "\n".join(warnings) if warnings else None


async def remove_player_roles(
    member: discord.Member,
    *,
    reason: str,
) -> tuple[str | None, str | None]:
    removable_role_ids = get_location_role_ids() | {SOUL_ROLE_ID}
    removable_role_names = get_location_role_names()
    roles_to_remove = [
        role for role in member.roles
        if role.id in removable_role_ids or role.name in removable_role_names
    ]

    if not roles_to_remove:
        return "No Soul or location roles needed to be removed.", None

    try:
        await member.remove_roles(*roles_to_remove, reason=reason)
        return (
            "Removed roles: " + ", ".join(f"**{role.name}**" for role in roles_to_remove),
            None,
        )
    except discord.Forbidden:
        return None, "I could not remove one or more player roles because the bot lacks permission."
    except discord.HTTPException:
        return None, "Discord rejected the role removal request."
