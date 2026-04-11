from __future__ import annotations

from dataclasses import dataclass


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
    attack_bias: int = 90
    guard_bias: int = 10


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
    attack_bias=90,
    guard_bias=10,
)


def get_enemy_for_exploration_combat(
    location_key: str,
    *,
    encounter_title: str,
    approach_risk: str,
) -> CombatEnemyTemplate:
    return GENERIC_LEVEL_ONE_BANDIT
