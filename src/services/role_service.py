from __future__ import annotations

import discord

from src.data.game_constants import SOUL_ROLE_ID
from src.data.locations import LOCATIONS


def get_location_role_ids() -> set[int]:
    return {location.role_id for location in LOCATIONS.values()}


async def sync_member_location_role(
    member: discord.Member,
    target_location_role_id: int,
    *,
    reason: str,
) -> tuple[str | None, str | None]:
    location_role_ids = get_location_role_ids()
    roles_to_remove = [role for role in member.roles if role.id in location_role_ids and role.id != target_location_role_id]
    roles_to_add: list[discord.Role] = []
    warnings: list[str] = []
    summaries: list[str] = []

    target_role = member.guild.get_role(target_location_role_id)
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
    roles_to_remove = [role for role in member.roles if role.id in removable_role_ids]

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
