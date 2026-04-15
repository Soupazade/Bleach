from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


def _deserialize_progress(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


@dataclass(slots=True)
class DungeonLootEntry:
    item_key: str
    item_name: str
    quantity: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_key": self.item_key,
            "item_name": self.item_name,
            "quantity": self.quantity,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DungeonLootEntry":
        return cls(
            item_key=str(payload["item_key"]),
            item_name=str(payload["item_name"]),
            quantity=int(payload["quantity"]),
        )


@dataclass(slots=True)
class DungeonProgressState:
    total_xp: int = 0
    total_kan: int = 0
    total_reputation: int = 0
    history: tuple[str, ...] = ()
    items: tuple[DungeonLootEntry, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_xp": self.total_xp,
            "total_kan": self.total_kan,
            "total_reputation": self.total_reputation,
            "history": list(self.history),
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "DungeonProgressState":
        if payload is None:
            return cls()
        return cls(
            total_xp=int(payload.get("total_xp", 0)),
            total_kan=int(payload.get("total_kan", 0)),
            total_reputation=int(payload.get("total_reputation", 0)),
            history=tuple(str(entry) for entry in payload.get("history", [])),
            items=tuple(
                DungeonLootEntry.from_dict(item_payload)
                for item_payload in payload.get("items", [])
            ),
        )


@dataclass(slots=True)
class ActiveDungeonRun:
    user_id: int
    channel_id: int
    message_id: int | None
    dungeon_key: str
    location: str
    current_room_index: int
    progress: DungeonProgressState
    created_at: Any
    updated_at: Any

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ActiveDungeonRun":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            message_id=int(record["message_id"]) if record["message_id"] is not None else None,
            dungeon_key=str(record["dungeon_key"]),
            location=str(record["location"]),
            current_room_index=int(record["current_room_index"]),
            progress=DungeonProgressState.from_dict(
                _deserialize_progress(record.get("progress_state", {}))
            ),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
