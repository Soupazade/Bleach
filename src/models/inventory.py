from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
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
        raw_metadata = record["metadata"]
        if raw_metadata is None:
            metadata: dict[str, Any] = {}
        elif isinstance(raw_metadata, Mapping):
            metadata = dict(raw_metadata)
        elif isinstance(raw_metadata, str):
            try:
                decoded = json.loads(raw_metadata)
            except json.JSONDecodeError:
                decoded = {}
            metadata = dict(decoded) if isinstance(decoded, Mapping) else {}
        else:
            metadata = {}
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
            metadata=metadata,
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
