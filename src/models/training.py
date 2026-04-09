from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class ActiveTraining:
    user_id: int
    channel_id: int
    stat_target: str
    duration_minutes: int
    start_time: datetime
    end_time: datetime
    stamina_cost: int

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ActiveTraining":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            stat_target=str(record["stat_target"]),
            duration_minutes=int(record["duration_minutes"]),
            start_time=record["start_time"],
            end_time=record["end_time"],
            stamina_cost=int(record["stamina_cost"]),
        )
