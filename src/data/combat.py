from __future__ import annotations

from dataclasses import dataclass, replace
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
    name_pool: tuple[str, ...] = ()


GENERIC_LEVEL_ONE_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l1",
    name="Rukongai Drifter",
    level=1,
    race="Soul",
    rank="Street Thug",
    hp=85,
    mana=35,
    power=1,
    defense=1,
    speed=1,
    reiatsu=1,
    reward_xp_win=10,
    reward_xp_lose=4,
    abilities=(),
    attack_bias=90,
    guard_bias=10,
    name_pool=("Suzu", "Toma", "Kenta", "Nobu", "Shin", "Mako"),
)

GENERIC_LEVEL_THREE_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l3",
    name="Rukongai Scrapper",
    level=3,
    race="Soul",
    rank="Scrapper",
    hp=120,
    mana=65,
    power=4,
    defense=3,
    speed=3,
    reiatsu=3,
    reward_xp_win=18,
    reward_xp_lose=6,
    abilities=("heavy_strike",),
    attack_bias=78,
    guard_bias=10,
    ability_bias=12,
    name_pool=("Daigo", "Rikka", "Hayate", "Isamu", "Kuro", "Seina"),
)

GENERIC_LEVEL_FIVE_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l5",
    name="Rukongai Cutthroat",
    level=5,
    race="Soul",
    rank="Cutthroat",
    hp=155,
    mana=95,
    power=7,
    defense=5,
    speed=5,
    reiatsu=5,
    reward_xp_win=28,
    reward_xp_lose=9,
    abilities=("heavy_strike", "multi_strike"),
    attack_bias=70,
    guard_bias=10,
    ability_bias=20,
    name_pool=("Tetsu", "Arata", "Ginji", "Kazane", "Rinzo", "Sabi"),
)

GENERIC_LEVEL_SEVEN_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l7",
    name="Rukongai Enforcer",
    level=7,
    race="Soul",
    rank="Enforcer",
    hp=205,
    mana=125,
    power=10,
    defense=7,
    speed=7,
    reiatsu=7,
    reward_xp_win=40,
    reward_xp_lose=13,
    abilities=("heavy_strike", "multi_strike", "cleaving_slash"),
    attack_bias=62,
    guard_bias=10,
    ability_bias=28,
    name_pool=("Kogarashi", "Raika", "Shigure", "Tobio", "Jinbei", "Akane"),
)

GENERIC_LEVEL_TEN_BANDIT = CombatEnemyTemplate(
    key="generic_bandit_l10",
    name="Rukongai Bandit Captain",
    level=10,
    race="Soul",
    rank="Bandit Captain",
    hp=260,
    mana=160,
    power=14,
    defense=10,
    speed=10,
    reiatsu=10,
    reward_xp_win=58,
    reward_xp_lose=18,
    abilities=("heavy_strike", "multi_strike", "cleaving_slash"),
    attack_bias=55,
    guard_bias=10,
    ability_bias=35,
    name_pool=("Kurohane", "Raizen", "Sanjuro", "Goryu", "Mizuchi", "Kagemaru"),
)


ENEMY_TIERS: tuple[CombatEnemyTemplate, ...] = (
    GENERIC_LEVEL_ONE_BANDIT,
    GENERIC_LEVEL_THREE_BANDIT,
    GENERIC_LEVEL_FIVE_BANDIT,
    GENERIC_LEVEL_SEVEN_BANDIT,
    GENERIC_LEVEL_TEN_BANDIT,
)


def _with_random_name(template: CombatEnemyTemplate) -> CombatEnemyTemplate:
    if not template.name_pool:
        return template
    return replace(template, name=random.choice(template.name_pool))


def get_enemy_for_exploration_combat(
    location_key: str,
    *,
    encounter_title: str,
    approach_risk: str,
    player_level: int = 1,
) -> CombatEnemyTemplate:
    del location_key, encounter_title, approach_risk
    eligible = [enemy for enemy in ENEMY_TIERS if enemy.level <= max(1, player_level)]
    chosen = random.choice(eligible or [GENERIC_LEVEL_ONE_BANDIT])
    return _with_random_name(chosen)
