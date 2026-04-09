from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class ActiveTravel:
    user_id: int
    channel_id: int
    source_location: str
    destination_location: str
    start_time: datetime
    end_time: datetime
    stamina_cost: int

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ActiveTravel":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            source_location=str(record["source_location"]),
            destination_location=str(record["destination_location"]),
            start_time=record["start_time"],
            end_time=record["end_time"],
            stamina_cost=int(record["stamina_cost"]),
        )
