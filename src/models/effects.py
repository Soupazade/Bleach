from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping


PlayerEffectType = Literal[
    "stamina_flat",
    "stamina_regen_pct",
    "xp_boost_pct",
    "power_pct",
    "defense_pct",
    "speed_pct",
    "reiatsu_pct",
    "hp_pct",
    "mana_pct",
    "shop_discount_pct",
    "travel_time_flat",
    "combat_focus_flat",
    "special_trigger_pct",
]


@dataclass(slots=True)
class PlayerEffect:
    id: int
    user_id: int
    effect_key: str
    title: str
    description: str
    effect_type: PlayerEffectType
    magnitude: int
    duration_minutes: int | None
    expires_at: datetime | None
    remaining_explores: int | None
    source_text: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PlayerEffect":
        return cls(
            id=int(record["id"]),
            user_id=int(record["user_id"]),
            effect_key=str(record["effect_key"]),
            title=str(record["title"]),
            description=str(record["description"]),
            effect_type=str(record["effect_type"]),  # type: ignore[assignment]
            magnitude=int(record["magnitude"]),
            duration_minutes=(
                int(record["duration_minutes"])
                if record["duration_minutes"] is not None
                else None
            ),
            expires_at=record["expires_at"],
            remaining_explores=(
                int(record["remaining_explores"])
                if record["remaining_explores"] is not None
                else None
            ),
            source_text=str(record["source_text"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    @property
    def is_positive(self) -> bool:
        return self.magnitude > 0
