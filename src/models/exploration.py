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


@dataclass(slots=True)
class PendingExplorationChoice:
    user_id: int
    channel_id: int
    message_id: int | None
    location: str
    approach: str
    start_time: datetime
    end_time: datetime
    event_key: str
    event_flow: str
    current_step: str
    choice_history: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PendingExplorationChoice":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            message_id=int(record["message_id"]) if record["message_id"] is not None else None,
            location=str(record["location"]),
            approach=str(record["approach"]),
            start_time=record["start_time"],
            end_time=record["end_time"],
            event_key=str(record["event_key"]),
            event_flow=str(record["event_flow"]),
            current_step=str(record["current_step"]),
            choice_history=tuple(record["choice_history"] or ()),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def to_active_exploration(self) -> ActiveExploration:
        return ActiveExploration(
            user_id=self.user_id,
            channel_id=self.channel_id,
            location=self.location,
            approach=self.approach,
            start_time=self.start_time,
            end_time=self.end_time,
        )
