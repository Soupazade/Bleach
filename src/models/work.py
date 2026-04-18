from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class ActiveWork:
    user_id: int
    channel_id: int
    location: str
    work_key: str
    start_time: datetime
    end_time: datetime
    stamina_cost: int

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ActiveWork":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            location=str(record["location"]),
            work_key=str(record["work_key"]),
            start_time=record["start_time"],
            end_time=record["end_time"],
            stamina_cost=int(record["stamina_cost"]),
        )
