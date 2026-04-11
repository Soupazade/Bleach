from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from src.data.locations import LocationDefinition, get_location_definition
from src.data.traits import TraitDefinition, get_trait_definition
from src.services.formulas import calculate_spiritual_pressure
from src.services.reputation_service import clamp_reputation, get_reputation_title


@dataclass(slots=True)
class PlayerProfile:
    user_id: int
    race: str
    rank: str
    level: int
    xp: int
    kan: int
    hp_current: int
    hp_max: int
    stamina_current: int
    stamina_max: int
    mana_current: int
    mana_max: int
    power: int
    defense: int
    speed: int
    reiatsu: int
    unspent_stat_points: int
    spiritual_pressure: int
    trait: str
    location: str
    rukongai_rep: int
    has_minor_setback: bool
    setback_source: str | None
    setback_at: datetime | None
    is_resting: bool
    rest_start_time: datetime | None
    rest_stamina_snapshot: int | None
    rest_hp_snapshot: int | None
    rest_mana_snapshot: int | None
    stamina_updated_at: datetime
    created_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PlayerProfile":
        power = int(record["power"])
        defense = int(record["defense"])
        speed = int(record["speed"])
        reiatsu = int(record["reiatsu"])

        return cls(
            user_id=int(record["user_id"]),
            race=str(record["race"]),
            rank=str(record["rank"]),
            level=int(record["level"]),
            xp=int(record["xp"]),
            kan=int(record["kan"]),
            hp_current=int(record["hp_current"]),
            hp_max=int(record["hp_max"]),
            stamina_current=int(record["stamina_current"]),
            stamina_max=int(record["stamina_max"]),
            mana_current=int(record["mana_current"]),
            mana_max=int(record["mana_max"]),
            power=power,
            defense=defense,
            speed=speed,
            reiatsu=reiatsu,
            unspent_stat_points=int(record["unspent_stat_points"]),
            spiritual_pressure=calculate_spiritual_pressure(
                power=power,
                defense=defense,
                speed=speed,
                reiatsu=reiatsu,
            ),
            trait=str(record["trait"]),
            location=str(record["location"]),
            rukongai_rep=clamp_reputation(int(record["rukongai_rep"])),
            has_minor_setback=bool(record["has_minor_setback"]),
            setback_source=str(record["setback_source"]) if record["setback_source"] is not None else None,
            setback_at=record["setback_at"],
            is_resting=bool(record["is_resting"]),
            rest_start_time=record["rest_start_time"],
            rest_stamina_snapshot=record["rest_stamina_snapshot"],
            rest_hp_snapshot=record["rest_hp_snapshot"],
            rest_mana_snapshot=record["rest_mana_snapshot"],
            stamina_updated_at=record["stamina_updated_at"],
            created_at=record["created_at"],
        )

    @property
    def trait_data(self) -> TraitDefinition:
        return get_trait_definition(self.trait)

    @property
    def location_data(self) -> LocationDefinition:
        return get_location_definition(self.location)

    @property
    def rukongai_reputation_title(self) -> str:
        return get_reputation_title(self.rukongai_rep)
