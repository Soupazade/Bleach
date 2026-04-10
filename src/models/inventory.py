from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class PlayerInventoryItem:
    id: int
    user_id: int
    item_key: str
    item_name: str
    item_description: str
    item_type: str
    rarity: str
    quantity: int
    stackable: bool
    source_text: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PlayerInventoryItem":
        metadata = record["metadata"] if record["metadata"] is not None else {}
        return cls(
            id=int(record["id"]),
            user_id=int(record["user_id"]),
            item_key=str(record["item_key"]),
            item_name=str(record["item_name"]),
            item_description=str(record["item_description"]),
            item_type=str(record["item_type"]),
            rarity=str(record["rarity"]),
            quantity=int(record["quantity"]),
            stackable=bool(record["stackable"]),
            source_text=str(record["source_text"]),
            metadata=dict(metadata),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
