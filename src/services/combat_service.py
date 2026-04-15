from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import io
import logging
from typing import TYPE_CHECKING, Literal

import discord
from asyncpg import Connection, Pool, Record

from src.data.combat import CombatEnemyTemplate, get_enemy_for_exploration_combat
from src.data.locations import RUKONGAI_STREETS, get_location_definition
from src.models.player import PlayerProfile
from src.services.combat.abilities import list_unlocked_player_abilities
from src.services.combat.engine import resolve_combat_round
from src.services.combat.repository import (
    append_fight_log_event,
    bind_fight_log_to_fight,
    create_active_combat,
    create_fight_log,
    delete_active_combat,
    fetch_active_combat_record,
    fetch_active_combat_record_by_message,
    finalize_fight_log,
    get_active_combat,
    get_active_combat_by_message,
    get_fight_log,
    list_active_combats,
    session_from_record,
    update_active_combat,
    update_active_combat_message,
)
from src.services.combat.types import (
    CombatAction,
    CombatChoice,
    CombatEntity,
    CombatSession,
)
from src.services.effect_service import EffectiveCombatSnapshot, build_effective_combat_snapshot, list_active_player_effects_for_connection
from src.services.inventory_service import consume_inventory_item_for_connection
from src.services.player_service import get_or_sync_player_record, update_player_record
from src.services.role_service import sync_member_location_role
from src.services.status_service import grant_wounded_status

if TYPE_CHECKING:
    from src.main import BleachBot
    from src.services.exploration.types import ExplorationResolution


COMBAT_TURN_TIMEOUT = timedelta(minutes=2)


@dataclass(slots=True)
class CombatAdvanceResult:
    status: Literal["missing", "blocked", "updated", "resolved"]
    combat: CombatSession | None = None
    resolution: "ExplorationResolution | None" = None
    fight_embed: discord.Embed | None = None
    blackout_applied: bool = False
    resolution_type: Literal["victory", "defeat", "retreated"] | None = None
    message: str | None = None


@dataclass(slots=True)
class StartFightTestResult:
    status: Literal[
        "started",
        "missing_profile",
        "resting",
        "busy",
        "active_combat",
    ]
    player: PlayerProfile | None = None
    combat: CombatSession | None = None
    reason: str | None = None


def _resource_ratio(current: int, maximum: int) -> float:
    if maximum <= 0:
        return 0.0
    return max(0.0, min(1.0, current / maximum))


def project_profile_hp_from_combat(player: PlayerProfile, combat: CombatSession) -> int:
    return max(1, min(player.hp_max, int(round(player.hp_max * _resource_ratio(combat.player.hp_current, combat.player.hp_max)))))


def project_profile_mana_from_combat(player: PlayerProfile, combat: CombatSession) -> int:
    return max(0, min(player.mana_max, int(round(player.mana_max * _resource_ratio(combat.player.mana_current, combat.player.mana_max)))))


def _build_player_entity(player: PlayerProfile, snapshot: EffectiveCombatSnapshot | None = None) -> CombatEntity:
    combat_snapshot = snapshot or EffectiveCombatSnapshot(
        hp_current=player.hp_current,
        hp_max=player.hp_max,
        mana_current=player.mana_current,
        mana_max=player.mana_max,
        power=player.power,
        defense=player.defense,
        speed=player.speed,
        reiatsu=player.reiatsu,
    )
    hp_ratio = _resource_ratio(player.hp_current, max(1, player.hp_max))
    mana_ratio = _resource_ratio(player.mana_current, max(1, player.mana_max))
    hp_max = max(1, player.hp_max + (combat_snapshot.defense * 10))
    mana_max = max(1, player.mana_max + (combat_snapshot.reiatsu * 5))
    return CombatEntity(
        entity_id="player",
        name="Player",
        level=player.level,
        race=player.race,
        rank=player.rank,
        hp_current=max(1, min(hp_max, int(round(hp_max * hp_ratio)))),
        hp_max=hp_max,
        mana_current=max(0, min(mana_max, int(round(mana_max * mana_ratio)))),
        mana_max=mana_max,
        power=combat_snapshot.power,
        defense=combat_snapshot.defense,
        speed=combat_snapshot.speed,
        reiatsu=combat_snapshot.reiatsu,
        abilities=tuple(ability.key for ability in list_unlocked_player_abilities(player.level)),
    )


def _build_enemy_entity(enemy_template: CombatEnemyTemplate) -> CombatEntity:
    hp_max = enemy_template.hp + (enemy_template.defense * 10)
    mana_max = enemy_template.mana + (enemy_template.reiatsu * 5)
    return CombatEntity(
        entity_id=enemy_template.key,
        name=enemy_template.name,
        level=enemy_template.level,
        race=enemy_template.race,
        rank=enemy_template.rank,
        hp_current=hp_max,
        hp_max=hp_max,
        mana_current=mana_max,
        mana_max=mana_max,
        power=enemy_template.power,
        defense=enemy_template.defense,
        speed=enemy_template.speed,
        reiatsu=enemy_template.reiatsu,
        abilities=enemy_template.abilities,
        attack_bias=enemy_template.attack_bias,
        guard_bias=enemy_template.guard_bias,
        ability_bias=enemy_template.ability_bias,
    )


def _build_initial_log_text(player: PlayerProfile, enemy_template: CombatEnemyTemplate, source_kind: str) -> str:
    return "\n".join(
        [
            f"Fight Start | source={source_kind}",
            f"Player | level={player.level} race={player.race} rank={player.rank} power={player.power} defense={player.defense} speed={player.speed} reiatsu={player.reiatsu}",
            f"Enemy | name={enemy_template.name} level={enemy_template.level} power={enemy_template.power} defense={enemy_template.defense} speed={enemy_template.speed} reiatsu={enemy_template.reiatsu} abilities={','.join(enemy_template.abilities) or 'none'}",
        ]
    )


async def create_active_exploration_combat(
    connection: Connection,
    *,
    exploration,
    player: PlayerProfile,
    encounter_title: str,
    encounter_description: str,
    resolution_title: str,
    resolution_description: str,
    reward_xp_win: int,
    reward_xp_lose: int,
    reputation_change: int = 0,
    enemy_template: CombatEnemyTemplate | None = None,
    combat_snapshot: EffectiveCombatSnapshot | None = None,
    initial_focus_bonus: int = 0,
    message_id: int | None = None,
) -> CombatSession:
    del initial_focus_bonus
    enemy = enemy_template or get_enemy_for_exploration_combat(
        exploration.location,
        encounter_title=encounter_title,
        approach_risk="medium",
        player_level=player.level,
    )
    fight_log = await create_fight_log(
        connection,
        user_id=player.user_id,
        source_kind="exploration",
        readable_log=_build_initial_log_text(player, enemy, "exploration"),
    )
    session = await create_active_combat(
        connection,
        fight_log_id=fight_log.fight_log_id,
        user_id=player.user_id,
        channel_id=exploration.channel_id,
        message_id=message_id,
        source_kind="exploration",
        location=exploration.location,
        approach=exploration.approach,
        encounter_title=encounter_title,
        encounter_description=encounter_description,
        resolution_title=resolution_title,
        resolution_description=resolution_description,
        reward_xp_win=reward_xp_win,
        reward_xp_lose=reward_xp_lose,
        reputation_change=reputation_change,
        player=_build_player_entity(player, combat_snapshot),
        enemies=(_build_enemy_entity(enemy),),
    )
    await bind_fight_log_to_fight(connection, fight_log_id=fight_log.fight_log_id, fight_id=session.fight_id)
    return session


async def create_active_dungeon_combat(
    connection: Connection,
    *,
    user_id: int,
    channel_id: int,
    message_id: int | None,
    location: str,
    approach: str,
    player: PlayerProfile,
    room,
    combat_snapshot: EffectiveCombatSnapshot | None = None,
) -> CombatSession:
    combat_definition = room.combat
    if combat_definition is None:
        raise ValueError(f"Room {room.key} does not define a combat encounter.")

    enemy = combat_definition.enemy_template
    fight_log = await create_fight_log(
        connection,
        user_id=user_id,
        source_kind="dungeon",
        readable_log=_build_initial_log_text(player, enemy, "dungeon"),
    )
    session = await create_active_combat(
        connection,
        fight_log_id=fight_log.fight_log_id,
        user_id=user_id,
        channel_id=channel_id,
        message_id=message_id,
        source_kind="dungeon",
        location=location,
        approach=approach,
        encounter_title=combat_definition.encounter_title,
        encounter_description=combat_definition.encounter_description,
        resolution_title=combat_definition.resolution_title,
        resolution_description=combat_definition.resolution_description,
        reward_xp_win=combat_definition.xp_reward_win,
        reward_xp_lose=combat_definition.xp_reward_lose,
        reputation_change=combat_definition.reputation_change_win,
        player=_build_player_entity(player, combat_snapshot),
        enemies=(_build_enemy_entity(enemy),),
    )
    await bind_fight_log_to_fight(connection, fight_log_id=fight_log.fight_log_id, fight_id=session.fight_id)
    return session


async def delete_active_exploration_combat(connection: Connection, user_id: int) -> None:
    await delete_active_combat(connection, user_id)


async def get_active_exploration_combat(pool: Pool | None, user_id: int) -> CombatSession | None:
    return await get_active_combat(pool, user_id)


async def get_active_exploration_combat_by_message(pool: Pool | None, message_id: int) -> CombatSession | None:
    return await get_active_combat_by_message(pool, message_id)


def _build_timeout_deadline() -> datetime:
    return datetime.now(timezone.utc) + COMBAT_TURN_TIMEOUT


async def bind_combat_message(pool: Pool | None, *, fight_id: int, message_id: int) -> CombatSession | None:
    if pool is None:
        return None
    async with pool.acquire() as connection:
        async with connection.transaction():
            return await update_active_combat_message(connection, fight_id=fight_id, message_id=message_id)


async def _advance_combat(
    pool: Pool | None,
    *,
    message_id: int,
    user_id: int,
    choice: CombatChoice,
) -> CombatAdvanceResult:
    if pool is None:
        return CombatAdvanceResult(status="missing")

    async with pool.acquire() as connection:
        async with connection.transaction():
            record = await fetch_active_combat_record_by_message(connection, message_id, for_update=True)
            if record is None:
                return CombatAdvanceResult(status="missing")

            session = session_from_record(record)
            if session.user_id != user_id:
                return CombatAdvanceResult(status="missing")

            if choice.action == "bandage":
                if session.player.hp_current >= session.player.hp_max:
                    return CombatAdvanceResult(
                        status="blocked",
                        combat=session,
                        message="Your HP is already full. Save the bandages for when the street actually opens you up.",
                    )
                consumed = await consume_inventory_item_for_connection(
                    connection,
                    user_id=user_id,
                    item_key="bandages",
                    quantity=1,
                )
                if consumed <= 0:
                    return CombatAdvanceResult(
                        status="blocked",
                        combat=session,
                        message="You reach for a bandage, but your hands come up empty.",
                    )
                bandage_heal = max(1, int(round(session.player.hp_max * 0.25)))
                session = replace(
                    session,
                    player=replace(
                        session.player,
                        hp_current=min(session.player.hp_max, session.player.hp_current + bandage_heal),
                    ),
                )
                choice = CombatChoice(action="bandage", reason=f"Bandage restores {bandage_heal} HP.")

            round_outcome = resolve_combat_round(session, choice)
            updated_session = round_outcome.session

            await append_fight_log_event(
                connection,
                fight_log_id=updated_session.fight_log_id,
                detail_text=round_outcome.log_event.detail_text,
                payload=round_outcome.log_event.payload,
            )

            if round_outcome.resolution_type is None:
                updated_session = replace(updated_session, turn_deadline_at=_build_timeout_deadline())
                persisted = await update_active_combat(connection, fight_id=updated_session.fight_id, session=updated_session)
                return CombatAdvanceResult(status="updated", combat=persisted)

            if updated_session.source_kind == "exploration":
                from src.services.exploration.rewards import finalize_combat_resolution

                resolution = await finalize_combat_resolution(
                    connection,
                    combat=updated_session,
                    base_xp=round_outcome.xp_reward,
                    combat_outcome="Retreated" if round_outcome.resolution_type == "retreated" else ("Victory" if round_outcome.resolution_type == "victory" else "Setback"),
                    title=round_outcome.resolution_title or updated_session.resolution_title,
                    description=round_outcome.resolution_description or updated_session.resolution_description,
                    reputation_change=updated_session.reputation_change,
                )
                await finalize_fight_log(connection, fight_log_id=updated_session.fight_log_id, outcome=round_outcome.resolution_type)
                return CombatAdvanceResult(
                    status="resolved",
                    combat=updated_session,
                    resolution=resolution,
                    blackout_applied=round_outcome.resolution_type == "defeat",
                    resolution_type=round_outcome.resolution_type,
                )

            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                await delete_active_combat(connection, user_id)
                await finalize_fight_log(connection, fight_log_id=updated_session.fight_log_id, outcome="missing_profile")
                return CombatAdvanceResult(status="missing")

            player = PlayerProfile.from_record(player_sync.record)
            updates = {
                "hp_current": project_profile_hp_from_combat(player, updated_session),
                "mana_current": project_profile_mana_from_combat(player, updated_session),
            }
            blackout_applied = round_outcome.resolution_type == "defeat"
            if blackout_applied:
                updates["hp_current"] = 1
                updates["location"] = RUKONGAI_STREETS.key
                await grant_wounded_status(connection, user_id)
            updated_player_record = await update_player_record(connection, user_id, updates)
            updated_player = PlayerProfile.from_record(updated_player_record)
            await delete_active_combat(connection, user_id)
            await finalize_fight_log(connection, fight_log_id=updated_session.fight_log_id, outcome=round_outcome.resolution_type)
            from src.ui.exploration_combat_view import build_fight_result_embed

            result_embed = build_fight_result_embed(
                combat=updated_session,
                player=updated_player,
                outcome=round_outcome.resolution_type,
                title=round_outcome.resolution_title or updated_session.resolution_title,
                description=round_outcome.resolution_description or updated_session.resolution_description,
            )
            return CombatAdvanceResult(
                status="resolved",
                combat=updated_session,
                fight_embed=result_embed,
                blackout_applied=blackout_applied,
                resolution_type=round_outcome.resolution_type,
            )


async def _remove_old_combat_message(message: discord.Message | None) -> None:
    if message is None:
        return
    try:
        await message.delete()
    except discord.HTTPException:
        try:
            await message.edit(view=None)
        except discord.HTTPException:
            pass


async def _post_active_combat_message(
    bot: "BleachBot",
    combat: CombatSession,
    *,
    discord_user: discord.abc.User | None = None,
    old_message: discord.Message | None = None,
) -> CombatSession | None:
    from src.ui.exploration_combat_view import ExplorationCombatView, build_exploration_combat_embed

    channel = bot.get_channel(combat.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(combat.channel_id)
        except discord.HTTPException:
            logging.exception("Could not fetch channel %s for combat.", combat.channel_id)
            return None

    if not hasattr(channel, "send"):
        return None

    if discord_user is None:
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
    message: discord.Message | None = None
    if old_message is not None:
        try:
            await old_message.edit(
                content=f"<@{combat.user_id}>",
                embed=embed,
                view=view,
            )
            message = old_message
        except discord.HTTPException:
            message = None

    if message is None:
        message = await channel.send(content=f"<@{combat.user_id}>", embed=embed, view=view)
        if old_message is not None and old_message.id != message.id:
            await _remove_old_combat_message(old_message)

    rebound = await bind_combat_message(bot.db_pool, fight_id=combat.fight_id, message_id=message.id)
    if rebound is None:
        return None
    if combat.source_kind == "exploration":
        bot.exploration_message_refs[combat.user_id] = message.id
    schedule_combat_task(bot, rebound)
    return rebound


async def resolve_and_post_combat_action(
    bot: "BleachBot",
    *,
    message_id: int,
    user_id: int,
    action: CombatAction,
    ability_key: str | None = None,
    old_message: discord.Message | None = None,
) -> CombatAdvanceResult:
    bot.combat_warning_rounds.pop(user_id, None)
    result = await _advance_combat(
        bot.db_pool,
        message_id=message_id,
        user_id=user_id,
        choice=CombatChoice(action=action, ability_key=ability_key),
    )
    if result.status == "updated" and result.combat is not None:
        await _post_active_combat_message(bot, result.combat, old_message=old_message)
        return result
    if result.status == "blocked":
        return result
    if result.status == "resolved" and result.resolution is not None:
        channel = None if old_message is None else old_message.channel
        if channel is None and result.combat is not None:
            channel = bot.get_channel(result.combat.channel_id)
        if channel is not None and hasattr(channel, "send"):
            from src.services.exploration.posting import post_exploration_result

            await post_exploration_result(
                bot,
                result.resolution,
                preferred_message=old_message,
            )
            if result.blackout_applied:
                await _sync_blackout_location_role(bot, result.combat.user_id)
        return result
    if result.status == "resolved" and result.combat is not None and result.combat.source_kind == "dungeon":
        from src.services.dungeon_service import resolve_dungeon_combat
        from src.ui.dungeon_view import (
            DungeonView,
            build_dungeon_completion_embed,
            build_dungeon_failure_embed,
            build_dungeon_room_embed,
        )

        dungeon_result = await resolve_dungeon_combat(
            bot.db_pool,
            user_id=result.combat.user_id,
            outcome=result.resolution_type or "defeat",
        )
        if old_message is None:
            return result
        if dungeon_result.status == "updated" and dungeon_result.player is not None and dungeon_result.run is not None:
            await old_message.edit(
                content=f"<@{result.combat.user_id}>",
                embed=build_dungeon_room_embed(dungeon_result.player, dungeon_result.run),
                view=DungeonView(bot, dungeon_result.run),
            )
            return result
        if dungeon_result.status == "completed" and dungeon_result.player is not None and dungeon_result.progress is not None:
            await old_message.edit(
                content=f"<@{result.combat.user_id}>",
                embed=build_dungeon_completion_embed(
                    dungeon_result.player,
                    dungeon_key=result.combat.approach,
                    progress=dungeon_result.progress,
                ),
                view=None,
            )
            return result
        if dungeon_result.status == "failed" and dungeon_result.player is not None and dungeon_result.progress is not None:
            await old_message.edit(
                content=f"<@{result.combat.user_id}>",
                embed=build_dungeon_failure_embed(
                    dungeon_result.player,
                    dungeon_key=result.combat.approach,
                    progress=dungeon_result.progress,
                    outcome=result.resolution_type or "defeat",
                ),
                view=None,
            )
            if result.blackout_applied:
                await _sync_blackout_location_role(bot, result.combat.user_id)
            return result
        return result
    if result.status == "resolved" and result.fight_embed is not None and result.combat is not None:
        if old_message is not None:
            try:
                await old_message.edit(
                    content=f"<@{result.combat.user_id}>",
                    embed=result.fight_embed,
                    view=None,
                )
            except discord.HTTPException:
                channel = old_message.channel
                if hasattr(channel, "send"):
                    await channel.send(content=f"<@{result.combat.user_id}>", embed=result.fight_embed)
        else:
            channel = bot.get_channel(result.combat.channel_id)
            if channel is not None and hasattr(channel, "send"):
                await channel.send(content=f"<@{result.combat.user_id}>", embed=result.fight_embed)
        if result.blackout_applied:
            await _sync_blackout_location_role(bot, result.combat.user_id)
        return result
    return result


async def advance_combat_state(
    pool: Pool | None,
    *,
    message_id: int,
    user_id: int,
    action: CombatAction,
    ability_key: str | None = None,
) -> CombatAdvanceResult:
    return await _advance_combat(
        pool,
        message_id=message_id,
        user_id=user_id,
        choice=CombatChoice(action=action, ability_key=ability_key),
    )


async def _sync_blackout_location_role(bot: "BleachBot", user_id: int) -> None:
    guilds = bot.guilds
    for guild in guilds:
        member = guild.get_member(user_id)
        if member is None:
            continue
        try:
            await sync_member_location_role(member, get_location_definition(RUKONGAI_STREETS.key), reason="Combat blackout")
        except Exception:
            logging.exception("Failed to sync blackout location role for user %s.", user_id)
        return


async def _run_combat_task(bot: "BleachBot", user_id: int, fight_id: int) -> None:
    try:
        while True:
            combat = await get_active_combat(bot.db_pool, user_id)
            if combat is None or combat.fight_id != fight_id:
                break
            delay = (combat.turn_deadline_at - datetime.now(timezone.utc)).total_seconds()
            warned_round = bot.combat_warning_rounds.get(user_id)
            if delay > 60 and warned_round != combat.round_number:
                await asyncio.sleep(delay - 60)
                combat = await get_active_combat(bot.db_pool, user_id)
                if combat is None or combat.fight_id != fight_id:
                    break
                if combat.turn_deadline_at <= datetime.now(timezone.utc):
                    continue
                if bot.combat_warning_rounds.get(user_id) != combat.round_number:
                    channel = bot.get_channel(combat.channel_id)
                    if channel is None:
                        try:
                            channel = await bot.fetch_channel(combat.channel_id)
                        except discord.HTTPException:
                            channel = None
                    if channel is not None and hasattr(channel, "send"):
                        try:
                            await channel.send(
                content=f"<@{combat.user_id}>",
                embed=discord.Embed(
                    title="Turn Warning",
                    description="If you do not act within **1 minute**, the fight will stay open until you return.",
                    color=discord.Color.orange(),
                ),
            )
                        except discord.HTTPException:
                            pass
                    bot.combat_warning_rounds[user_id] = combat.round_number
                continue
            if delay > 0:
                await asyncio.sleep(delay + 0.25)
            combat = await get_active_combat(bot.db_pool, user_id)
            if combat is None or combat.fight_id != fight_id:
                break
            if combat.turn_deadline_at > datetime.now(timezone.utc):
                continue
            break
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Unexpected combat task failure for user %s.", user_id)
    finally:
        bot.combat_tasks.pop(user_id, None)
        bot.combat_warning_rounds.pop(user_id, None)


def schedule_combat_task(bot: "BleachBot", combat: CombatSession) -> None:
    existing = bot.combat_tasks.get(combat.user_id)
    if existing is not None:
        existing.cancel()
    bot.combat_tasks[combat.user_id] = asyncio.create_task(_run_combat_task(bot, combat.user_id, combat.fight_id))


async def restore_combat_tasks(bot: "BleachBot") -> None:
    active_combats = await list_active_combats(bot.db_pool)
    for combat in active_combats:
        await _post_active_combat_message(bot, combat)


async def post_combat_prompt(
    bot: "BleachBot",
    combat: CombatSession,
) -> None:
    await _post_active_combat_message(bot, combat)


async def start_fight_test(
    pool: Pool | None,
    *,
    user_id: int,
    channel_id: int,
) -> StartFightTestResult:
    if pool is None:
        return StartFightTestResult(status="missing_profile")

    from src.services.exploration_service import fetch_active_exploration_record, fetch_pending_choice_record
    from src.services.training_service import fetch_active_training_record
    from src.services.travel_service import fetch_active_travel_record

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return StartFightTestResult(status="missing_profile")
            player = PlayerProfile.from_record(player_sync.record)
            if player.is_resting:
                return StartFightTestResult(status="resting", player=player)
            if await fetch_active_combat_record(connection, user_id, for_update=True) is not None:
                return StartFightTestResult(status="active_combat", player=player)
            if await fetch_active_exploration_record(connection, user_id, for_update=True) is not None:
                return StartFightTestResult(status="busy", player=player, reason="Finish your exploration first.")
            if await fetch_pending_choice_record(connection, user_id, for_update=True) is not None:
                return StartFightTestResult(status="busy", player=player, reason="A pending exploration choice is waiting.")
            if await fetch_active_training_record(connection, user_id, for_update=True) is not None:
                return StartFightTestResult(status="busy", player=player, reason="Finish your training first.")
            if await fetch_active_travel_record(connection, user_id, for_update=True) is not None:
                return StartFightTestResult(status="busy", player=player, reason="Finish your travel first.")

            active_effects = await list_active_player_effects_for_connection(connection, user_id)
            snapshot = build_effective_combat_snapshot(player, active_effects)
            enemy = get_enemy_for_exploration_combat(
                player.location,
                encounter_title="Fight Test",
                approach_risk="medium",
                player_level=player.level,
            )
            fight_log = await create_fight_log(
                connection,
                user_id=user_id,
                source_kind="fighttest",
                readable_log=_build_initial_log_text(player, enemy, "fighttest"),
            )
            combat = await create_active_combat(
                connection,
                fight_log_id=fight_log.fight_log_id,
                user_id=user_id,
                channel_id=channel_id,
                message_id=None,
                source_kind="fighttest",
                location=player.location,
                approach="fighttest",
                encounter_title=f"Combat Test - {enemy.name}",
                encounter_description="A live combat drill snaps into place so you can test the system under pressure.",
                resolution_title="You Put the Bandit Down",
                resolution_description="The test fight settles cleanly. You stay standing, the bandit does not, and the system has another round of data to chew on.",
                reward_xp_win=0,
                reward_xp_lose=0,
                reputation_change=0,
                player=_build_player_entity(player, snapshot),
                enemies=(_build_enemy_entity(enemy),),
            )
            await bind_fight_log_to_fight(connection, fight_log_id=fight_log.fight_log_id, fight_id=combat.fight_id)
            return StartFightTestResult(status="started", player=player, combat=combat)


async def build_fight_log_file(pool: Pool | None, fight_log_id: int) -> tuple[str, io.BytesIO] | None:
    record = await get_fight_log(pool, fight_log_id)
    if record is None:
        return None
    payload = record.readable_log.strip() + "\n"
    return f"fightlog-{fight_log_id}.txt", io.BytesIO(payload.encode("utf-8"))
