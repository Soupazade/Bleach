from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from src.data.exploration import get_explore_approach
from src.data.locations import get_location_definition
from src.models.combat import ActiveExplorationCombat
from src.services.combat_service import bind_combat_message, schedule_combat_task
from src.services.exploration.repository import (
    delete_pending_choice,
    fetch_pending_choice_record,
    update_pending_choice,
)
from src.services.exploration.resolution import resolve_exploration
from src.services.exploration.types import ExplorationDecisionPrompt, ExplorationPostResult, ExplorationResolution
from src.services.reputation_service import (
    format_reputation_change_text,
    format_reputation_xp_text,
    get_location_reputation_title,
)
from src.services.quest_service import record_quest_action
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


async def _get_messageable_channel(bot: "BleachBot", channel_id: int) -> discord.abc.Messageable | None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            logging.exception("Could not fetch channel %s for exploration posting.", channel_id)
            return None

    if not hasattr(channel, "send"):
        logging.warning("Channel %s is not messageable for exploration posting.", channel_id)
        return None

    return channel


async def _get_existing_exploration_message(
    bot: "BleachBot",
    *,
    channel: discord.abc.Messageable,
    user_id: int,
) -> discord.Message | None:
    message_id = bot.exploration_message_refs.get(user_id)
    if message_id is None or not hasattr(channel, "fetch_message"):
        return None
    try:
        return await channel.fetch_message(message_id)
    except discord.HTTPException:
        return None


def build_exploration_result_embed(resolution: ExplorationResolution) -> discord.Embed:
    location = get_location_definition(resolution.exploration.location)
    approach = get_explore_approach(resolution.exploration.approach)
    reputation_title = get_location_reputation_title(
        resolution.player,
        resolution.exploration.location,
    )
    xp_modifier_text = format_reputation_xp_text(
        resolution.reputation_xp_modifier_pct,
        reputation_title,
    )
    color_map = {
        "reward": get_explore_color("reward"),
        "choice": get_explore_color("choice"),
        "combat": get_explore_color("combat"),
        "flavor": get_explore_color("flavor"),
    }
    title_prefix = {
        "reward": "Reward",
        "choice": "Decision",
        "combat": "Combat",
        "flavor": "Street",
    }
    embed_title = f"{title_prefix[resolution.event_type]} | {resolution.title}"
    if resolution.event_type == "combat" and resolution.combat_outcome is not None:
        embed_title = f"Combat | {resolution.combat_outcome} | {resolution.title}"

    embed = discord.Embed(
        title=embed_title,
        description=resolution.description,
        color=color_map[resolution.event_type],
    )
    embed.add_field(
        name="This Run",
        value=build_explore_info_lines(
            f"Location: {location.name}",
            f"Approach: {approach.label}",
            f"Duration: {approach.duration_minutes} minutes",
            f"Reputation: {reputation_title}",
        ),
        inline=True,
    )
    embed.add_field(
        name="What Came Of It",
        value=build_explore_info_lines(
            "XP Gained: **"
            + str(resolution.xp_gained)
            + "**"
            + (f" {xp_modifier_text}" if xp_modifier_text is not None else "")
            + (f" {resolution.explore_xp_effect_text}" if resolution.explore_xp_effect_text is not None else ""),
            f"Level: **{resolution.player.level}**",
            f"XP Progress: **{resolution.player.xp}**",
            f"Reputation Shift: {format_reputation_change_text(resolution.reputation_change)}",
        ),
        inline=False,
    )

    if resolution.combat_outcome is not None:
        embed.add_field(
            name="Combat Result",
            value=build_explore_info_lines(
                f"Outcome: **{resolution.combat_outcome}**",
                f"Reputation: {reputation_title}",
            ),
            inline=False,
        )
        embed.add_field(
            name="Resources",
            value=build_explore_info_lines(
                f"HP Remaining: **{resolution.player.hp_current}/{resolution.player.hp_max}**",
                f"Mana Remaining: **{resolution.player.mana_current}/{resolution.player.mana_max}**",
                f"Stamina Used This Run: **{approach.stamina_cost}**",
            ),
            inline=False,
        )

    if resolution.applied_effect is not None:
        embed.add_field(
            name="Status Effect",
            value=build_explore_info_lines(
                resolution.applied_effect.title,
                resolution.applied_effect.description,
                resolution.applied_effect.summary_text,
            ),
            inline=False,
        )

    if resolution.applied_loot is not None:
        embed.add_field(
            name="Loot Found",
            value=build_explore_info_lines(
                resolution.applied_loot.summary_text,
                resolution.applied_loot.description,
            ),
            inline=False,
        )

    if resolution.levels_gained > 0:
        embed.add_field(
            name="Level Up",
            value=f"Your spiritual pressure rises. You climbed **{resolution.levels_gained}** level(s).",
            inline=False,
        )

    add_explore_divider(embed)
    embed.set_footer(text="The streets remember what kind of soul you are.")
    return embed


async def post_exploration_result(
    bot: "BleachBot",
    resolution: ExplorationResolution,
    *,
    preferred_message: discord.Message | None = None,
) -> None:
    channel = await _get_messageable_channel(bot, resolution.exploration.channel_id)
    if channel is None:
        return

    embed = build_exploration_result_embed(resolution)
    existing_message = preferred_message
    if existing_message is None:
        existing_message = await _get_existing_exploration_message(
            bot,
            channel=channel,
            user_id=resolution.exploration.user_id,
        )
    try:
        if existing_message is not None:
            await existing_message.edit(
                content=f"<@{resolution.exploration.user_id}>",
                embed=embed,
                view=None,
            )
        else:
            await channel.send(content=f"<@{resolution.exploration.user_id}>", embed=embed)
    except discord.HTTPException:
        logging.exception("Failed to send exploration result for user %s.", resolution.exploration.user_id)
    finally:
        bot.exploration_message_refs.pop(resolution.exploration.user_id, None)

    await record_quest_action(
        bot.db_pool,
        resolution.exploration.user_id,
        "explore_completed",
    )


async def post_exploration_choice_prompt(
    bot: "BleachBot",
    prompt: ExplorationDecisionPrompt,
) -> None:
    from src.ui.exploration_choice_view import ExplorationChoiceView, build_exploration_choice_embed

    async def _clear_pending_choice() -> None:
        if bot.db_pool is None:
            return

        async with bot.db_pool.acquire() as connection:
            async with connection.transaction():
                await delete_pending_choice(connection, prompt.session.user_id)

    channel = await _get_messageable_channel(bot, prompt.session.channel_id)
    if channel is None:
        await _clear_pending_choice()
        return

    view = ExplorationChoiceView(bot, prompt)
    embed = build_exploration_choice_embed(prompt)
    existing_message = await _get_existing_exploration_message(
        bot,
        channel=channel,
        user_id=prompt.session.user_id,
    )
    try:
        if existing_message is not None:
            await existing_message.edit(
                content=f"<@{prompt.session.user_id}>",
                embed=embed,
                view=view,
            )
            message = existing_message
        else:
            message = await channel.send(
                content=f"<@{prompt.session.user_id}>",
                embed=embed,
                view=view,
            )
    except discord.HTTPException:
        logging.exception("Failed to send exploration choice prompt for user %s.", prompt.session.user_id)
        await _clear_pending_choice()
        return

    bot.exploration_message_refs[prompt.session.user_id] = message.id

    if bot.db_pool is None:
        return

    async with bot.db_pool.acquire() as connection:
        async with connection.transaction():
            session_record = await fetch_pending_choice_record(connection, prompt.session.user_id, for_update=True)
            if session_record is None:
                return

            await update_pending_choice(
                connection,
                prompt.session.user_id,
                {"message_id": message.id},
            )


async def post_exploration_combat_prompt(
    bot: "BleachBot",
    combat: ActiveExplorationCombat,
) -> None:
    from src.ui.exploration_combat_view import ExplorationCombatView, build_exploration_combat_embed

    channel = await _get_messageable_channel(bot, combat.channel_id)
    if channel is None:
        return

    discord_user: discord.abc.User | None = None
    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        discord_user = channel.guild.get_member(combat.user_id)
    if discord_user is None:
        discord_user = bot.get_user(combat.user_id)
    if discord_user is None:
        try:
            discord_user = await bot.fetch_user(combat.user_id)
        except discord.HTTPException:
            discord_user = None

    view = ExplorationCombatView(bot, combat)
    embed = build_exploration_combat_embed(combat, discord_user)
    existing_message = await _get_existing_exploration_message(
        bot,
        channel=channel,
        user_id=combat.user_id,
    )

    try:
        if existing_message is not None:
            await existing_message.edit(
                content=f"<@{combat.user_id}>",
                embed=embed,
                view=view,
            )
            message = existing_message
        else:
            message = await channel.send(
                content=f"<@{combat.user_id}>",
                embed=embed,
                view=view,
            )
    except discord.HTTPException:
        logging.exception("Failed to send exploration combat prompt for user %s.", combat.user_id)
        return

    bot.exploration_message_refs[combat.user_id] = message.id
    rebound = await bind_combat_message(bot.db_pool, fight_id=combat.fight_id, message_id=message.id)
    if rebound is not None:
        schedule_combat_task(bot, rebound)


async def resolve_and_post_exploration(
    bot: "BleachBot",
    user_id: int,
    *,
    force: bool = False,
) -> ExplorationPostResult | None:
    post_result = await resolve_exploration(bot.db_pool, user_id, force=force)
    if post_result is None:
        return None

    if post_result.status == "instant" and post_result.resolution is not None:
        await post_exploration_result(bot, post_result.resolution)
    elif post_result.status == "choice_prompt" and post_result.prompt is not None:
        await post_exploration_choice_prompt(bot, post_result.prompt)
    elif post_result.status == "combat_prompt" and post_result.combat is not None:
        await post_exploration_combat_prompt(bot, post_result.combat)

    return post_result
