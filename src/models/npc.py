from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class PlayerNpcProgress:
    user_id: int
    npc_id: str
    state: str
    stage: int
    last_encounter_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PlayerNpcProgress":
        return cls(
            user_id=int(record["user_id"]),
            npc_id=str(record["npc_id"]),
            state=str(record["state"]),
            stage=int(record["stage"]),
            last_encounter_at=record["last_encounter_at"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
