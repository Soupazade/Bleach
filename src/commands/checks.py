from __future__ import annotations

import discord
from discord import app_commands

from src.data.staff import get_allowed_staff_role_ids


STAFF_COMMAND_MARKER = "__staff_rank__"


def is_staff_member(member: discord.abc.User | discord.Member) -> bool:
    if not isinstance(member, discord.Member):
        return False

    allowed_role_ids = get_allowed_staff_role_ids("trial_mod")
    return any(role.id in allowed_role_ids for role in member.roles)


def is_staff_command(command: app_commands.Command | app_commands.ContextMenu | None) -> bool:
    if command is None:
        return False

    return any(
        getattr(check, STAFF_COMMAND_MARKER, None) is not None
        for check in getattr(command, "checks", [])
    )


def require_staff_rank(minimum_rank: str):
    allowed_role_ids = get_allowed_staff_role_ids(minimum_rank)

    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            raise app_commands.CheckFailure("This staff command can only be used in a guild.")

        if any(role.id in allowed_role_ids for role in member.roles):
            return True

        raise app_commands.CheckFailure("You do not have permission to use this staff command.")

    setattr(predicate, STAFF_COMMAND_MARKER, minimum_rank)
    return app_commands.check(predicate)
