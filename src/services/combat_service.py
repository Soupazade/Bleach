from __future__ import annotations

from dataclasses import dataclass, replace
import random
from typing import Literal

from asyncpg import Connection, Pool, Record

from src.data.combat import CombatEnemyTemplate, get_enemy_for_exploration_combat
from src.data.exploration import get_explore_approach
from src.models.combat import ActiveExplorationCombat
from src.models.exploration import ActiveExploration
from src.models.player import PlayerProfile


CombatAction = Literal["attack", "guard", "focus", "retreat"]

ACTIVE_EXPLORATION_COMBAT_COLUMNS = """
    user_id,
    channel_id,
    message_id,
    location,
    approach,
    encounter_title,
    encounter_description,
    resolution_title,
    resolution_description,
    enemy_name,
    enemy_hp_current,
    enemy_hp_max,
    enemy_power,
    enemy_defense,
    enemy_speed,
    reward_xp_win,
    reward_xp_lose,
    reputation_change,
    player_hp_current,
    player_hp_max,
    player_mana_current,
    player_mana_max,
    player_power,
    player_defense,
    player_speed,
    player_reiatsu,
    round_number,
    focus_bonus,
    guard_active,
    last_round_summary,
    created_at,
    updated_at
"""

@dataclass(slots=True)
class CombatOutcome:
    combat: ActiveExplorationCombat
    title: str
    description: str
    xp_reward: int
    combat_outcome: Literal["Victory", "Setback", "Retreated"]
    reputation_change: int
    player_hp_current: int
    player_mana_current: int


@dataclass(slots=True)
class CombatAdvanceResult:
    status: Literal["updated", "resolved"]
    combat: ActiveExplorationCombat | None = None
    outcome: CombatOutcome | None = None


async def fetch_active_combat_record(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_EXPLORATION_COMBAT_COLUMNS}
        FROM active_exploration_combats
        WHERE user_id = $1
        {lock_clause}
        """,
        user_id,
    )


async def fetch_active_combat_record_by_message(
    connection: Connection,
    message_id: int,
    *,
    for_update: bool = False,
) -> Record | None:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetchrow(
        f"""
        SELECT {ACTIVE_EXPLORATION_COMBAT_COLUMNS}
        FROM active_exploration_combats
        WHERE message_id = $1
        {lock_clause}
        """,
        message_id,
    )


async def get_active_exploration_combat(pool: Pool | None, user_id: int) -> ActiveExplorationCombat | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_combat_record(connection, user_id)
        if record is None:
            return None

        return ActiveExplorationCombat.from_record(record)


async def get_active_exploration_combat_by_message(
    pool: Pool | None,
    message_id: int,
) -> ActiveExplorationCombat | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        record = await fetch_active_combat_record_by_message(connection, message_id)
        if record is None:
            return None

        return ActiveExplorationCombat.from_record(record)


async def create_active_exploration_combat(
    connection: Connection,
    *,
    exploration: ActiveExploration,
    player: PlayerProfile,
    encounter_title: str,
    encounter_description: str,
    resolution_title: str,
    resolution_description: str,
    reward_xp_win: int,
    reward_xp_lose: int,
    reputation_change: int = 0,
    enemy_template: CombatEnemyTemplate | None = None,
    message_id: int | None = None,
) -> ActiveExplorationCombat:
    approach = get_explore_approach(exploration.approach)
    enemy = enemy_template or get_enemy_for_exploration_combat(
        exploration.location,
        encounter_title=encounter_title,
        approach_risk=approach.risk_tier,
    )
    record = await connection.fetchrow(
        f"""
        INSERT INTO active_exploration_combats (
            user_id,
            channel_id,
            message_id,
            location,
            approach,
            encounter_title,
            encounter_description,
            resolution_title,
            resolution_description,
            enemy_name,
            enemy_hp_current,
            enemy_hp_max,
            enemy_power,
            enemy_defense,
            enemy_speed,
            reward_xp_win,
            reward_xp_lose,
            reputation_change,
            player_hp_current,
            player_hp_max,
            player_mana_current,
            player_mana_max,
            player_power,
            player_defense,
            player_speed,
            player_reiatsu,
            round_number,
            focus_bonus,
            guard_active,
            last_round_summary
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28, $29, $30
        )
        RETURNING {ACTIVE_EXPLORATION_COMBAT_COLUMNS}
        """,
        exploration.user_id,
        exploration.channel_id,
        message_id,
        exploration.location,
        exploration.approach,
        encounter_title,
        encounter_description,
        resolution_title,
        resolution_description,
        enemy.name,
        enemy.hp,
        enemy.hp,
        enemy.power,
        enemy.defense,
        enemy.speed,
        reward_xp_win,
        reward_xp_lose,
        reputation_change,
        max(1, player.hp_current),
        player.hp_max,
        player.mana_current,
        player.mana_max,
        player.power,
        player.defense,
        player.speed,
        player.reiatsu,
        1,
        0,
        False,
        "The alley tightens. One bad exchange and the whole run goes sideways.",
    )
    return ActiveExplorationCombat.from_record(record)


async def update_active_exploration_combat(
    connection: Connection,
    user_id: int,
    fields: dict[str, object],
) -> ActiveExplorationCombat:
    assignments: list[str] = []
    values: list[object] = []
    for index, (column_name, value) in enumerate(fields.items(), start=1):
        assignments.append(f"{column_name} = ${index}")
        values.append(value)

    values.append(user_id)
    record = await connection.fetchrow(
        f"""
        UPDATE active_exploration_combats
        SET {", ".join(assignments)}, updated_at = NOW()
        WHERE user_id = ${len(values)}
        RETURNING {ACTIVE_EXPLORATION_COMBAT_COLUMNS}
        """,
        *values,
    )
    return ActiveExplorationCombat.from_record(record)


async def delete_active_exploration_combat(connection: Connection, user_id: int) -> None:
    await connection.execute(
        """
        DELETE FROM active_exploration_combats
        WHERE user_id = $1
        """,
        user_id,
    )


def _clamp_probability(value: float, *, low: float, high: float) -> float:
    return max(low, min(high, value))


def _roll_initiative(combat: ActiveExplorationCombat) -> bool:
    player_roll = combat.player_speed + random.randint(0, 3)
    enemy_roll = combat.enemy_speed + random.randint(0, 3)
    return player_roll >= enemy_roll


def _roll_dodge(*, attacker_speed: int, defender_speed: int) -> bool:
    dodge_chance = _clamp_probability(
        0.04 + max(0, defender_speed - attacker_speed) * 0.02,
        low=0.0,
        high=0.22,
    )
    return random.random() < dodge_chance


def _calculate_player_damage(combat: ActiveExplorationCombat) -> int:
    # TODO: Replace this baseline-heavy placeholder once Zanpakuto, skills, and traits feed the full combat engine.
    return max(
        1,
        4 + combat.player_power - combat.enemy_defense + combat.focus_bonus + random.randint(-1, 3),
    )


def _calculate_enemy_damage(combat: ActiveExplorationCombat, *, guarded: bool) -> int:
    damage = max(
        1,
        4 + combat.enemy_power - combat.player_defense + random.randint(-1, 2),
    )
    if guarded:
        damage = max(1, damage // 2)
    return damage


def _build_victory_description(combat: ActiveExplorationCombat) -> str:
    if combat.resolution_description.strip():
        return combat.resolution_description
    return (
        f"The clash with **{combat.enemy_name}** finally breaks your way. "
        "You stay on your feet, catch your breath, and move before the rest of the block can close around you."
    )


def _build_setback_description(combat: ActiveExplorationCombat) -> str:
    setbacks = (
        f"**{combat.enemy_name}** drives you back before you can finish the job. You get out alive, but only because you know when the street has turned against you.",
        f"The fight turns ugly and you lose control of the pace. You stagger clear of **{combat.enemy_name}**, battered and breathing hard.",
        f"The exchange slips away from you. By the time you break off from **{combat.enemy_name}**, the opening is gone and the price is already written into your ribs.",
    )
    return random.choice(setbacks)


def _build_retreat_description(combat: ActiveExplorationCombat) -> str:
    return (
        f"You break away from **{combat.enemy_name}** before the alley can swallow the whole fight. "
        "It is not a clean win, but it beats being dragged down for scraps."
    )


def _resolve_outcome(
    combat: ActiveExplorationCombat,
    *,
    combat_outcome: Literal["Victory", "Setback", "Retreated"],
    round_summary: str,
) -> CombatOutcome:
    updated_combat = replace(combat, guard_active=False, last_round_summary=round_summary)

    if combat_outcome == "Victory":
        title = updated_combat.resolution_title
        description = _build_victory_description(updated_combat)
        xp_reward = updated_combat.reward_xp_win
    elif combat_outcome == "Retreated":
        title = f"You Break Away from {updated_combat.enemy_name}"
        description = _build_retreat_description(updated_combat)
        xp_reward = updated_combat.reward_xp_lose
    else:
        title = f"{updated_combat.enemy_name} Leaves You Reeling"
        description = _build_setback_description(updated_combat)
        xp_reward = updated_combat.reward_xp_lose

    return CombatOutcome(
        combat=updated_combat,
        title=title,
        description=description,
        xp_reward=xp_reward,
        combat_outcome=combat_outcome,
        reputation_change=updated_combat.reputation_change,
        player_hp_current=max(0, updated_combat.player_hp_current),
        player_mana_current=max(0, updated_combat.player_mana_current),
    )


def advance_combat_state(
    combat: ActiveExplorationCombat,
    action: CombatAction,
) -> CombatAdvanceResult:
    player_hp = combat.player_hp_current
    enemy_hp = combat.enemy_hp_current
    player_mana = combat.player_mana_current
    focus_bonus = combat.focus_bonus
    guard_active = False
    round_summary_parts: list[str] = []

    if action == "retreat":
        retreat_chance = _clamp_probability(
            0.35 + (combat.player_speed - combat.enemy_speed) * 0.05,
            low=0.15,
            high=0.75,
        )
        if random.random() < retreat_chance:
            round_summary_parts.append("You catch one narrow opening and slip the fight before it can lock down.")
            combat = replace(combat, last_round_summary=" ".join(round_summary_parts))
            return CombatAdvanceResult(
                status="resolved",
                outcome=_resolve_outcome(combat, combat_outcome="Retreated", round_summary=" ".join(round_summary_parts)),
            )

        round_summary_parts.append(f"You try to break away, but **{combat.enemy_name}** stays on you.")
        if _roll_dodge(attacker_speed=combat.enemy_speed, defender_speed=combat.player_speed):
            round_summary_parts.append("You still avoid the worst of the follow-up.")
        else:
            enemy_damage = _calculate_enemy_damage(combat, guarded=False)
            player_hp = max(0, player_hp - enemy_damage)
            round_summary_parts.append(f"It lands for **{enemy_damage}** damage before you can reset.")

        updated_round = combat.round_number + 1
        updated_combat = replace(
            combat,
            player_hp_current=player_hp,
            round_number=updated_round,
            last_round_summary=" ".join(round_summary_parts),
            guard_active=False,
        )
        if player_hp <= 0:
            return CombatAdvanceResult(
                status="resolved",
                outcome=_resolve_outcome(updated_combat, combat_outcome="Setback", round_summary=" ".join(round_summary_parts)),
            )
        return CombatAdvanceResult(status="updated", combat=updated_combat)

    if action == "guard":
        guard_active = True
        round_summary_parts.append("You tighten your stance and let the enemy crash into a guarded frame.")
    elif action == "focus":
        mana_gain = min(combat.player_mana_max - player_mana, 4 + max(1, combat.player_reiatsu // 5))
        player_mana += mana_gain
        focus_bonus = 3 + max(1, combat.player_reiatsu // 6)
        if mana_gain > 0:
            round_summary_parts.append(
                f"You gather your breathing and reiatsu, restoring **{mana_gain} mana** for the next exchange."
            )
        else:
            round_summary_parts.append("You draw your focus inward and line up a harder hit for the next opening.")

    player_acts_first = action != "attack" or _roll_initiative(combat)
    player_attack_consumed = False

    def _player_attack() -> None:
        nonlocal enemy_hp, focus_bonus, player_attack_consumed
        if _roll_dodge(attacker_speed=combat.player_speed, defender_speed=combat.enemy_speed):
            round_summary_parts.append(f"**{combat.enemy_name}** slips the angle and your hit glances wide.")
        else:
            player_damage = _calculate_player_damage(
                replace(combat, focus_bonus=focus_bonus)
            )
            enemy_hp = max(0, enemy_hp - player_damage)
            round_summary_parts.append(f"You strike for **{player_damage}** damage.")
        if focus_bonus > 0:
            player_attack_consumed = True
            focus_bonus = 0

    def _enemy_attack() -> None:
        nonlocal player_hp
        if _roll_dodge(attacker_speed=combat.enemy_speed, defender_speed=combat.player_speed):
            round_summary_parts.append("You slip the worst of the counter before it can settle clean.")
            return
        enemy_damage = _calculate_enemy_damage(combat, guarded=guard_active)
        player_hp = max(0, player_hp - enemy_damage)
        round_summary_parts.append(f"**{combat.enemy_name}** answers with **{enemy_damage}** damage.")

    if action == "attack" and player_acts_first:
        _player_attack()
        if enemy_hp <= 0:
            updated_combat = replace(
                combat,
                enemy_hp_current=enemy_hp,
                player_hp_current=player_hp,
                player_mana_current=player_mana,
                focus_bonus=focus_bonus,
                guard_active=False,
                last_round_summary=" ".join(round_summary_parts),
            )
            return CombatAdvanceResult(
                status="resolved",
                outcome=_resolve_outcome(updated_combat, combat_outcome="Victory", round_summary=" ".join(round_summary_parts)),
            )

    _enemy_attack()
    if player_hp <= 0:
        updated_combat = replace(
            combat,
            enemy_hp_current=enemy_hp,
            player_hp_current=player_hp,
            player_mana_current=player_mana,
            focus_bonus=focus_bonus,
            guard_active=False,
            last_round_summary=" ".join(round_summary_parts),
        )
        return CombatAdvanceResult(
            status="resolved",
            outcome=_resolve_outcome(updated_combat, combat_outcome="Setback", round_summary=" ".join(round_summary_parts)),
        )

    if action == "attack" and not player_acts_first:
        _player_attack()
        if enemy_hp <= 0:
            updated_combat = replace(
                combat,
                enemy_hp_current=enemy_hp,
                player_hp_current=player_hp,
                player_mana_current=player_mana,
                focus_bonus=focus_bonus,
                guard_active=False,
                last_round_summary=" ".join(round_summary_parts),
            )
            return CombatAdvanceResult(
                status="resolved",
                outcome=_resolve_outcome(updated_combat, combat_outcome="Victory", round_summary=" ".join(round_summary_parts)),
            )

    updated_round = combat.round_number + 1
    updated_combat = replace(
        combat,
        enemy_hp_current=enemy_hp,
        player_hp_current=player_hp,
        player_mana_current=player_mana,
        focus_bonus=focus_bonus,
        guard_active=False,
        round_number=updated_round,
        last_round_summary=" ".join(round_summary_parts),
    )

    return CombatAdvanceResult(status="updated", combat=updated_combat)
