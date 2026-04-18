from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.services.combat_service import get_active_exploration_combat
from src.services.dungeon_service import bind_dungeon_message, get_active_dungeon_run, start_first_dungeon
from src.services.location_service import channel_matches_location
from src.services.player_service import build_resting_block_message, get_player_profile, get_rest_status
from src.services.work_service import get_active_work, resolve_and_post_work
from src.ui.dungeon_view import (
    DungeonView,
    build_dungeon_blocked_embed,
    build_dungeon_room_embed,
    build_dungeon_started_embed,
)
from src.ui.exploration_combat_view import build_active_combat_embed
from src.ui.work_view import build_work_active_embed, build_work_resolution_posted_embed

if TYPE_CHECKING:
    from src.main import BleachBot


def register_dungeon_command(bot: "BleachBot") -> None:
    @bot.tree.command(name="dungeon", description="Enter the Outskirts bandit hideout.")
    @app_commands.guild_only()
    async def dungeon(interaction: discord.Interaction) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "Dungeon Unavailable",
                    "The hideout records are not reachable right now.",
                ),
                ephemeral=True,
            )
            return

        player = await get_player_profile(bot.db_pool, interaction.user.id)
        if player is None:
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "No Soul Record Found",
                    "You need to use `/start` before Rukongai lets you press into the Outskirts alone.",
                ),
                ephemeral=True,
            )
            return

        if not channel_matches_location(player.location_data, interaction.channel):
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "Wrong District",
                    "The bandit hideout is tucked away in your current district. Step into the right room before you try to force the run.",
                ),
                ephemeral=True,
            )
            return

        if player.is_resting:
            rest_status = get_rest_status(player)
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "You Are Resting",
                    build_resting_block_message(player, rest_status),
                    kind="choice",
                ),
                ephemeral=True,
            )
            return

        existing_run = await get_active_dungeon_run(bot.db_pool, interaction.user.id)
        if existing_run is not None:
            await interaction.response.send_message(
                embed=build_dungeon_room_embed(player, existing_run),
                view=DungeonView(bot, existing_run),
            )
            message = await interaction.original_response()
            await bind_dungeon_message(
                bot.db_pool,
                user_id=interaction.user.id,
                message_id=message.id,
            )
            return

        active_combat = await get_active_exploration_combat(bot.db_pool, interaction.user.id)
        if active_combat is not None:
            await interaction.response.send_message(
                embed=build_active_combat_embed(active_combat, interaction.user),
                ephemeral=True,
            )
            return

        active_work = await get_active_work(bot.db_pool, interaction.user.id)
        if active_work is not None:
            if active_work.end_time > datetime.now(timezone.utc):
                await interaction.response.send_message(
                    embed=build_work_active_embed(player, active_work),
                    ephemeral=True,
                )
                return

            resolution = await resolve_and_post_work(bot, interaction.user.id)
            await interaction.response.send_message(
                embed=build_work_resolution_posted_embed() if resolution is not None else build_dungeon_blocked_embed(
                    "Work Resolution Failed",
                    "That shift should have been over, but I could not settle it cleanly just yet.",
                ),
                ephemeral=True,
            )
            return

        if interaction.channel_id is None:
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "Dungeon Failed",
                    "I could not determine which channel to anchor the run in.",
                ),
                ephemeral=True,
            )
            return

        result = await start_first_dungeon(
            bot.db_pool,
            user_id=interaction.user.id,
            channel_id=interaction.channel_id,
        )

        if result.status == "started" and result.player is not None and result.run is not None:
            view = DungeonView(bot, result.run)
            embed = build_dungeon_started_embed(
                result.player,
                result.run,
                stamina_cost=result.stamina_cost,
            )
            await interaction.response.send_message(embed=embed, view=view)
            message = await interaction.original_response()
            rebound = await bind_dungeon_message(
                bot.db_pool,
                user_id=interaction.user.id,
                message_id=message.id,
            )
            if rebound is not None:
                await message.edit(
                    embed=build_dungeon_room_embed(result.player, rebound),
                    view=DungeonView(bot, rebound),
                )
            return

        if result.status == "active" and result.player is not None and result.run is not None:
            await interaction.response.send_message(
                embed=build_dungeon_room_embed(result.player, result.run),
                view=DungeonView(bot, result.run),
            )
            message = await interaction.original_response()
            await bind_dungeon_message(
                bot.db_pool,
                user_id=interaction.user.id,
                message_id=message.id,
            )
            return

        if result.status == "active_combat":
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "Dungeon Blocked",
                    "You already have a live fight running.",
                ),
                ephemeral=True,
            )
            return

        if result.status == "busy":
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "Dungeon Blocked",
                    result.reason or "Finish what you are doing first.",
                ),
                ephemeral=True,
            )
            return

        if result.status == "wrong_location":
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "Wrong District",
                    "This dungeon is hidden in the Rukongai Outskirts.",
                ),
                ephemeral=True,
            )
            return

        if result.status == "insufficient_stamina" and result.player is not None:
            await interaction.response.send_message(
                embed=build_dungeon_blocked_embed(
                    "Not Enough Stamina",
                    (
                        "You do not have enough left in you to force the hideout.\n"
                        f"Current: **{result.player.stamina_current}/{result.player.stamina_max}**\n"
                        f"Required: **{result.stamina_cost}**"
                    ),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=build_dungeon_blocked_embed(
                "Dungeon Failed",
                "I could not open the hideout cleanly right now.",
            ),
            ephemeral=True,
        )
