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
