from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True, slots=True)
class CombatEnemyTemplate:
    key: str
    name: str
    hp: int
    power: int
    defense: int
    speed: int
    reward_xp_win: int
    reward_xp_lose: int


RUKONGAI_STREETS_ENEMIES = (
    CombatEnemyTemplate(
        key="starving_ruffian",
        name="Starving Ruffian",
        hp=12,
        power=5,
        defense=1,
        speed=5,
        reward_xp_win=14,
        reward_xp_lose=5,
    ),
    CombatEnemyTemplate(
        key="knife_runner",
        name="Knife Runner",
        hp=11,
        power=6,
        defense=1,
        speed=7,
        reward_xp_win=15,
        reward_xp_lose=5,
    ),
    CombatEnemyTemplate(
        key="alley_tough",
        name="Alley Tough",
        hp=15,
        power=7,
        defense=2,
        speed=4,
        reward_xp_win=17,
        reward_xp_lose=6,
    ),
    CombatEnemyTemplate(
        key="weak_hollow",
        name="Weak Hollow",
        hp=14,
        power=7,
        defense=2,
        speed=6,
        reward_xp_win=18,
        reward_xp_lose=6,
    ),
)

LOCATION_ENEMY_POOLS = {
    "rukongai_streets": RUKONGAI_STREETS_ENEMIES,
}


def get_enemy_pool_for_location(location_key: str) -> tuple[CombatEnemyTemplate, ...]:
    return LOCATION_ENEMY_POOLS.get(location_key, RUKONGAI_STREETS_ENEMIES)


def get_enemy_for_exploration_combat(
    location_key: str,
    *,
    encounter_title: str,
    approach_risk: str,
) -> CombatEnemyTemplate:
    normalized_title = encounter_title.lower()
    enemy_pool = get_enemy_pool_for_location(location_key)

    if "hollow" in normalized_title:
        return next(enemy for enemy in enemy_pool if enemy.key == "weak_hollow")
    if "gang" in normalized_title or "collector" in normalized_title or "courier" in normalized_title:
        return next(enemy for enemy in enemy_pool if enemy.key == "alley_tough")
    if "alley" in normalized_title or "ambush" in normalized_title:
        return next(enemy for enemy in enemy_pool if enemy.key == "knife_runner")
    if approach_risk == "high":
        weighted_pool = tuple(enemy for enemy in enemy_pool if enemy.key != "starving_ruffian")
        return random.choice(weighted_pool)
    return random.choice(enemy_pool)
