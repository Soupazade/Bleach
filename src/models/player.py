from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from src.data.locations import LocationDefinition, get_location_definition
from src.data.traits import TraitDefinition, get_trait_definition
from src.services.formulas import calculate_spiritual_pressure


@dataclass(slots=True)
class PlayerProfile:
    user_id: int
    race: str
    rank: str
    level: int
    xp: int
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
    spiritual_pressure: int
    trait: str
    location: str
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
            spiritual_pressure=calculate_spiritual_pressure(
                power=power,
                defense=defense,
                speed=speed,
                reiatsu=reiatsu,
            ),
            trait=str(record["trait"]),
            location=str(record["location"]),
            created_at=record["created_at"],
        )

    @property
    def trait_data(self) -> TraitDefinition:
        return get_trait_definition(self.trait)

    @property
    def location_data(self) -> LocationDefinition:
        return get_location_definition(self.location)
