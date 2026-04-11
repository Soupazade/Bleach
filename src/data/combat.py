from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True, slots=True)
class CombatEnemyTemplate:
    key: str
    name: str
    level: int
    race: str
    rank: str
    hp: int
    mana: int
    power: int
    defense: int
    speed: int
    reiatsu: int
    reward_xp_win: int
    reward_xp_lose: int
    abilities: tuple[str, ...] = ()
    attack_bias: int = 90
    guard_bias: int = 10
    ability_bias: int = 0


GENERIC_LEVEL_ONE_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l1",
    name="Generic Level 1 Bandit",
    level=1,
    race="Soul",
    rank="Street Thug",
    hp=150,
    mana=50,
    power=5,
    defense=5,
    speed=5,
    reiatsu=5,
    reward_xp_win=15,
    reward_xp_lose=5,
    abilities=(),
    attack_bias=90,
    guard_bias=10,
)

GENERIC_LEVEL_THREE_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l3",
    name="Generic Level 3 Bandit",
    level=3,
    race="Soul",
    rank="Scrapper",
    hp=155,
    mana=65,
    power=8,
    defense=7,
    speed=7,
    reiatsu=7,
    reward_xp_win=22,
    reward_xp_lose=7,
    abilities=("heavy_strike",),
    attack_bias=80,
    guard_bias=10,
    ability_bias=10,
)

GENERIC_LEVEL_FIVE_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l5",
    name="Generic Level 5 Bandit",
    level=5,
    race="Soul",
    rank="Cutthroat",
    hp=185,
    mana=95,
    power=11,
    defense=10,
    speed=10,
    reiatsu=10,
    reward_xp_win=32,
    reward_xp_lose=10,
    abilities=("heavy_strike", "multi_strike"),
    attack_bias=72,
    guard_bias=10,
    ability_bias=18,
)

GENERIC_LEVEL_SEVEN_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l7",
    name="Generic Level 7 Bandit",
    level=7,
    race="Soul",
    rank="Enforcer",
    hp=225,
    mana=125,
    power=15,
    defense=13,
    speed=13,
    reiatsu=13,
    reward_xp_win=44,
    reward_xp_lose=14,
    abilities=("heavy_strike", "multi_strike", "cleaving_slash"),
    attack_bias=65,
    guard_bias=10,
    ability_bias=25,
)

GENERIC_LEVEL_TEN_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l10",
    name="Generic Level 10 Bandit",
    level=10,
    race="Soul",
    rank="Bandit Captain",
    hp=280,
    mana=160,
    power=20,
    defense=17,
    speed=17,
    reiatsu=17,
    reward_xp_win=60,
    reward_xp_lose=18,
    abilities=("heavy_strike", "multi_strike", "cleaving_slash"),
    attack_bias=58,
    guard_bias=10,
    ability_bias=32,
)


ENEMY_TIERS: tuple[CombatEnemyTemplate, ...] = (
    GENERIC_LEVEL_ONE_BANDIT,
    GENERIC_LEVEL_THREE_BANDIT,
    GENERIC_LEVEL_FIVE_BANDIT,
    GENERIC_LEVEL_SEVEN_BANDIT,
    GENERIC_LEVEL_TEN_BANDIT,
)


def get_enemy_for_exploration_combat(
    location_key: str,
    *,
    encounter_title: str,
    approach_risk: str,
    player_level: int = 1,
) -> CombatEnemyTemplate:
    del location_key, encounter_title, approach_risk
    eligible = [enemy for enemy in ENEMY_TIERS if enemy.level <= max(1, player_level)]
    return random.choice(eligible or [GENERIC_LEVEL_ONE_BANDIT])
