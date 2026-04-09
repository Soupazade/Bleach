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
    session_kind: str
    npc_id: str | None
    location: str
    approach: str
    start_time: datetime
    end_time: datetime
    event_key: str
    special_event_key: str | None
    event_flow: str
    current_step: str
    choice_history: tuple[str, ...]
    base_event_type: str | None
    base_title: str | None
    base_description: str | None
    base_xp: int | None
    base_rep_change: int | None
    base_combat_outcome: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PendingExplorationChoice":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            message_id=int(record["message_id"]) if record["message_id"] is not None else None,
            session_kind=str(record["session_kind"]),
            npc_id=str(record["npc_id"]) if record["npc_id"] is not None else None,
            location=str(record["location"]),
            approach=str(record["approach"]),
            start_time=record["start_time"],
            end_time=record["end_time"],
            event_key=str(record["event_key"]),
            special_event_key=str(record["special_event_key"]) if record["special_event_key"] is not None else None,
            event_flow=str(record["event_flow"]),
            current_step=str(record["current_step"]),
            choice_history=tuple(record["choice_history"] or ()),
            base_event_type=str(record["base_event_type"]) if record["base_event_type"] is not None else None,
            base_title=str(record["base_title"]) if record["base_title"] is not None else None,
            base_description=str(record["base_description"]) if record["base_description"] is not None else None,
            base_xp=int(record["base_xp"]) if record["base_xp"] is not None else None,
            base_rep_change=int(record["base_rep_change"]) if record["base_rep_change"] is not None else None,
            base_combat_outcome=(
                str(record["base_combat_outcome"])
                if record["base_combat_outcome"] is not None
                else None
            ),
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
