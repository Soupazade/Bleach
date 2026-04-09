from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.commands.checks import require_staff_rank
from src.data.locations import LOCATIONS, get_location_definition
from src.services.role_service import remove_player_roles, sync_member_location_role
from src.services.staff_service import (
    delete_player_profile,
    give_player_xp,
    reset_player_action_timers,
    set_player_location,
    set_player_stamina,
    set_player_xp,
)

if TYPE_CHECKING:
    from src.main import BleachBot


LOCATION_CHOICES = [
    app_commands.Choice(name=location.name, value=location.key)
    for location in LOCATIONS.values()
]


def _cancel_player_exploration_task(bot: "BleachBot", user_id: int) -> bool:
    task = bot.exploration_tasks.pop(user_id, None)
    if task is None:
        return False

    task.cancel()
    return True


def register_staff_commands(bot: "BleachBot") -> None:
    @bot.tree.command(name="resetplayer", description="Delete a player's profile so they must use /start again.")
    @app_commands.guild_only()
    @require_staff_rank("super_admin")
    async def resetplayer(interaction: discord.Interaction, player: discord.Member) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        cancelled_task = _cancel_player_exploration_task(bot, player.id)
        deleted_profile = await delete_player_profile(bot.db_pool, player.id)
        role_summary, role_warning = await remove_player_roles(
            player,
            reason=f"Player profile reset by {interaction.user}",
        )

        embed = discord.Embed(
            title="Player Reset Complete",
            description=(
                f"{player.mention} has been reset and can use **/start** again."
                if deleted_profile
                else f"{player.mention} did not have a saved profile, but any leftover player roles were checked."
            ),
            color=discord.Color.red(),
        )
        embed.add_field(name="Profile Deleted", value="Yes" if deleted_profile else "No", inline=True)
        embed.add_field(
            name="Exploration Task Cancelled",
            value="Yes" if cancelled_task else "No active task",
            inline=True,
        )
        if role_summary is not None:
            embed.add_field(name="Role Update", value=role_summary, inline=False)
        if role_warning is not None:
            embed.add_field(name="Role Warning", value=role_warning, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="setxp", description="Set a player's XP progress using admin controls.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    async def setxp(interaction: discord.Interaction, player: discord.Member, amount: app_commands.Range[int, 0]) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        updated_player, levels_gained = await set_player_xp(bot.db_pool, player.id, amount)
        if updated_player is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        xp_to_next = updated_player.level * 20
        embed = discord.Embed(
            title="XP Set",
            description=f"{player.mention}'s XP progress has been updated.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Level", value=f"**{updated_player.level}**", inline=True)
        embed.add_field(name="Stored XP", value=f"**{updated_player.xp} / {xp_to_next}**", inline=True)
        embed.add_field(name="Levels Gained", value=f"**{levels_gained}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="givexp", description="Give XP to a player and apply any resulting level-ups.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    async def givexp(interaction: discord.Interaction, player: discord.Member, amount: app_commands.Range[int, 0]) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        updated_player, levels_gained = await give_player_xp(bot.db_pool, player.id, amount)
        if updated_player is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        xp_to_next = updated_player.level * 20
        embed = discord.Embed(
            title="XP Granted",
            description=f"{player.mention} gains **{amount} XP**.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Level", value=f"**{updated_player.level}**", inline=True)
        embed.add_field(name="Stored XP", value=f"**{updated_player.xp} / {xp_to_next}**", inline=True)
        embed.add_field(name="Levels Gained", value=f"**{levels_gained}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="setstam", description="Set a player's current stamina.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    async def setstam(interaction: discord.Interaction, player: discord.Member, amount: int) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        updated_player = await set_player_stamina(bot.db_pool, player.id, amount)
        if updated_player is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Stamina Updated",
            description=f"{player.mention}'s stamina has been adjusted.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Current Stamina",
            value=f"**{updated_player.stamina_current}/{updated_player.stamina_max}**",
            inline=True,
        )
        embed.add_field(
            name="Resting",
            value="Yes" if updated_player.is_resting else "No",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="cooldownreset", description="Reset a player's active timed-action locks.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    async def cooldownreset(interaction: discord.Interaction, player: discord.Member) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        cancelled_task = _cancel_player_exploration_task(bot, player.id)
        result = await reset_player_action_timers(bot.db_pool, player.id)
        if result is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Timed Actions Reset",
            description=f"{player.mention}'s active pacing locks have been cleared.",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="Exploration Cleared",
            value="Yes" if result.cleared_exploration or cancelled_task else "No",
            inline=True,
        )
        embed.add_field(
            name="Rest Cleared",
            value="Yes" if result.cleared_resting else "No",
            inline=True,
        )
        embed.add_field(
            name="Current Stamina",
            value=f"**{result.player.stamina_current}/{result.player.stamina_max}**",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="setlocation", description="Move a player to a new location and sync their location role.")
    @app_commands.guild_only()
    @require_staff_rank("mod")
    @app_commands.choices(location=LOCATION_CHOICES)
    async def setlocation(
        interaction: discord.Interaction,
        player: discord.Member,
        location: app_commands.Choice[str],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        updated_player = await set_player_location(bot.db_pool, player.id, location.value)
        if updated_player is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        location_data = get_location_definition(updated_player.location)
        role_summary, role_warning = await sync_member_location_role(
            player,
            location_data.role_id,
            reason=f"Location updated by {interaction.user}",
        )

        embed = discord.Embed(
            title="Location Updated",
            description=f"{player.mention} has been moved to **{location_data.name}**.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Location", value=f"**{location_data.name}**", inline=True)
        embed.add_field(name="Room", value=f"<#{location_data.room_id}>", inline=True)
        if role_summary is not None:
            embed.add_field(name="Role Update", value=role_summary, inline=False)
        if role_warning is not None:
            embed.add_field(name="Role Warning", value=role_warning, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
