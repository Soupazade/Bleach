from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.commands.checks import require_staff_rank
from src.data.exploration import get_explore_approach
from src.data.locations import LOCATIONS, get_location_definition
from src.data.npcs import RECURRING_NPCS
from src.data.quests import QUEST_DEFINITIONS
from src.data.traits import SOUL_TRAITS, get_trait_definition
from src.services.dungeon_service import get_active_dungeon_run
from src.services.exploration_service import get_exploration_remaining_time, resolve_and_post_exploration
from src.services.formulas import get_xp_required_for_level
from src.services.location_service import format_location_room_reference
from src.services.role_service import remove_player_roles, sync_member_location_role
from src.services.training_service import get_training_remaining_time
from src.services.travel_service import get_travel_remaining_time
from src.services.work_service import get_work_remaining_time
from src.services.staff_service import (
    clear_player_effects,
    delete_player_profile,
    end_fight_without_victor,
    give_player_xp,
    get_player_debug_state,
    reset_player_action_timers,
    set_player_level,
    set_player_location,
    staff_reset_player_npc,
    staff_reset_player_quest,
    set_player_stat,
    set_player_stamina,
    set_player_trait,
    set_player_xp,
)

if TYPE_CHECKING:
    from src.main import BleachBot


LOCATION_CHOICES = [
    app_commands.Choice(name=location.name, value=location.key)
    for location in LOCATIONS.values()
]

TRAIT_CHOICES = [
    app_commands.Choice(name=trait.name, value=trait.key)
    for trait in SOUL_TRAITS.values()
]

STAT_CHOICES = [
    app_commands.Choice(name="Power", value="power"),
    app_commands.Choice(name="Defense", value="defense"),
    app_commands.Choice(name="Speed", value="speed"),
    app_commands.Choice(name="Reiatsu", value="reiatsu"),
]

FORCE_RESOLVE_CHOICES = [
    app_commands.Choice(name="Explore", value="explore"),
]

QUEST_CHOICES = [
    app_commands.Choice(name=quest.title, value=quest.key)
    for quest in QUEST_DEFINITIONS.values()
]

NPC_CHOICES = [
    app_commands.Choice(name=npc.name, value=npc.id)
    for npc in RECURRING_NPCS.values()
]


def _cancel_player_exploration_task(bot: "BleachBot", user_id: int) -> bool:
    task = bot.exploration_tasks.pop(user_id, None)
    if task is None:
        return False

    task.cancel()
    return True


def _cancel_player_travel_task(bot: "BleachBot", user_id: int) -> bool:
    task = bot.travel_tasks.pop(user_id, None)
    if task is None:
        return False

    task.cancel()
    return True


def _cancel_player_training_task(bot: "BleachBot", user_id: int) -> bool:
    task = bot.training_tasks.pop(user_id, None)
    if task is None:
        return False

    task.cancel()
    return True


def _cancel_player_work_task(bot: "BleachBot", user_id: int) -> bool:
    task = bot.work_tasks.pop(user_id, None)
    if task is None:
        return False

    task.cancel()
    return True


def _cancel_player_combat_task(bot: "BleachBot", user_id: int) -> bool:
    task = bot.combat_tasks.pop(user_id, None)
    if task is None:
        return False

    task.cancel()
    return True


def _clear_player_runtime_refs(bot: "BleachBot", user_id: int) -> None:
    bot.exploration_message_refs.pop(user_id, None)
    bot.combat_warning_rounds.pop(user_id, None)
    bot.recent_combat_resolutions.pop(user_id, None)


async def _close_fight_message(
    bot: "BleachBot",
    *,
    combat,
    embed: discord.Embed,
) -> bool:
    if combat.message_id is None:
        return False

    channel = bot.get_channel(combat.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(combat.channel_id)
        except discord.HTTPException:
            return False

    if not hasattr(channel, "fetch_message"):
        return False

    try:
        message = await channel.fetch_message(combat.message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False

    try:
        await message.edit(
            content=f"<@{combat.user_id}>",
            embed=embed,
            view=None,
        )
        return True
    except discord.HTTPException:
        return False


def _can_bulk_delete(message: discord.Message) -> bool:
    return (discord.utils.utcnow() - message.created_at) < timedelta(days=14)


async def _delete_single_message(
    message: discord.Message,
    *,
    reason: str,
    retries: int = 3,
) -> bool:
    for attempt in range(retries):
        try:
            await message.delete(reason=reason)
            return True
        except discord.NotFound:
            return False
        except (discord.DiscordServerError, discord.HTTPException):
            if attempt == retries - 1:
                return False
            await asyncio.sleep(0.8 * (attempt + 1))

    return False


async def _delete_recent_batch(
    channel: discord.TextChannel | discord.Thread,
    messages: list[discord.Message],
    *,
    reason: str,
) -> tuple[int, int]:
    if not messages:
        return 0, 0

    try:
        if len(messages) == 1:
            success = await _delete_single_message(messages[0], reason=reason)
            return (1, 0) if success else (0, 1)

        await channel.delete_messages(messages, reason=reason)
        return len(messages), 0
    except discord.NotFound:
        return 0, len(messages)
    except (discord.DiscordServerError, discord.HTTPException):
        deleted = 0
        failed = 0
        for message in messages:
            if await _delete_single_message(message, reason=reason):
                deleted += 1
            else:
                failed += 1
        return deleted, failed


async def _purge_channel_messages(
    channel: discord.TextChannel | discord.Thread,
    *,
    limit: int,
    reason: str,
) -> tuple[int, int, int]:
    messages = [message async for message in channel.history(limit=limit)]
    recent_messages = [message for message in messages if _can_bulk_delete(message)]
    old_messages = [message for message in messages if not _can_bulk_delete(message)]

    deleted = 0
    failed = 0

    for index in range(0, len(recent_messages), 100):
        batch_deleted, batch_failed = await _delete_recent_batch(
            channel,
            recent_messages[index:index + 100],
            reason=reason,
        )
        deleted += batch_deleted
        failed += batch_failed
        await asyncio.sleep(0.35)

    for message in old_messages:
        if await _delete_single_message(message, reason=reason):
            deleted += 1
        else:
            failed += 1
        await asyncio.sleep(0.35)

    return deleted, failed, len(old_messages)


def build_player_state_embed(bot: "BleachBot", player: discord.Member, debug_state) -> discord.Embed:
    profile = debug_state.player
    location = profile.location_data
    trait = profile.trait_data
    active_exploration = debug_state.active_exploration
    pending_choice = debug_state.pending_choice
    active_combat = debug_state.active_combat
    active_training = debug_state.active_training
    active_travel = debug_state.active_travel
    active_work = debug_state.active_work

    embed = discord.Embed(
        title="Player State",
        description=f"Compact admin debug sheet for {player.mention}.",
        color=discord.Color.dark_blue(),
    )
    embed.add_field(
        name="Identity",
        value=(
            f"Race: **{profile.race}**\n"
            f"Rank: **{profile.rank}**\n"
            f"Trait: **{trait.name}**\n"
            f"Location: **{location.name}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Progress",
        value=(
            f"Level: **{profile.level}**\n"
            f"XP: **{profile.xp}**\n"
            f"Kan: **{profile.kan}**\n"
            f"Power: **{profile.power}**\n"
            f"Defense: **{profile.defense}**\n"
            f"Speed: **{profile.speed}**\n"
            f"Reiatsu: **{profile.reiatsu}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Resources",
        value=(
            f"HP: **{profile.hp_current}/{profile.hp_max}**\n"
            f"Stamina: **{profile.stamina_current}/{profile.stamina_max}**\n"
            f"Mana: **{profile.mana_current}/{profile.mana_max}**\n"
            f"Minor Setback: **{'Active' if profile.has_minor_setback else 'None'}**"
        ),
        inline=False,
    )
    if profile.has_minor_setback:
        embed.add_field(
            name="Setback Hook",
            value=(
                f"Source: **{profile.setback_source or 'Unknown'}**\n"
                f"When: **{discord.utils.format_dt(profile.setback_at, 'R')}**"
                if profile.setback_at is not None
                else f"Source: **{profile.setback_source or 'Unknown'}**"
            ),
            inline=False,
        )
    embed.add_field(
        name="Rest",
        value=(
            f"Status: **{'Resting' if profile.is_resting else 'Not Resting'}**\n"
            f"Rest Start: **{discord.utils.format_dt(profile.rest_start_time, 'R')}**\n"
            f"Rest Minutes: **{debug_state.rest_minutes}**\n"
            f"Projected Recovery: **+{debug_state.projected_rest_stamina_recovery} stamina, +{debug_state.projected_rest_hp_recovery} HP, +{debug_state.projected_rest_mana_recovery} mana**\n"
            f"Rest Snapshots: **ST {profile.rest_stamina_snapshot} | HP {profile.rest_hp_snapshot} | MP {profile.rest_mana_snapshot}**\n"
            f"Stamina Updated: **{discord.utils.format_dt(profile.stamina_updated_at, 'R')}**"
            if profile.is_resting and profile.rest_start_time is not None
            else (
                f"Status: **Not Resting**\n"
                f"Stamina Updated: **{discord.utils.format_dt(profile.stamina_updated_at, 'R')}**"
            )
        ),
        inline=False,
    )

    if active_exploration is None and pending_choice is None and active_combat is None:
        exploration_value = "No active exploration or pending street decision."
    elif active_exploration is not None:
        approach = get_explore_approach(active_exploration.approach)
        exploration_value = (
            f"Approach: **{approach.name}**\n"
            f"Channel: <#{active_exploration.channel_id}>\n"
            f"Start: **{discord.utils.format_dt(active_exploration.start_time, 'R')}**\n"
            f"End: **{discord.utils.format_dt(active_exploration.end_time, 'R')}**\n"
            f"Remaining: **{get_exploration_remaining_time(active_exploration)}**\n"
            f"Task Tracked: **{'Yes' if active_exploration.user_id in bot.exploration_tasks else 'No'}**"
        )
    elif pending_choice is not None:
        approach = get_explore_approach(pending_choice.approach)
        exploration_value = (
            f"Approach: **{approach.name}**\n"
            f"Pending Decision: **{pending_choice.event_key.replace('_', ' ').title()}**\n"
            f"Step: **{pending_choice.current_step}**\n"
            f"Channel: <#{pending_choice.channel_id}>\n"
            f"Message: **{pending_choice.message_id or 'Not posted'}**"
        )
    else:
        exploration_value = "Exploration timer is clear. Only the active combat state remains."
    embed.add_field(name="Exploration", value=exploration_value, inline=False)

    if active_training is not None:
        embed.add_field(
            name="Training",
            value=(
                f"Focus: **{active_training.stat_target.replace('_', ' ').title()}**\n"
                f"Duration: **{active_training.duration_minutes} minute(s)**\n"
                f"Channel: <#{active_training.channel_id}>\n"
                f"End: **{discord.utils.format_dt(active_training.end_time, 'R')}**\n"
                f"Remaining: **{get_training_remaining_time(active_training)}**\n"
                f"Task Tracked: **{'Yes' if active_training.user_id in bot.training_tasks else 'No'}**"
            ),
            inline=False,
        )

    if active_travel is not None:
        embed.add_field(
            name="Travel",
            value=(
                f"From: **{get_location_definition(active_travel.source_location).name}**\n"
                f"To: **{get_location_definition(active_travel.destination_location).name}**\n"
                f"Channel: <#{active_travel.channel_id}>\n"
                f"End: **{discord.utils.format_dt(active_travel.end_time, 'R')}**\n"
                f"Remaining: **{get_travel_remaining_time(active_travel)}**\n"
                f"Task Tracked: **{'Yes' if active_travel.user_id in bot.travel_tasks else 'No'}**"
            ),
            inline=False,
        )

    if active_work is not None:
        embed.add_field(
            name="Work",
            value=(
                f"Job: **{active_work.work_key.replace('_', ' ').title()}**\n"
                f"Channel: <#{active_work.channel_id}>\n"
                f"End: **{discord.utils.format_dt(active_work.end_time, 'R')}**\n"
                f"Remaining: **{get_work_remaining_time(active_work)}**\n"
                f"Task Tracked: **{'Yes' if active_work.user_id in bot.work_tasks else 'No'}**"
            ),
            inline=False,
        )

    if active_combat is not None:
        embed.add_field(
            name="Combat",
            value=(
                f"Encounter: **{active_combat.encounter_title}**\n"
                f"Enemy: **{active_combat.enemy_name}**\n"
                f"Round: **{active_combat.round_number}**\n"
                f"Player HP: **{active_combat.player_hp_current}/{active_combat.player_hp_max}**\n"
                f"Enemy HP: **{active_combat.enemy_hp_current}/{active_combat.enemy_hp_max}**\n"
                f"Channel: <#{active_combat.channel_id}>\n"
                f"Message: **{active_combat.message_id or 'Not posted'}**"
            ),
            inline=False,
        )
    return embed


def register_staff_commands(bot: "BleachBot") -> None:
    @bot.tree.command(name="purge", description="Delete recent messages from the current channel.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    async def purge(
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 500],
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                "This channel type does not support message purging.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted_count, failed_count, old_count = await _purge_channel_messages(
            channel,
            limit=amount,
            reason=f"Purged by {interaction.user} via /purge",
        )

        embed = discord.Embed(
            title="Messages Purged",
            description=f"Cleared recent chat history in {channel.mention}.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Deleted", value=f"**{deleted_count}** message(s)", inline=True)
        embed.add_field(name="Requested", value=f"**{amount}**", inline=True)
        embed.add_field(name="Failed", value=f"**{failed_count}**", inline=True)
        if old_count > 0:
            embed.add_field(
                name="Older Messages",
                value=f"**{old_count}** older message(s) were cleared with slower single deletes.",
                inline=False,
            )
        if failed_count > 0:
            embed.add_field(
                name="Note",
                value="Some messages could not be deleted because Discord returned a temporary error or the messages were already gone.",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="resetplayer", description="Completely wipe a player's profile so they must use /start again.")
    @app_commands.guild_only()
    @require_staff_rank("super_admin")
    async def resetplayer(interaction: discord.Interaction, player: discord.Member) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        debug_state = await get_player_debug_state(bot.db_pool, player.id)
        active_dungeon_run = await get_active_dungeon_run(bot.db_pool, player.id)
        cancelled_task = _cancel_player_exploration_task(bot, player.id)
        cancelled_training_task = _cancel_player_training_task(bot, player.id)
        cancelled_travel_task = _cancel_player_travel_task(bot, player.id)
        cancelled_work_task = _cancel_player_work_task(bot, player.id)
        cancelled_combat_task = _cancel_player_combat_task(bot, player.id)
        _clear_player_runtime_refs(bot, player.id)
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
            value="Yes" if cancelled_task else "No active exploration task",
            inline=True,
        )
        embed.add_field(
            name="Travel Task Cancelled",
            value="Yes" if cancelled_travel_task else "No active travel task",
            inline=True,
        )
        embed.add_field(
            name="Training Task Cancelled",
            value="Yes" if cancelled_training_task else "No active training task",
            inline=True,
        )
        embed.add_field(
            name="Work Task Cancelled",
            value="Yes" if cancelled_work_task else "No active work task",
            inline=True,
        )
        embed.add_field(
            name="Combat Cleared",
            value=(
                "Yes"
                if cancelled_combat_task or (debug_state is not None and debug_state.active_combat is not None)
                else "No active combat"
            ),
            inline=True,
        )
        embed.add_field(
            name="Dungeon Cleared",
            value="Yes" if active_dungeon_run is not None else "No active dungeon run",
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

        xp_to_next = get_xp_required_for_level(updated_player.level)
        stored_xp_text = f"**{updated_player.xp} / {xp_to_next}**" if xp_to_next > 0 else "**MAX / MAX**"
        embed = discord.Embed(
            title="XP Set",
            description=f"{player.mention}'s XP progress has been updated.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Level", value=f"**{updated_player.level}**", inline=True)
        embed.add_field(name="Stored XP", value=stored_xp_text, inline=True)
        embed.add_field(name="Levels Gained", value=f"**{levels_gained}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="setlevel", description="Set a player's level directly and reset stored XP to 0.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    async def setlevel(
        interaction: discord.Interaction,
        player: discord.Member,
        amount: app_commands.Range[int, 1],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        updated_player = await set_player_level(bot.db_pool, player.id, amount)
        if updated_player is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Level Set",
            description=f"{player.mention}'s level has been set directly for testing.",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Level", value=f"**{updated_player.level}**", inline=True)
        embed.add_field(name="Stored XP", value=f"**{updated_player.xp}**", inline=True)
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

        xp_to_next = get_xp_required_for_level(updated_player.level)
        stored_xp_text = f"**{updated_player.xp} / {xp_to_next}**" if xp_to_next > 0 else "**MAX / MAX**"
        embed = discord.Embed(
            title="XP Granted",
            description=f"{player.mention} gains **{amount} XP**.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Level", value=f"**{updated_player.level}**", inline=True)
        embed.add_field(name="Stored XP", value=stored_xp_text, inline=True)
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

    @bot.tree.command(name="settrait", description="Set a player's Soul Trait directly for testing.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    @app_commands.choices(trait=TRAIT_CHOICES)
    async def settrait(
        interaction: discord.Interaction,
        player: discord.Member,
        trait: app_commands.Choice[str],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        updated_player = await set_player_trait(bot.db_pool, player.id, trait.value)
        if updated_player is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        trait_data = get_trait_definition(updated_player.trait)
        embed = discord.Embed(
            title="Trait Updated",
            description=f"{player.mention}'s Soul Trait has been changed.",
            color=discord.Color.magenta(),
        )
        embed.add_field(name="Trait", value=f"**{trait_data.name}**", inline=True)
        embed.add_field(name="Effect", value=trait_data.effect, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="setstat", description="Set one of a player's core stats directly.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    @app_commands.choices(stat=STAT_CHOICES)
    async def setstat(
        interaction: discord.Interaction,
        player: discord.Member,
        stat: app_commands.Choice[str],
        amount: app_commands.Range[int, 0],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        updated_player = await set_player_stat(bot.db_pool, player.id, stat.value, amount)
        if updated_player is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        stat_labels = {
            "power": updated_player.power,
            "defense": updated_player.defense,
            "speed": updated_player.speed,
            "reiatsu": updated_player.reiatsu,
        }
        embed = discord.Embed(
            title="Stat Updated",
            description=f"{player.mention}'s **{stat.name}** has been set.",
            color=discord.Color.teal(),
        )
        embed.add_field(name=stat.name, value=f"**{stat_labels[stat.value]}**", inline=True)
        embed.add_field(
            name="Spiritual Pressure",
            value=f"**{updated_player.spiritual_pressure}**",
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
        cancelled_training_task = _cancel_player_training_task(bot, player.id)
        cancelled_travel_task = _cancel_player_travel_task(bot, player.id)
        cancelled_work_task = _cancel_player_work_task(bot, player.id)
        cancelled_combat_task = _cancel_player_combat_task(bot, player.id)
        result = await reset_player_action_timers(bot.db_pool, player.id)
        if result is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return
        _clear_player_runtime_refs(bot, player.id)

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
            name="Decision Cleared",
            value="Yes" if result.cleared_choice else "No",
            inline=True,
        )
        embed.add_field(
            name="Combat Cleared",
            value="Yes" if result.cleared_combat or cancelled_combat_task else "No",
            inline=True,
        )
        embed.add_field(
            name="Training Cleared",
            value="Yes" if result.cleared_training or cancelled_training_task else "No",
            inline=True,
        )
        embed.add_field(
            name="Travel Cleared",
            value="Yes" if result.cleared_travel or cancelled_travel_task else "No",
            inline=True,
        )
        embed.add_field(
            name="Work Cleared",
            value="Yes" if result.cleared_work or cancelled_work_task else "No",
            inline=True,
        )
        embed.add_field(
            name="Rest Cleared",
            value="Yes" if result.cleared_resting else "No",
            inline=True,
        )
        embed.add_field(name="Current Stamina", value=f"**{result.player.stamina_current}/{result.player.stamina_max}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="cleareffects", description="Remove all active effects from a player.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    async def cleareffects(interaction: discord.Interaction, player: discord.Member) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        result = await clear_player_effects(bot.db_pool, player.id)
        if result.status == "missing":
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Effects Cleared",
            description=f"All active effects have been removed from {player.mention}.",
            color=discord.Color.dark_teal(),
        )
        embed.add_field(name="Effects Removed", value=f"**{result.cleared_count}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="resetquest", description="Reset one quest record so a player can start it again.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    @app_commands.choices(quest=QUEST_CHOICES)
    async def resetquest(
        interaction: discord.Interaction,
        player: discord.Member,
        quest: app_commands.Choice[str],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        result = await staff_reset_player_quest(bot.db_pool, player.id, quest.value)
        if result.status == "missing_profile":
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return
        if result.status == "invalid_quest":
            await interaction.response.send_message("That quest is not recognized.", ephemeral=True)
            return
        if result.status == "not_found":
            await interaction.response.send_message(
                f"{player.mention} does not have a saved record for **{quest.name}**.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Quest Reset",
            description=f"{player.mention}'s quest record has been cleared.",
            color=discord.Color.dark_gold(),
        )
        embed.add_field(name="Quest", value=f"**{quest.name}**", inline=True)
        if result.previous_status is not None:
            embed.add_field(name="Previous Status", value=f"**{result.previous_status}**", inline=True)
        embed.add_field(
            name="Next Step",
            value="The player can accept or re-enter the quest flow again.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="resetnpc", description="Reset one recurring NPC chain for a player.")
    @app_commands.guild_only()
    @require_staff_rank("admin")
    @app_commands.choices(npc=NPC_CHOICES)
    async def resetnpc(
        interaction: discord.Interaction,
        player: discord.Member,
        npc: app_commands.Choice[str],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        result = await staff_reset_player_npc(bot.db_pool, player.id, npc.value)
        if result.status == "missing_profile":
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return
        if result.status == "invalid_npc":
            await interaction.response.send_message("That NPC chain is not recognized.", ephemeral=True)
            return
        if result.status == "not_found":
            await interaction.response.send_message(
                f"{player.mention} has no saved progress for **{npc.name}**.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="NPC Progress Reset",
            description=f"{player.mention}'s recurring NPC chain has been reset.",
            color=discord.Color.dark_green(),
        )
        embed.add_field(name="NPC", value=f"**{npc.name}**", inline=True)
        embed.add_field(name="Progress Cleared", value="Yes" if result.cleared_progress else "No", inline=True)
        embed.add_field(
            name="Pending Encounter Cleared",
            value="Yes" if result.cleared_pending_choice else "No",
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
            location_data,
            reason=f"Location updated by {interaction.user}",
        )

        embed = discord.Embed(
            title="Location Updated",
            description=f"{player.mention} has been moved to **{location_data.name}**.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Location", value=f"**{location_data.name}**", inline=True)
        embed.add_field(name="Room", value=format_location_room_reference(location_data), inline=True)
        if role_summary is not None:
            embed.add_field(name="Role Update", value=role_summary, inline=False)
        if role_warning is not None:
            embed.add_field(name="Role Warning", value=role_warning, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="forceresolve", description="Force a timed action to resolve immediately for testing.")
    @app_commands.guild_only()
    @require_staff_rank("mod")
    @app_commands.choices(action=FORCE_RESOLVE_CHOICES)
    async def forceresolve(
        interaction: discord.Interaction,
        player: discord.Member,
        action: app_commands.Choice[str],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        if action.value != "explore":
            await interaction.response.send_message("That force-resolve action is not supported yet.", ephemeral=True)
            return

        cancelled_task = _cancel_player_exploration_task(bot, player.id)
        resolution = await resolve_and_post_exploration(bot, player.id, force=True)
        if resolution is None:
            await interaction.response.send_message(
                f"{player.mention} does not have an active exploration to resolve.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Exploration Force-Resolved",
            description=f"{player.mention}'s exploration was resolved immediately and posted to the original channel.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Task Cancelled", value="Yes" if cancelled_task else "No tracked task", inline=True)
        if resolution.status == "instant" and resolution.resolution is not None:
            embed.add_field(name="Outcome", value=f"**{resolution.resolution.title}**", inline=True)
            embed.add_field(name="XP Gained", value=f"**{resolution.resolution.xp_gained}**", inline=True)
        elif resolution.status == "combat_prompt" and resolution.combat is not None:
            embed.add_field(name="Outcome", value="**Combat Encounter Posted**", inline=True)
            embed.add_field(name="Enemy", value=f"**{resolution.combat.enemy_name}**", inline=True)
        elif resolution.prompt is not None:
            embed.add_field(name="Outcome", value="**Street Decision Posted**", inline=True)
            embed.add_field(name="Step", value=f"**{resolution.prompt.step_number}/{resolution.prompt.total_steps}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="endfight", description="End an active fight by fight ID with no victor.")
    @app_commands.guild_only()
    @require_staff_rank("mod")
    async def endfight(
        interaction: discord.Interaction,
        fight_id: app_commands.Range[int, 1],
    ) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        result = await end_fight_without_victor(
            bot.db_pool,
            fight_id,
            closed_by=str(interaction.user),
        )

        if result.status == "missing":
            await interaction.followup.send(
                f"No fight with ID `{fight_id}` was found.",
                ephemeral=True,
            )
            return

        if result.status == "already_closed":
            outcome_text = result.final_outcome or "unknown"
            await interaction.followup.send(
                f"Fight `{fight_id}` is already closed with outcome `{outcome_text}`.",
                ephemeral=True,
            )
            return

        if result.combat is None:
            await interaction.followup.send(
                "I could not close that fight cleanly.",
                ephemeral=True,
            )
            return

        cancelled_combat_task = _cancel_player_combat_task(bot, result.combat.user_id)
        _clear_player_runtime_refs(bot, result.combat.user_id)

        closed_embed = discord.Embed(
            title="Fight Closed",
            description="This fight was ended by staff with **no victor**.",
            color=discord.Color.dark_orange(),
        )
        closed_embed.add_field(name="Fight ID", value=f"**{result.combat.fight_id}**", inline=True)
        closed_embed.add_field(name="Player", value=f"<@{result.combat.user_id}>", inline=True)
        closed_embed.add_field(name="Source", value=f"**{result.combat.source_kind.title()}**", inline=True)
        closed_embed.add_field(name="Encounter", value=f"**{result.combat.encounter_title}**", inline=False)
        closed_embed.set_footer(text=f"Closed by {interaction.user}")

        message_closed = await _close_fight_message(
            bot,
            combat=result.combat,
            embed=closed_embed,
        )

        embed = discord.Embed(
            title="Fight Ended",
            description=f"Fight `{result.combat.fight_id}` has been ended with **no victor**.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Player", value=f"<@{result.combat.user_id}>", inline=True)
        embed.add_field(name="Log Outcome", value=f"**{result.final_outcome or 'no_victor'}**", inline=True)
        embed.add_field(
            name="Combat Task Cancelled",
            value="Yes" if cancelled_combat_task else "No tracked task",
            inline=True,
        )
        embed.add_field(
            name="Message Closed",
            value="Yes" if message_closed else "No message update",
            inline=True,
        )
        if result.combat.source_kind == "dungeon":
            embed.add_field(
                name="Dungeon Follow-up",
                value="The dungeon run remains open. The player can use **/dungeon** to reopen the room.",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="playerstate", description="Show a compact admin debug sheet for a player.")
    @app_commands.guild_only()
    @require_staff_rank("mod")
    async def playerstate(interaction: discord.Interaction, player: discord.Member) -> None:
        if bot.db_pool is None:
            await interaction.response.send_message("Database is unavailable right now.", ephemeral=True)
            return

        debug_state = await get_player_debug_state(bot.db_pool, player.id)
        if debug_state is None:
            await interaction.response.send_message(
                f"{player.mention} does not have a profile yet.",
                ephemeral=True,
            )
            return

        embed = build_player_state_embed(bot, player, debug_state)
        await interaction.response.send_message(embed=embed, ephemeral=True)
