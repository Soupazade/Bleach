from __future__ import annotations

from src.data.traits import TraitDefinition


def calculate_spiritual_pressure(
    strength: int,
    defense: int,
    speed: int,
    intelligence: int,
) -> int:
    return strength + defense + speed + intelligence


def apply_percent_bonus(base_value: int, percent_bonus: float) -> int:
    return int(round(base_value * (1 + percent_bonus)))


def calculate_effective_hp_max(base_hp_max: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_hp_max, trait.bonuses.max_hp_pct)


def calculate_effective_stamina_max(base_stamina_max: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_stamina_max, trait.bonuses.max_stamina_pct)


def calculate_effective_mana_max(base_mana_max: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_mana_max, trait.bonuses.max_mana_pct)


def calculate_effective_damage_strength(base_strength: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_strength, trait.bonuses.damage_str_pct)


def calculate_effective_defense(base_defense: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_defense, trait.bonuses.defense_pct)


def calculate_effective_speed(base_speed: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_speed, trait.bonuses.dodge_spd_pct)
