from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from src.models.exploration import ActiveExploration


CombatAction = Literal["strike", "guard", "retreat", "ability", "bandage"]
CombatSourceKind = Literal["exploration", "fighttest"]
CombatResolutionType = Literal["victory", "defeat", "retreated"]
AbilityTargeting = Literal["single", "all"]


@dataclass(slots=True)
class CombatAbility:
    key: str
    name: str
    mana_cost: int
    cooldown_turns: int
    unlock_level: int
    power_multiplier: float
    hit_chance: float
    hits: int = 1
    targeting: AbilityTargeting = "single"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "mana_cost": self.mana_cost,
            "cooldown_turns": self.cooldown_turns,
            "unlock_level": self.unlock_level,
            "power_multiplier": self.power_multiplier,
            "hit_chance": self.hit_chance,
            "hits": self.hits,
            "targeting": self.targeting,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CombatAbility":
        return cls(
            key=str(payload["key"]),
            name=str(payload["name"]),
            mana_cost=int(payload["mana_cost"]),
            cooldown_turns=int(payload["cooldown_turns"]),
            unlock_level=int(payload["unlock_level"]),
            power_multiplier=float(payload["power_multiplier"]),
            hit_chance=float(payload["hit_chance"]),
            hits=int(payload.get("hits", 1)),
            targeting=payload.get("targeting", "single"),
        )


@dataclass(slots=True)
class CombatEntity:
    entity_id: str
    name: str
    level: int
    race: str
    rank: str
    hp_current: int
    hp_max: int
    mana_current: int
    mana_max: int
    power: int
    defense: int
    speed: int
    reiatsu: int
    abilities: tuple[str, ...] = ()
    cooldowns: dict[str, int] = field(default_factory=dict)
    attack_bias: int = 100
    guard_bias: int = 0
    ability_bias: int = 0

    @property
    def is_alive(self) -> bool:
        return self.hp_current > 0

    @property
    def dodge_chance_pct(self) -> float:
        return max(0.0, self.speed * 0.1)

    @property
    def damage_reduction_pct(self) -> float:
        return max(0.0, self.defense * 0.1)

    @property
    def mana_regen_pct(self) -> float:
        return 5.0 + (self.reiatsu * 0.025)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "level": self.level,
            "race": self.race,
            "rank": self.rank,
            "hp_current": self.hp_current,
            "hp_max": self.hp_max,
            "mana_current": self.mana_current,
            "mana_max": self.mana_max,
            "power": self.power,
            "defense": self.defense,
            "speed": self.speed,
            "reiatsu": self.reiatsu,
            "abilities": list(self.abilities),
            "cooldowns": self.cooldowns,
            "attack_bias": self.attack_bias,
            "guard_bias": self.guard_bias,
            "ability_bias": self.ability_bias,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CombatEntity":
        return cls(
            entity_id=str(payload["entity_id"]),
            name=str(payload["name"]),
            level=int(payload["level"]),
            race=str(payload.get("race", "Unknown")),
            rank=str(payload.get("rank", "Unknown")),
            hp_current=int(payload["hp_current"]),
            hp_max=int(payload["hp_max"]),
            mana_current=int(payload["mana_current"]),
            mana_max=int(payload["mana_max"]),
            power=int(payload["power"]),
            defense=int(payload["defense"]),
            speed=int(payload["speed"]),
            reiatsu=int(payload["reiatsu"]),
            abilities=tuple(str(value) for value in payload.get("abilities", [])),
            cooldowns={str(key): int(value) for key, value in payload.get("cooldowns", {}).items()},
            attack_bias=int(payload.get("attack_bias", 100)),
            guard_bias=int(payload.get("guard_bias", 0)),
            ability_bias=int(payload.get("ability_bias", 0)),
        )


@dataclass(slots=True)
class CombatSession:
    fight_id: int
    fight_log_id: int
    user_id: int
    channel_id: int
    message_id: int | None
    source_kind: CombatSourceKind
    location: str
    approach: str
    encounter_title: str
    encounter_description: str
    resolution_title: str
    resolution_description: str
    reward_xp_win: int
    reward_xp_lose: int
    reputation_change: int
    round_number: int
    afk_skips: int
    last_round_summary: str
    turn_deadline_at: datetime
    player: CombatEntity
    enemies: tuple[CombatEntity, ...]
    created_at: datetime
    updated_at: datetime

    @property
    def primary_enemy(self) -> CombatEntity:
        return self.enemies[0]

    @property
    def enemy_name(self) -> str:
        return self.primary_enemy.name

    @property
    def enemy_hp_current(self) -> int:
        return self.primary_enemy.hp_current

    @property
    def enemy_hp_max(self) -> int:
        return self.primary_enemy.hp_max

    @property
    def player_hp_current(self) -> int:
        return self.player.hp_current

    @property
    def player_hp_max(self) -> int:
        return self.player.hp_max

    @property
    def player_mana_current(self) -> int:
        return self.player.mana_current

    @property
    def player_mana_max(self) -> int:
        return self.player.mana_max

    @property
    def player_power(self) -> int:
        return self.player.power

    @property
    def player_defense(self) -> int:
        return self.player.defense

    @property
    def player_speed(self) -> int:
        return self.player.speed

    @property
    def player_reiatsu(self) -> int:
        return self.player.reiatsu

    @property
    def focus_bonus(self) -> int:
        return 0

    @property
    def guard_active(self) -> bool:
        return False

    def to_active_exploration(self) -> ActiveExploration:
        return ActiveExploration(
            user_id=self.user_id,
            channel_id=self.channel_id,
            location=self.location,
            approach=self.approach,
            start_time=self.created_at,
            end_time=self.updated_at,
        )


@dataclass(slots=True)
class CombatChoice:
    action: CombatAction
    ability_key: str | None = None
    reason: str | None = None


@dataclass(slots=True)
class CombatLogEvent:
    turn_number: int
    summary_text: str
    detail_text: str
    payload: dict[str, Any]


@dataclass(slots=True)
class CombatRoundOutcome:
    session: CombatSession
    log_event: CombatLogEvent
    resolution_type: CombatResolutionType | None = None
    resolution_title: str | None = None
    resolution_description: str | None = None
    xp_reward: int = 0


@dataclass(slots=True)
class FightLogRecord:
    fight_log_id: int
    fight_id: int
    user_id: int
    source_kind: str
    outcome: str | None
    readable_log: str
    turn_payloads: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None
