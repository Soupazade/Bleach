from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.exploration_service import get_active_exploration, resolve_and_post_exploration
from src.services.player_service import RestStatus, get_player_profile, get_rest_status, toggle_resting
from src.services.training_service import get_active_training, resolve_and_post_training
from src.services.travel_service import get_active_travel, resolve_and_post_travel

if TYPE_CHECKING:
    from src.main import BleachBot


def build_rest_started_embed(player, rest_status: RestStatus) -> discord.Embed:
    embed = discord.Embed(
        title="Resting Begun",
        description="You begin resting. You recover **5 stamina and 5 HP per minute** until you stop.",
        color=discord.Color.teal(),
    )
    embed.add_field(name="Status", value="**Resting**", inline=True)
    embed.add_field(
        name="Resting Since",
        value=f"**{rest_status.resting_minutes} minute(s) ago**",
        inline=True,
    )
    embed.add_field(
        name="Projected Recovery",
        value=f"**+{rest_status.recovered_stamina} stamina, +{rest_status.recovered_hp} HP**",
        inline=True,
    )
    embed.add_field(
        name="Current Resources",
        value=(
            f"**HP:** {player.hp_current}/{player.hp_max}\n"
            f"**Stamina:** {player.stamina_current}/{player.stamina_max}"
        ),
        inline=False,
    )
    return embed


def build_rest_stopped_embed(player, rest_status: RestStatus) -> discord.Embed:
    embed = discord.Embed(
        title="Rest Ended",
        description=(
            "You stop resting and recover "
            f"**{rest_status.recovered_stamina} stamina** and **{rest_status.recovered_hp} HP**."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Time Rested",
        value=f"**{rest_status.resting_minutes} minute(s)**",
        inline=True,
    )
    embed.add_field(
        name="Recovered",
        value=(
            f"**+{rest_status.recovered_stamina} stamina**\n"
            f"**+{rest_status.recovered_hp} HP**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Current Resources",
        value=(
            f"**HP:** {player.hp_current}/{player.hp_max}\n"
            f"**Stamina:** {player.stamina_current}/{player.stamina_max}"
        ),
        inline=True,
    )
    return embed


def register_rest_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="rest", description="Toggle resting to recover stamina and HP over time.")
    @app_commands.guild_only()
    async def rest(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                "The database is not connected right now, so resting is unavailable.",
                ephemeral=True,
            )
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(
                "You don't have a profile yet. Use /start first.",
                ephemeral=True,
            )
            return

        if not player.is_resting:
            active_training = await get_active_training(bot.db_pool, interaction.user.id)
            active_travel = await get_active_travel(bot.db_pool, interaction.user.id)
            now = datetime.now(timezone.utc)
            if active_training is not None:
                if active_training.end_time > now:
                    await interaction.response.send_message(
                        "You cannot rest while training is active.",
                        ephemeral=True,
                    )
                    return

                await resolve_and_post_training(bot, interaction.user.id)

            if active_travel is not None:
                if active_travel.end_time > now:
                    await interaction.response.send_message(
                        "You cannot rest while travel is active.",
                        ephemeral=True,
                    )
                    return

                await resolve_and_post_travel(bot, interaction.user.id)

            active_exploration = await get_active_exploration(bot.db_pool, interaction.user.id)
            if active_exploration is not None:
                if active_exploration.end_time > now:
                    await interaction.response.send_message(
                        "You cannot rest while an exploration is active.",
                        ephemeral=True,
                    )
                    return

                await resolve_and_post_exploration(bot, interaction.user.id)

        updated_player, started_resting, rest_status = await toggle_resting(
            bot.db_pool,
            interaction.user.id,
        )
        if updated_player is None:
            await interaction.response.send_message(
                "I couldn't load your profile right now.",
                ephemeral=True,
            )
            return

        if started_resting:
            rest_status = get_rest_status(updated_player)
            await interaction.response.send_message(
                embed=build_rest_started_embed(updated_player, rest_status),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=build_rest_stopped_embed(updated_player, rest_status),
            ephemeral=True,
        )
