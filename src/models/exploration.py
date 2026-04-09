from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class ActiveExploration:
    user_id: int
    channel_id: int
    location: str
    approach: str
    start_time: datetime
    end_time: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ActiveExploration":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            location=str(record["location"]),
            approach=str(record["approach"]),
            start_time=record["start_time"],
            end_time=record["end_time"],
        )
