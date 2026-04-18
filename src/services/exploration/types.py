from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.models.combat import ActiveExplorationCombat
from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.models.player import PlayerProfile
from src.models.work import ActiveWork


@dataclass(slots=True)
class StartExplorationResult:
    status: Literal[
        "started",
        "missing_profile",
        "resting",
        "insufficient_stamina",
        "active",
        "finished",
        "pending_choice",
        "active_work",
    ]
    player: PlayerProfile | None = None
    exploration: ActiveExploration | None = None
    work: ActiveWork | None = None
    rest_minutes: int = 0
    rest_recovery: int = 0
    pending_choice: "ExplorationDecisionPrompt | None" = None
    stamina_cost: int = 0
    base_stamina_cost: int = 0
    duration_minutes: int = 0
    base_duration_minutes: int = 0
    wounded_penalty: bool = False


@dataclass(slots=True)
class ExplorationResolution:
    exploration: ActiveExploration
    player: PlayerProfile
    event_type: Literal["reward", "combat", "choice", "flavor"]
    title: str
    description: str
    xp_gained: int
    levels_gained: int
    base_xp: int = 0
    reputation_xp_modifier_pct: int = 0
    reputation_change: int = 0
    combat_outcome: str | None = None
    explore_xp_effect_text: str | None = None
    applied_effect: "AppliedExploreEffect | None" = None
    applied_loot: "AppliedExploreLoot | None" = None


@dataclass(slots=True)
class AppliedExploreEffect:
    title: str
    description: str
    summary_text: str


@dataclass(slots=True)
class AppliedExploreLoot:
    item_key: str
    item_name: str
    quantity: int
    description: str
    summary_text: str


@dataclass(frozen=True, slots=True)
class ExplorationDecisionOptionRender:
    slot: int
    label: str
    style: Literal["primary", "secondary", "success", "danger"]


@dataclass(slots=True)
class ExplorationDecisionPrompt:
    session: PendingExplorationChoice
    prompt_kind: Literal["decision", "special_offer", "special_event", "npc_event"]
    event_title: str
    step_title: str
    description: str
    step_number: int
    total_steps: int
    options: tuple[ExplorationDecisionOptionRender, ...]
    stamina_cost: int = 0
    stamina_cost_modifier: int = 0
    reputation_title: str = "Unknown"


@dataclass(slots=True)
class ExplorationPostResult:
    status: Literal["instant", "choice_prompt", "combat_prompt"]
    resolution: ExplorationResolution | None = None
    prompt: ExplorationDecisionPrompt | None = None
    combat: ActiveExplorationCombat | None = None


@dataclass(slots=True)
class ExplorationChoiceAdvanceResult:
    status: Literal["missing", "advanced", "updated", "resolved", "insufficient_stamina", "combat"]
    prompt: ExplorationDecisionPrompt | None = None
    resolution: ExplorationResolution | None = None
    required_stamina: int = 0
    combat: ActiveExplorationCombat | None = None
