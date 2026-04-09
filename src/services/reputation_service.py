from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.player import PlayerProfile


REPUTATION_MIN = -100
REPUTATION_MAX = 100

SMALL_POSITIVE_REPUTATION = 2
MAJOR_POSITIVE_REPUTATION = 5
SMALL_NEGATIVE_REPUTATION = -2
MAJOR_NEGATIVE_REPUTATION = -5

REPUTATION_TITLE_RANGES = (
    (-100, -81, "Hated"),
    (-80, -61, "Despised"),
    (-60, -41, "Distrusted"),
    (-40, -21, "Unwelcome"),
    (-20, 20, "Unknown"),
    (21, 40, "Accepted"),
    (41, 60, "Trusted"),
    (61, 80, "Respected"),
    (81, 100, "Admired"),
)

LOCATION_REPUTATION_FIELDS = {
    "rukongai_streets": ("rukongai_rep", "Rukongai Reputation"),
}

REPUTATION_MODIFIER_RANGES = (
    (
        -100,
        -81,
        {
            "title": "Hated",
            "xp_modifier": -8,
            "stamina_cost_modifier": 2,
            "shop_price_modifier": 8,
            "training_time_modifier": 8,
        },
    ),
    (
        -80,
        -61,
        {
            "title": "Despised",
            "xp_modifier": -6,
            "stamina_cost_modifier": 2,
            "shop_price_modifier": 6,
            "training_time_modifier": 6,
        },
    ),
    (
        -60,
        -41,
        {
            "title": "Distrusted",
            "xp_modifier": -4,
            "stamina_cost_modifier": 1,
            "shop_price_modifier": 4,
            "training_time_modifier": 4,
        },
    ),
    (
        -40,
        -21,
        {
            "title": "Unwelcome",
            "xp_modifier": -2,
            "stamina_cost_modifier": 1,
            "shop_price_modifier": 2,
            "training_time_modifier": 2,
        },
    ),
    (
        -20,
        20,
        {
            "title": "Unknown",
            "xp_modifier": 0,
            "stamina_cost_modifier": 0,
            "shop_price_modifier": 0,
            "training_time_modifier": 0,
        },
    ),
    (
        21,
        40,
        {
            "title": "Accepted",
            "xp_modifier": 2,
            "stamina_cost_modifier": 0,
            "shop_price_modifier": -2,
            "training_time_modifier": -2,
        },
    ),
    (
        41,
        60,
        {
            "title": "Trusted",
            "xp_modifier": 4,
            "stamina_cost_modifier": -1,
            "shop_price_modifier": -4,
            "training_time_modifier": -4,
        },
    ),
    (
        61,
        80,
        {
            "title": "Respected",
            "xp_modifier": 6,
            "stamina_cost_modifier": -1,
            "shop_price_modifier": -6,
            "training_time_modifier": -6,
        },
    ),
    (
        81,
        100,
        {
            "title": "Admired",
            "xp_modifier": 8,
            "stamina_cost_modifier": -2,
            "shop_price_modifier": -8,
            "training_time_modifier": -8,
        },
    ),
)


def clamp_reputation(region_rep: int) -> int:
    return max(REPUTATION_MIN, min(REPUTATION_MAX, int(region_rep)))


def get_reputation_title(region_rep: int) -> str:
    clamped_value = clamp_reputation(region_rep)
    for minimum, maximum, title in REPUTATION_TITLE_RANGES:
        if minimum <= clamped_value <= maximum:
            return title

    return "Unknown"


def apply_reputation_change(current_value: int, delta: int) -> int:
    return clamp_reputation(current_value + delta)


def get_reputation_modifiers(rep_value: int) -> dict[str, int | str]:
    clamped_value = clamp_reputation(rep_value)
    for minimum, maximum, modifier_data in REPUTATION_MODIFIER_RANGES:
        if minimum <= clamped_value <= maximum:
            return dict(modifier_data)

    return {
        "title": "Unknown",
        "xp_modifier": 0,
        "stamina_cost_modifier": 0,
        "shop_price_modifier": 0,
        "training_time_modifier": 0,
    }


def apply_rep_xp(base_xp: int, rep_value: int) -> int:
    modifiers = get_reputation_modifiers(rep_value)
    xp_modifier = int(modifiers["xp_modifier"])
    adjusted_xp = round(int(base_xp) * (1 + xp_modifier / 100))
    return max(0, int(adjusted_xp))


def apply_rep_stamina_cost(base_cost: int, rep_value: int) -> int:
    modifiers = get_reputation_modifiers(rep_value)
    stamina_modifier = int(modifiers["stamina_cost_modifier"])
    return max(1, int(base_cost) + stamina_modifier)


def apply_rep_training_duration(base_minutes: int, rep_value: int) -> int:
    modifiers = get_reputation_modifiers(rep_value)
    training_modifier = int(modifiers["training_time_modifier"])
    adjusted_minutes = round(int(base_minutes) * (1 + training_modifier / 100))
    return max(1, int(adjusted_minutes))


def apply_rep_shop_price(base_price: int, rep_value: int) -> int:
    modifiers = get_reputation_modifiers(rep_value)
    price_modifier = int(modifiers["shop_price_modifier"])
    adjusted_price = round(int(base_price) * (1 + price_modifier / 100))
    return max(1, int(adjusted_price))


def format_reputation_xp_text(modifier_pct: int, reputation_title: str) -> str | None:
    if modifier_pct == 0:
        return None

    descriptor = "bonus" if modifier_pct > 0 else "penalty"
    return f"({modifier_pct:+d}% reputation {descriptor} from {reputation_title})"


def format_reputation_stamina_text(stamina_cost: int, modifier: int, reputation_title: str) -> str:
    if modifier == 0:
        return f"**{stamina_cost}**"

    return f"**{stamina_cost}** ({modifier:+d} from {reputation_title} reputation)"


def get_location_reputation_label(location_key: str) -> str:
    _, label = LOCATION_REPUTATION_FIELDS.get(
        location_key,
        ("rukongai_rep", "Region Reputation"),
    )
    return label


def get_location_reputation_value(player: "PlayerProfile", location_key: str) -> int:
    field_name, _ = LOCATION_REPUTATION_FIELDS.get(
        location_key,
        ("rukongai_rep", "Region Reputation"),
    )
    return clamp_reputation(getattr(player, field_name, 0))


def get_location_reputation_title(player: "PlayerProfile", location_key: str) -> str:
    return get_reputation_title(get_location_reputation_value(player, location_key))
