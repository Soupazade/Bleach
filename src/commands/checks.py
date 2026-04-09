from __future__ import annotations

import discord
from discord import app_commands

from src.data.staff import get_allowed_staff_role_ids


def require_staff_rank(minimum_rank: str):
    allowed_role_ids = get_allowed_staff_role_ids(minimum_rank)

    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            raise app_commands.CheckFailure("This staff command can only be used in a guild.")

        if any(role.id in allowed_role_ids for role in member.roles):
            return True

        raise app_commands.CheckFailure("You do not have permission to use this staff command.")

    return app_commands.check(predicate)
