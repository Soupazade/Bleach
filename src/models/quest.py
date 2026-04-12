from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping


QuestCategory = Literal["main", "side", "daily", "repeatable"]
QuestStatus = Literal["active", "completed"]
QuestActionType = Literal["explore_completed", "craft_item", "travel_completed", "training_started"]


@dataclass(frozen=True, slots=True)
class QuestRewardItemDefinition:
    item_key: str
    quantity: int


@dataclass(frozen=True, slots=True)
class QuestRewardDefinition:
    xp: int
    kan: int = 0
    reputation: int = 0
    stat_points: int = 0
    items: tuple[QuestRewardItemDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestStepRequirement:
    action_type: QuestActionType
    accepted_item_keys: tuple[str, ...] = ()
    required_location: str | None = None


@dataclass(frozen=True, slots=True)
class QuestStepDefinition:
    title: str
    narrative_prompt: str
    system_explanation: tuple[str, ...]
    objective: str
    requirement: QuestStepRequirement


@dataclass(frozen=True, slots=True)
class QuestDefinition:
    key: str
    category: QuestCategory
    title: str
    short_description: str
    guide_name: str
    difficulty: str = "Unknown"
    lore_summary: str = ""
    briefing_objective: str = ""
    min_level: int = 1
    auto_start: bool = False
    steps: tuple[QuestStepDefinition, ...] = ()
    reward: QuestRewardDefinition = QuestRewardDefinition(xp=0)
    completion_text: str = ""


@dataclass(slots=True)
class PlayerQuestRecord:
    user_id: int
    quest_key: str
    status: QuestStatus
    current_step_index: int
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PlayerQuestRecord":
        return cls(
            user_id=int(record["user_id"]),
            quest_key=str(record["quest_key"]),
            status=str(record["status"]),
            current_step_index=int(record["current_step_index"]),
            started_at=record["started_at"],
            completed_at=record["completed_at"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )


@dataclass(slots=True)
class QuestRewardItemGrant:
    item_key: str
    item_name: str
    quantity: int


@dataclass(slots=True)
class QuestProgressUpdate:
    quest: QuestDefinition
    status: Literal["advanced", "completed"]
    previous_step_index: int
    current_step_index: int
    xp_gained: int = 0
    kan_gained: int = 0
    reputation_gained: int = 0
    stat_points_gained: int = 0
    levels_gained: int = 0
    granted_items: tuple[QuestRewardItemGrant, ...] = ()
