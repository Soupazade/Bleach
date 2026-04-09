from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from src.models.exploration import ActiveExploration


@dataclass(slots=True)
class ActiveExplorationCombat:
    user_id: int
    channel_id: int
    message_id: int | None
    location: str
    approach: str
    encounter_title: str
    encounter_description: str
    resolution_title: str
    resolution_description: str
    enemy_name: str
    enemy_hp_current: int
    enemy_hp_max: int
    enemy_power: int
    enemy_defense: int
    enemy_speed: int
    reward_xp_win: int
    reward_xp_lose: int
    reputation_change: int
    player_hp_current: int
    player_hp_max: int
    player_mana_current: int
    player_mana_max: int
    player_power: int
    player_defense: int
    player_speed: int
    player_reiatsu: int
    round_number: int
    focus_bonus: int
    guard_active: bool
    last_round_summary: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ActiveExplorationCombat":
        return cls(
            user_id=int(record["user_id"]),
            channel_id=int(record["channel_id"]),
            message_id=int(record["message_id"]) if record["message_id"] is not None else None,
            location=str(record["location"]),
            approach=str(record["approach"]),
            encounter_title=str(record["encounter_title"]),
            encounter_description=str(record["encounter_description"]),
            resolution_title=str(record["resolution_title"]),
            resolution_description=str(record["resolution_description"]),
            enemy_name=str(record["enemy_name"]),
            enemy_hp_current=int(record["enemy_hp_current"]),
            enemy_hp_max=int(record["enemy_hp_max"]),
            enemy_power=int(record["enemy_power"]),
            enemy_defense=int(record["enemy_defense"]),
            enemy_speed=int(record["enemy_speed"]),
            reward_xp_win=int(record["reward_xp_win"]),
            reward_xp_lose=int(record["reward_xp_lose"]),
            reputation_change=int(record["reputation_change"]),
            player_hp_current=int(record["player_hp_current"]),
            player_hp_max=int(record["player_hp_max"]),
            player_mana_current=int(record["player_mana_current"]),
            player_mana_max=int(record["player_mana_max"]),
            player_power=int(record["player_power"]),
            player_defense=int(record["player_defense"]),
            player_speed=int(record["player_speed"]),
            player_reiatsu=int(record["player_reiatsu"]),
            round_number=int(record["round_number"]),
            focus_bonus=int(record["focus_bonus"]),
            guard_active=bool(record["guard_active"]),
            last_round_summary=str(record["last_round_summary"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def to_active_exploration(self) -> ActiveExploration:
        return ActiveExploration(
            user_id=self.user_id,
            channel_id=self.channel_id,
            location=self.location,
            approach=self.approach,
            start_time=self.created_at,
            end_time=self.updated_at,
        )
