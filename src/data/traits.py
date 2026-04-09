from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True, slots=True)
class TraitBonuses:
    max_hp_pct: float = 0.0
    max_mana_pct: float = 0.0
    damage_power_pct: float = 0.0
    dodge_spd_pct: float = 0.0
    defense_pct: float = 0.0
    max_stamina_pct: float = 0.0
    flat_dodge_pct: float = 0.0
    stamina_regen_pct: float = 0.0
    event_reward_pct: float = 0.0
    defeat_penalty_reduction_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class TraitDefinition:
    key: str
    name: str
    effect: str
    bonuses: TraitBonuses


SOUL_TRAITS = {
    "resilient": TraitDefinition(
        key="resilient",
        name="Resilient",
        effect="+5% max HP",
        bonuses=TraitBonuses(max_hp_pct=0.05),
    ),
    "focused": TraitDefinition(
        key="focused",
        name="Focused",
        effect="+5% max Mana",
        bonuses=TraitBonuses(max_mana_pct=0.05),
    ),
    "fierce": TraitDefinition(
        key="fierce",
        name="Fierce",
        effect="+5% bonus Power for damage calculations only",
        bonuses=TraitBonuses(damage_power_pct=0.05),
    ),
    "fleet": TraitDefinition(
        key="fleet",
        name="Fleet",
        effect="+5% bonus Speed for dodge/speed calculations only",
        bonuses=TraitBonuses(dodge_spd_pct=0.05),
    ),
    "guarded": TraitDefinition(
        key="guarded",
        name="Guarded",
        effect="+5% bonus Defense for defense calculations only",
        bonuses=TraitBonuses(defense_pct=0.05),
    ),
    "calm_soul": TraitDefinition(
        key="calm_soul",
        name="Calm Soul",
        effect="+5% max Stamina",
        bonuses=TraitBonuses(max_stamina_pct=0.05),
    ),
    "sharp_instincts": TraitDefinition(
        key="sharp_instincts",
        name="Sharp Instincts",
        effect="+5% dodge chance in combat",
        bonuses=TraitBonuses(flat_dodge_pct=0.05),
    ),
    "steady_spirit": TraitDefinition(
        key="steady_spirit",
        name="Steady Spirit",
        effect="+5% stamina regeneration rate",
        bonuses=TraitBonuses(stamina_regen_pct=0.05),
    ),
    "observant": TraitDefinition(
        key="observant",
        name="Observant",
        effect="+5% better event reward chance",
        bonuses=TraitBonuses(event_reward_pct=0.05),
    ),
    "tenacious": TraitDefinition(
        key="tenacious",
        name="Tenacious",
        effect="Reduces defeat penalties by 10%",
        bonuses=TraitBonuses(defeat_penalty_reduction_pct=0.10),
    ),
}

SOUL_TRAIT_KEYS = tuple(SOUL_TRAITS)


def get_trait_definition(trait_key: str) -> TraitDefinition:
    try:
        return SOUL_TRAITS[trait_key]
    except KeyError as error:
        raise ValueError(f"Unknown trait key: {trait_key}") from error


def roll_random_soul_trait() -> TraitDefinition:
    return get_trait_definition(random.choice(SOUL_TRAIT_KEYS))
