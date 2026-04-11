from __future__ import annotations

from src.services.combat.types import CombatAbility


HEAVY_STRIKE = CombatAbility(
    key="heavy_strike",
    name="Heavy Strike",
    mana_cost=50,
    cooldown_turns=3,
    unlock_level=2,
    power_multiplier=2.0,
    hit_chance=80.0,
)

MULTI_STRIKE = CombatAbility(
    key="multi_strike",
    name="Multi Strike",
    mana_cost=50,
    cooldown_turns=3,
    unlock_level=5,
    power_multiplier=1.0,
    hit_chance=80.0,
    hits=3,
)

CLEAVING_SLASH = CombatAbility(
    key="cleaving_slash",
    name="Cleaving Slash",
    mana_cost=50,
    cooldown_turns=3,
    unlock_level=7,
    power_multiplier=2.0,
    hit_chance=80.0,
    targeting="all",
)


PLAYER_ABILITIES = (
    HEAVY_STRIKE,
    MULTI_STRIKE,
    CLEAVING_SLASH,
)

ABILITY_MAP = {ability.key: ability for ability in PLAYER_ABILITIES}


def get_combat_ability(ability_key: str) -> CombatAbility:
    return ABILITY_MAP[ability_key]


def list_unlocked_player_abilities(level: int) -> tuple[CombatAbility, ...]:
    return tuple(ability for ability in PLAYER_ABILITIES if level >= ability.unlock_level)
