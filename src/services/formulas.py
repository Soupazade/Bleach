from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.data.traits import TraitDefinition

RUKONGAI_EARLY_GAME_LEVEL_CAP = 10
RUKONGAI_XP_PER_LEVEL = 15
RUKONGAI_STAT_CAP_PER_LEVEL = 5


def calculate_spiritual_pressure(
    power: int,
    defense: int,
    speed: int,
    reiatsu: int,
) -> int:
    return power + defense + speed + reiatsu


def apply_percent_bonus(base_value: int, percent_bonus: float) -> int:
    return int(round(base_value * (1 + percent_bonus)))


def calculate_effective_hp_max(base_hp_max: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_hp_max, trait.bonuses.max_hp_pct)


def calculate_effective_stamina_max(base_stamina_max: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_stamina_max, trait.bonuses.max_stamina_pct)


def calculate_effective_mana_max(base_mana_max: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_mana_max, trait.bonuses.max_mana_pct)


def calculate_effective_damage_power(base_power: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_power, trait.bonuses.damage_power_pct)


def calculate_effective_defense(base_defense: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_defense, trait.bonuses.defense_pct)


def calculate_effective_speed(base_speed: int, trait: TraitDefinition) -> int:
    return apply_percent_bonus(base_speed, trait.bonuses.dodge_spd_pct)


def calculate_minutes_elapsed(start_time: datetime, end_time: datetime) -> int:
    start_utc = start_time.astimezone(timezone.utc)
    end_utc = end_time.astimezone(timezone.utc)
    return max(0, int((end_utc - start_utc).total_seconds() // 60))


def calculate_rest_stamina_recovery(minutes_resting: int) -> int:
    return max(0, minutes_resting) * 5


def calculate_passive_stamina_recovery(
    current_stamina: int,
    stamina_max: int,
    elapsed_minutes: int,
) -> int:
    stamina = current_stamina

    for _ in range(max(0, elapsed_minutes)):
        if stamina >= stamina_max:
            break

        regen_amount = 3 if stamina < 50 else 2
        stamina = min(stamina_max, stamina + regen_amount)

    return stamina - current_stamina


def get_xp_required_for_level(level: int) -> int:
    # Rukongai is tuned as the early-game zone for roughly levels 1-10, so the
    # opening curve stays intentionally quick and rewarding before later regions scale up.
    return max(1, level) * RUKONGAI_XP_PER_LEVEL


def get_stat_cap_for_level(level: int) -> int:
    # Early-game stat growth stays intentionally readable in Rukongai. This cap is
    # surfaced in the UI now, and later regions/forms can swap in their own scaling cleanly.
    return max(1, level) * RUKONGAI_STAT_CAP_PER_LEVEL


def apply_experience_gain(
    current_level: int,
    current_xp: int,
    xp_gain: int,
) -> tuple[int, int, int]:
    level = current_level
    xp = current_xp + xp_gain
    levels_gained = 0

    while xp >= get_xp_required_for_level(level):
        xp -= get_xp_required_for_level(level)
        level += 1
        levels_gained += 1

    return level, xp, levels_gained


def format_remaining_duration(end_time: datetime, now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)

    remaining = max(timedelta(0), end_time.astimezone(timezone.utc) - now.astimezone(timezone.utc))
    total_seconds = int(remaining.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)

    if minutes > 0:
        return f"{minutes}m {seconds:02d}s"

    return f"{seconds}s"
