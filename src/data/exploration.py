from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Literal


ExploreEventType = Literal["reward", "combat", "choice", "flavor"]
ExploreFlowType = Literal["instant", "single_choice", "multi_step"]
ExploreXpProfile = Literal[
    "none",
    "approach_low",
    "approach_base",
    "approach_high",
    "combat_win",
    "combat_lose",
    "special_base",
    "special_high",
    "special_combat_win",
    "special_combat_lose",
]
ButtonStyleName = Literal["primary", "secondary", "success", "danger"]
ExploreFocusKey = Literal[
    "explore_streets",
    "scavenge_supplies",
    "help_district",
    "chase_rumors",
    "look_for_fight",
]


@dataclass(frozen=True, slots=True)
class ExploreApproachDefinition:
    key: str
    label: str
    duration_minutes: int
    stamina_cost: int
    xp_min: int
    xp_max: int
    risk_tier: str
    reward_tier: str
    event_biases: dict[ExploreEventType, int]
    menu_description: str
    intro_text: str
    focus_key: str = "legacy"
    focus_emoji: str = "🧭"
    focus_description: str = ""
    duration_key: str = "legacy"
    duration_emoji: str = "⏱"

    @property
    def id(self) -> str:
        return self.key

    @property
    def name(self) -> str:
        return self.label

    @property
    def duration_label(self) -> str:
        return f"{self.duration_minutes}m"

    @property
    def dropdown_label(self) -> str:
        return f"{self.label} [{self.duration_label}]"


@dataclass(frozen=True, slots=True)
class ExplorationEventTemplate:
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class ExploreFocusDefinition:
    key: ExploreFocusKey
    label: str
    emoji: str
    description: str
    menu_description: str
    intro_text: str
    event_biases: dict[ExploreEventType, int]


@dataclass(frozen=True, slots=True)
class ExploreDurationDefinition:
    key: str
    label: str
    emoji: str
    duration_minutes: int
    stamina_cost: int
    risk_tier: str
    reward_tier: str
    description: str


@dataclass(frozen=True, slots=True)
class ExplorationOutcomeDefinition:
    title: str
    description: str
    event_type: ExploreEventType
    xp_profile: ExploreXpProfile
    reputation_change: int = 0
    combat_outcome: str | None = None


@dataclass(frozen=True, slots=True)
class ExplorationDecisionOptionDefinition:
    key: str
    label: str
    style: ButtonStyleName
    next_step_id: str | None = None
    outcome: ExplorationOutcomeDefinition | None = None


@dataclass(frozen=True, slots=True)
class ExplorationDecisionStepDefinition:
    key: str
    title: str
    description: str
    options: tuple[ExplorationDecisionOptionDefinition, ...]


@dataclass(frozen=True, slots=True)
class ExplorationDecisionEventDefinition:
    key: str
    title: str
    flow_type: Literal["single_choice", "multi_step"]
    initial_step_id: str
    steps: tuple[ExplorationDecisionStepDefinition, ...]
    min_rep: int | None = None
    max_rep: int | None = None

    @property
    def step_count(self) -> int:
        return 2 if self.flow_type == "multi_step" else 1


@dataclass(frozen=True, slots=True)
class LocationEventPool:
    reward_events: tuple[ExplorationEventTemplate, ...]
    combat_events: tuple[ExplorationEventTemplate, ...]
    choice_events: tuple[ExplorationEventTemplate, ...]
    flavor_events: tuple[ExplorationEventTemplate, ...]


@dataclass(frozen=True, slots=True)
class LocationExploreDefinition:
    location_key: str
    menu_title: str
    menu_description: str
    menu_footer: str
    approach_pool: tuple[ExploreApproachDefinition, ...]
    event_pool: LocationEventPool
    single_choice_events: tuple[ExplorationDecisionEventDefinition, ...]
    multi_step_events: tuple[ExplorationDecisionEventDefinition, ...]
    special_offer_templates: tuple[ExplorationEventTemplate, ...]
    special_events: tuple[ExplorationDecisionEventDefinition, ...]


def _biases(
    *,
    reward: int,
    combat: int,
    choice: int,
    flavor: int,
) -> dict[ExploreEventType, int]:
    return {
        "reward": reward,
        "combat": combat,
        "choice": choice,
        "flavor": flavor,
    }


def _outcome(
    *,
    title: str,
    description: str,
    event_type: ExploreEventType,
    xp_profile: ExploreXpProfile,
    reputation_change: int = 0,
    combat_outcome: str | None = None,
) -> ExplorationOutcomeDefinition:
    return ExplorationOutcomeDefinition(
        title=title,
        description=description,
        event_type=event_type,
        xp_profile=xp_profile,
        reputation_change=reputation_change,
        combat_outcome=combat_outcome,
    )


def _option(
    *,
    key: str,
    label: str,
    style: ButtonStyleName,
    next_step_id: str | None = None,
    outcome: ExplorationOutcomeDefinition | None = None,
) -> ExplorationDecisionOptionDefinition:
    return ExplorationDecisionOptionDefinition(
        key=key,
        label=label,
        style=style,
        next_step_id=next_step_id,
        outcome=outcome,
    )


RUKONGAI_STREETS_APPROACHES = (
    ExploreApproachDefinition(
        key="rukongai_search_scraps",
        label="Search for scraps",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=54, combat=10, choice=10, flavor=26),
        menu_description="Low risk. Best option for scavenging cloth, food scraps, and other leftovers.",
        intro_text="You drift through busted stalls and broken crates, hoping the streets left something behind.",
    ),
    ExploreApproachDefinition(
        key="rukongai_follow_crowd",
        label="Follow the crowd",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=30, combat=12, choice=38, flavor=20),
        menu_description="Low risk. Blend in and chase movement in the district.",
        intro_text="You let the flow of hungry souls carry you, listening for where fear and opportunity gather.",
    ),
    ExploreApproachDefinition(
        key="rukongai_keep_head_down",
        label="Keep your head down",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=22, combat=10, choice=18, flavor=50),
        menu_description="Lowest risk. Stay unseen and survive the block.",
        intro_text="You avoid hard stares and lowered blades, moving like another tired soul trying to make it through the hour.",
    ),
    ExploreApproachDefinition(
        key="rukongai_listen_rumors",
        label="Listen for rumors",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="medium",
        event_biases=_biases(reward=28, combat=10, choice=42, flavor=20),
        menu_description="Low risk. Chase whispers, debts, and dirty secrets.",
        intro_text="You haunt cookfires and alley corners, picking truth out of desperate whispers and cheap lies.",
    ),
    ExploreApproachDefinition(
        key="rukongai_walk_back_alleys",
        label="Walk the back alleys",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=30, combat=28, choice=18, flavor=24),
        menu_description="Medium risk. The alleys hide danger and useful scraps.",
        intro_text="You slip away from the main flow and into the narrow veins of the district, where trouble rarely announces itself.",
    ),
    ExploreApproachDefinition(
        key="rukongai_offer_help",
        label="Offer a helping hand",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=36, combat=12, choice=34, flavor=18),
        menu_description="Medium risk. Small kindness can open unexpected doors.",
        intro_text="You spend your time helping where you can, knowing Rukongai remembers even the smallest mercy.",
    ),
    ExploreApproachDefinition(
        key="rukongai_check_market_edges",
        label="Check the market edges",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=40, combat=18, choice=22, flavor=20),
        menu_description="Medium risk. Scavenge the fringe where trade breaks down.",
        intro_text="You circle the edges of the market where spoiled goods, thrown scrap, and bad tempers pile together.",
    ),
    ExploreApproachDefinition(
        key="rukongai_trail_figure",
        label="Trail a suspicious figure",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="high",
        event_biases=_biases(reward=18, combat=32, choice=34, flavor=16),
        menu_description="Medium risk. Follow trouble and hope it leads somewhere useful.",
        intro_text="You shadow a nervous soul through the district, careful not to lose them in the crowd or the smoke.",
    ),
    ExploreApproachDefinition(
        key="rukongai_push_rough_blocks",
        label="Push into the rough blocks",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=24, combat=48, choice=16, flavor=12),
        menu_description="High risk. Press deeper where gangs and fear hold ground.",
        intro_text="You leave the safer lanes behind and step into blocks where every doorway watches and every mistake costs.",
    ),
    ExploreApproachDefinition(
        key="rukongai_chase_disturbance",
        label="Chase a spiritual disturbance",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=20, combat=52, choice=16, flavor=12),
        menu_description="High risk. Hunt the pressure spike before it finds someone else.",
        intro_text="You lock onto a shiver in the spiritual air and follow it through shattered streets before it can fade.",
    ),
    ExploreApproachDefinition(
        key="rukongai_defend_corner",
        label="Defend your corner",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="medium",
        event_biases=_biases(reward=24, combat=44, choice=20, flavor=12),
        menu_description="High risk. Hold ground when the district turns ugly.",
        intro_text="You stay where the pressure is rising and make it clear that your corner will not fold without a fight.",
    ),
    ExploreApproachDefinition(
        key="rukongai_hunt_better_life",
        label="Hunt for a better life",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=34, combat=24, choice=30, flavor=12),
        menu_description="High risk. Chase a rare break beyond mere survival.",
        intro_text="You push beyond daily survival, looking for a thread that might actually pull you toward something better.",
    ),
)

LEGACY_RUKONGAI_STREETS_APPROACHES = RUKONGAI_STREETS_APPROACHES

RUKONGAI_EXPLORE_FOCUSES = (
    ExploreFocusDefinition(
        key="explore_streets",
        label="Explore the Streets",
        emoji="🧭",
        description="A broad run through Rukongai where anything from scraps to danger to quiet human moments can find you.",
        menu_description="Balanced run for scraps, danger, and street moments.",
        intro_text=(
            "You move through the district without forcing one narrow goal, reading the rhythm of the streets and taking whatever opening the night offers."
        ),
        event_biases=_biases(reward=28, combat=18, choice=30, flavor=24),
    ),
    ExploreFocusDefinition(
        key="scavenge_supplies",
        label="Scavenge for Supplies",
        emoji="🧺",
        description="Best for cloth scraps, food scraps, and the rough little materials that keep you alive long enough to craft.",
        menu_description="Best for cloth, food scraps, and crafting materials.",
        intro_text=(
            "You keep your eyes on broken stalls, discarded bundles, cookfires gone cold, and every corner where hunger might have left something behind."
        ),
        event_biases=_biases(reward=42, combat=10, choice=14, flavor=34),
    ),
    ExploreFocusDefinition(
        key="help_district",
        label="Help the District",
        emoji="🤝",
        description="Best for reputation, hard moral choices, and the kind of street memory that changes how people look at you.",
        menu_description="Best for reputation, moral choices, and local goodwill.",
        intro_text=(
            "You spend the run watching for people about to be cornered, cheated, or crushed under the weight of another bad night in Rukongai."
        ),
        event_biases=_biases(reward=30, combat=16, choice=36, flavor=18),
    ),
    ExploreFocusDefinition(
        key="chase_rumors",
        label="Chase Rumors",
        emoji="👂",
        description="Best for leads, whispers, hidden routes, NPC trouble, and the kind of clue that can turn into a bigger score later.",
        menu_description="Best for leads, whispers, hidden routes, and clues.",
        intro_text=(
            "You trail whispers from washlines, cookfires, doorway mutters, and half-swallowed warnings, trusting that one real lead is buried somewhere in the noise."
        ),
        event_biases=_biases(reward=18, combat=14, choice=48, flavor=20),
    ),
    ExploreFocusDefinition(
        key="look_for_fight",
        label="Look for a Fight",
        emoji="⚔️",
        description="Best for combat, danger, and higher XP if you can walk away from the clash still standing.",
        menu_description="Best for combat, danger, and higher XP.",
        intro_text=(
            "You stop pretending tonight will stay quiet and start hunting the places where pressure, anger, and fear are about to break into violence."
        ),
        event_biases=_biases(reward=10, combat=56, choice=20, flavor=14),
    ),
)

RUKONGAI_EXPLORE_DURATIONS = (
    ExploreDurationDefinition(
        key="quick",
        label="2m Quick",
        emoji="⏱️",
        duration_minutes=2,
        stamina_cost=10,
        risk_tier="low",
        reward_tier="low",
        description="Safer and lighter. Good for cautious runs and fast scavenging.",
    ),
    ExploreDurationDefinition(
        key="steady",
        label="3m Balanced",
        emoji="🕰️",
        duration_minutes=3,
        stamina_cost=14,
        risk_tier="medium",
        reward_tier="medium",
        description="A balanced commitment with room for trouble or payoff.",
    ),
    ExploreDurationDefinition(
        key="deep",
        label="5m Risky",
        emoji="🌒",
        duration_minutes=5,
        stamina_cost=20,
        risk_tier="high",
        reward_tier="high",
        description="Long enough for better chances, uglier turns, and stronger rewards.",
    ),
    ExploreDurationDefinition(
        key="grind",
        label="10m Jackpot",
        emoji="🔥",
        duration_minutes=10,
        stamina_cost=30,
        risk_tier="high",
        reward_tier="high",
        description="A hard commitment with the biggest danger and the best shot at major outcomes.",
    ),
)


def _merge_biases(
    base: dict[ExploreEventType, int],
    adjustment: dict[ExploreEventType, int],
) -> dict[ExploreEventType, int]:
    merged: dict[ExploreEventType, int] = {}
    for event_type in ("reward", "combat", "choice", "flavor"):
        merged[event_type] = max(1, base.get(event_type, 0) + adjustment.get(event_type, 0))
    return merged


def _duration_bias_adjustment(duration_key: str) -> dict[ExploreEventType, int]:
    adjustments = {
        "quick": _biases(reward=-2, combat=-6, choice=-2, flavor=10),
        "steady": _biases(reward=0, combat=0, choice=0, flavor=0),
        "deep": _biases(reward=4, combat=5, choice=2, flavor=-11),
        "grind": _biases(reward=8, combat=8, choice=6, flavor=-22),
    }
    return adjustments[duration_key]


def _build_rukongai_focus_approaches() -> tuple[ExploreApproachDefinition, ...]:
    approaches: list[ExploreApproachDefinition] = []
    for focus in RUKONGAI_EXPLORE_FOCUSES:
        for duration in RUKONGAI_EXPLORE_DURATIONS:
            approaches.append(
                ExploreApproachDefinition(
                    key=f"rukongai_{focus.key}_{duration.key}",
                    label=focus.label,
                    duration_minutes=duration.duration_minutes,
                    stamina_cost=duration.stamina_cost,
                    xp_min=max(4, duration.duration_minutes * 3),
                    xp_max=max(8, duration.duration_minutes * 5),
                    risk_tier=duration.risk_tier,
                    reward_tier=duration.reward_tier,
                    event_biases=_merge_biases(
                        focus.event_biases,
                        _duration_bias_adjustment(duration.key),
                    ),
                    menu_description=f"{focus.description} {duration.description}",
                    intro_text=focus.intro_text,
                    focus_key=focus.key,
                    focus_emoji=focus.emoji,
                    focus_description=focus.description,
                    duration_key=duration.key,
                    duration_emoji=duration.emoji,
                )
            )
    return tuple(approaches)


RUKONGAI_STREETS_APPROACHES = _build_rukongai_focus_approaches()

RUKONGAI_STREETS_EVENTS = LocationEventPool(
    reward_events=(
        ExplorationEventTemplate(
            title="Scrap Luck",
            description=(
                "Halfway through the run, your foot kicks something under a sheet of warped wood. "
                "It is only a little salvage, but tonight that little feels like the district looked away for one second and let you keep it."
            ),
        ),
        ExplorationEventTemplate(
            title="A Kind Hand in a Hard Place",
            description=(
                "Near the end of the run, someone you helped earlier presses a wrapped ration into your hand without meeting your eyes. "
                "No speech. No thanks. Just proof that kindness is not dead here yet, only ashamed to be seen."
            ),
        ),
        ExplorationEventTemplate(
            title="Market Edge Score",
            description=(
                "The market fringe breaks into shouting, then silence. By the time you reach the aftermath, the best scraps are gone but not all of them. "
                "You come away with enough to call it a good night by Rukongai standards."
            ),
        ),
        ExplorationEventTemplate(
            title="Rumor Turned Reward",
            description=(
                "A whisper picked up along the way leads you behind split stone and mold-stiff cloth. "
                "Most rumors out here rot on the tongue. This one leaves something real in your hands."
            ),
        ),
    ),
    combat_events=(
        ExplorationEventTemplate(
            title="Alley Ambush",
            description=(
                "A narrow alley opens ahead of you, and the silence inside it is wrong. "
                "By the time you feel the eyes on you, the first step toward violence is already taken."
            ),
        ),
        ExplorationEventTemplate(
            title="Raider Stirring",
            description=(
                "A thin warning cry tears across the lane and a desperate raider lunges out from the wreckage between homes. "
                "A starving cutthroat in a poor block is still bad news for everyone nearby."
            ),
        ),
        ExplorationEventTemplate(
            title="Gang Pressure",
            description=(
                "You drift into a stretch claimed by local toughs who have not eaten enough and want you to know it. "
                "One hard look becomes two, and then the whole block shifts."
            ),
        ),
        ExplorationEventTemplate(
            title="Corner Turned Violent",
            description=(
                "It starts with a stare, then a shove, then somebody deciding your worn-out little pile of survival ought to be theirs. "
                "The whole thing turns ugly in a blink."
            ),
        ),
    ),
    choice_events=(
        ExplorationEventTemplate(
            title="A Whisper Worth Chasing",
            description=(
                "A rumor catches in the back of your mind and refuses to leave. "
                "Safe route. Hidden stash. Debt collectors on the move. Three possibilities, and all of them smell like trouble."
            ),
        ),
        ExplorationEventTemplate(
            title="Need Versus Opportunity",
            description=(
                "A stranger with gaunt cheeks needs help now. Ten steps away, a risky opening cracks wide in the district. "
                "You get just enough time to hate whichever choice you make."
            ),
        ),
        ExplorationEventTemplate(
            title="The Street Tests Your Instincts",
            description=(
                "The crowd breaks wrong around you. Fear runs one way, hunger runs the other, and for one heartbeat you can see the shape of what comes next."
            ),
        ),
        ExplorationEventTemplate(
            title="A Lead in the Dust",
            description=(
                "Dust, boot marks, a dropped cloth charm, and noise from farther down the lane. "
                "You stop in one of those small moments that only stays small if you walk away."
            ),
        ),
    ),
    flavor_events=(
        ExplorationEventTemplate(
            title="Another Night in Rukongai",
            description=(
                "The night gives you no score worth bragging about. Just smoke in your clothes, thin lantern light, and the soft scrape of neighbors making one more night out of almost nothing."
            ),
        ),
        ExplorationEventTemplate(
            title="Hunger in the Air",
            description=(
                "You end up near a cookfire full of water pretending to be soup. "
                "Nobody laughs. Nobody complains. They just keep waiting for it to be enough."
            ),
        ),
        ExplorationEventTemplate(
            title="Small Mercy, Small Hope",
            description=(
                "Before the run is over, you catch two neighbors splitting a meal that would not fill one stomach. "
                "They do it anyway. Somehow that stays with you longer than a bigger prize might have."
            ),
        ),
        ExplorationEventTemplate(
            title="The District Watches Back",
            description=(
                "The alleys give you no reward, only the feeling of being weighed. "
                "By the time you turn back, you know the block a little better, and it knows you too."
            ),
        ),
    ),
)

RUKONGAI_STREETS_SINGLE_CHOICE_EVENTS = (
    ExplorationDecisionEventDefinition(
        key="rukongai_hidden_ration",
        title="Hidden Ration",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A sack beneath the boards",
                description=(
                    "A ration sack shows under warped planks just as your hand reaches for it. "
                    "Two other hungry souls see it in the same breath. Nobody speaks. Nobody needs to."
                ),
                options=(
                    _option(
                        key="split_it",
                        label="Split it",
                        style="success",
                        outcome=_outcome(
                            title="Small Victory Shared",
                            description=(
                                "You split the find instead of clutching it all for yourself. Nobody eats well, but in a district like this, people remember a soul who still knows how to share."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="take_it",
                        label="Take it and move",
                        style="danger",
                        outcome=_outcome(
                            title="Hard Choice, Hard Street",
                            description=(
                                "You grab the ration and disappear before hunger turns into knives. You stay fed a little longer, but the look left behind follows you."
                            ),
                            event_type="choice",
                            xp_profile="approach_base",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="leave_it",
                        label="Leave it",
                        style="secondary",
                        outcome=_outcome(
                            title="Empty Hands",
                            description=(
                                "You step back and let the others have it. The street stays quiet, and you carry on with one more lesson about what Rukongai does to people."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_washline_rumor",
        title="Rumor at the Washline",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A whisper worth acting on",
                description=(
                    "A washline whisper turns sharp halfway through the run. "
                    "A pack of raiders is circling a nearby block, and a gang means to make coin off the fear before dawn."
                ),
                options=(
                    _option(
                        key="chase_whisper",
                        label="Chase the whisper",
                        style="primary",
                        outcome=_outcome(
                            title="You Follow the Lead",
                            description=(
                                "You move on the rumor before it cools and catch the trail while it still matters. In Rukongai, acting fast is often the only edge you get."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                        ),
                    ),
                    _option(
                        key="warn_locals",
                        label="Warn the block",
                        style="success",
                        outcome=_outcome(
                            title="The Warning Holds",
                            description=(
                                "You pass the warning from doorway to doorway until the whole stretch is awake. Panic still stirs, but it never gets to own the block."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="ignore_it",
                        label="Let it pass",
                        style="secondary",
                        outcome=_outcome(
                            title="Noise in the District",
                            description=(
                                "You let the rumor drift on without you. Around here, every alley wants something, and nobody has enough strength for all of it."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_corner_hollow",
        title="Raiders by the Wall",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A shriek in the plaster",
                description=(
                    "Near the end of the run, a cracked wall rattles with boots and low voices. "
                    "A small raider crew is probing the edge of the block, and everybody hiding nearby knows what happens if nobody answers it."
                ),
                options=(
                    _option(
                        key="drive_it_off",
                        label="Drive it off",
                        style="danger",
                        outcome=_outcome(
                            title="The Raiders Break First",
                            description=(
                                "You hit the raiders before fear can spread. It is quick, filthy work, but the lane breathes easier when it's over."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="draw_it_away",
                        label="Draw it away",
                        style="primary",
                        outcome=_outcome(
                            title="Danger Redirected",
                            description=(
                                "You draw the raiders away from the homes and buy the block a few precious minutes of quiet. In these streets, that counts."
                            ),
                            event_type="choice",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="raise_alarm",
                        label="Raise the alarm",
                        style="success",
                        outcome=_outcome(
                            title="The Block Stands Ready",
                            description=(
                                "You shout the warning before the danger lands. Doors slam, lamps go dark, and the block rides out the worst of it standing."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                ),
            ),
        ),
    ),
)

RUKONGAI_STREETS_MULTI_STEP_EVENTS = (
    ExplorationDecisionEventDefinition(
        key="rukongai_market_debt",
        title="Debt in the Market Fringe",
        flow_type="multi_step",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The collector arrives",
                description=(
                    "You reach the market edge at the worst moment. "
                    "A gang collector has a vendor trapped by the stall, and the whole stretch is pretending not to look while listening to every word."
                ),
                options=(
                    _option(key="shadow", label="Shadow the collector", style="primary", next_step_id="shadow_step"),
                    _option(key="back_vendor", label="Back the vendor", style="success", next_step_id="vendor_step"),
                    _option(
                        key="leave",
                        label="Leave it",
                        style="secondary",
                        outcome=_outcome(
                            title="You Keep Moving",
                            description=(
                                "You keep your head down and move on. In Rukongai, not every fight is yours, even when leaving it behind tastes bitter."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="shadow_step",
                title="You have their trail",
                description=(
                    "You fall in behind the collector through broken alleys and stacks of split crates. "
                    "One careless sound ends the tail. One clean read might show you where the stolen scraps keep disappearing."
                ),
                options=(
                    _option(
                        key="keep_tailing",
                        label="Keep tailing",
                        style="primary",
                        outcome=_outcome(
                            title="You Find the Hideout",
                            description=(
                                "You stay patient and catch the stash point without tipping your hand. That kind of patience can feed more than one empty night."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="spring_trap",
                        label="Spring the trap",
                        style="danger",
                        outcome=_outcome(
                            title="Collector Put Down",
                            description=(
                                "You strike before the collector can bark for help. The alley turns mean in a heartbeat, but you're the one left standing."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="vendor_step",
                title="Now the street is looking at you",
                description=(
                    "The second you step in, the air changes. "
                    "The crowd is still scared, but now it is watching you to decide whether this becomes courage or blood."
                ),
                options=(
                    _option(
                        key="rally_crowd",
                        label="Rally the crowd",
                        style="success",
                        outcome=_outcome(
                            title="The Crowd Holds the Line",
                            description=(
                                "You turn fear into backbone. Once the collector sees the whole stretch stop bowing, he decides this debt is not worth bleeding for."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=5,
                        ),
                    ),
                    _option(
                        key="take_hit",
                        label="Take the hit",
                        style="danger",
                        outcome=_outcome(
                            title="You Hold the Corner",
                            description=(
                                "You take the first hit so the vendor does not have to. It hurts like hell, but nobody on that corner forgets who held the line."
                            ),
                            event_type="combat",
                            xp_profile="combat_lose",
                            reputation_change=2,
                            combat_outcome="Setback",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_alley_cry",
        title="A Cry from the Alley",
        flow_type="multi_step",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="Someone is calling for help",
                description=(
                    "A cry for help cuts through the alley maze late in the run. "
                    "It sounds thin, frightened, and maybe a little too well placed. In Rukongai, that usually means trouble either way."
                ),
                options=(
                    _option(key="investigate", label="Investigate", style="primary", next_step_id="investigate_step"),
                    _option(key="watch", label="Watch from cover", style="secondary", next_step_id="watch_step"),
                    _option(
                        key="move_on",
                        label="Move on",
                        style="secondary",
                        outcome=_outcome(
                            title="You Leave the Cry Behind",
                            description=(
                                "You let the alley keep its secrets and move on. Surviving this place sometimes means accepting that you cannot answer every cry."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="investigate_step",
                title="It was a trap, but not only a trap",
                description=(
                    "You step in and find a wounded soul slumped against the wall just as shadows start to close. "
                    "The trap is real. So is the person caught in it."
                ),
                options=(
                    _option(
                        key="help_wounded",
                        label="Help the wounded",
                        style="success",
                        outcome=_outcome(
                            title="Mercy Before Escape",
                            description=(
                                "You get the wounded soul moving before the alley seals shut. It is clumsy, desperate work, but you drag both of you through it."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="set_trap",
                        label="Turn it back on them",
                        style="danger",
                        outcome=_outcome(
                            title="Ambushers Broken",
                            description=(
                                "You use the alley against the ambushers and break their rush before it becomes a beating in the dark."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="watch_step",
                title="The pattern becomes clear",
                description=(
                    "From cover, the whole setup finally shows itself: the bait, the watchers, the lane they want their victim to stumble into. "
                    "Now that you see the shape of it, you either break it or carry the knowledge away."
                ),
                options=(
                    _option(
                        key="intervene",
                        label="Step in",
                        style="danger",
                        outcome=_outcome(
                            title="You Break the Setup",
                            description=(
                                "You move at the exact right moment and smash the setup before it snaps shut. The alley erupts, but the people marked for it get out."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="slip_away",
                        label="Slip away with intel",
                        style="primary",
                        outcome=_outcome(
                            title="Knowledge Carried Forward",
                            description=(
                                "You leave unseen with a better read on the alley crews and their patterns. Sometimes the best win is knowing where not to be next time."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                        ),
                    ),
                ),
            ),
        ),
    ),
)

RUKONGAI_STREETS_SPECIAL_OFFERS = (
    ExplorationEventTemplate(
        title="A Hidden Pull in the District",
        description=(
            "Just when the run feels finished, something catches at the edge of your senses. "
            "A buried spiritual pull. A hidden pocket. The kind of chance that usually costs more than it gives."
        ),
    ),
    ExplorationEventTemplate(
        title="A Rare Opening",
        description=(
            "The streets shift around you and, for one narrow second, something opens that should have stayed hidden. "
            "It smells like hunger, luck, and bad judgment all at once."
        ),
    ),
    ExplorationEventTemplate(
        title="Something Valuable Stirs",
        description=(
            "A lead with real weight behind it rises out of the run. "
            "Not rumor. Not wishful thinking. Something worth chasing, if you are willing to pay for it up front."
        ),
    ),
)

RUKONGAI_STREETS_SPECIAL_EVENTS = (
    ExplorationDecisionEventDefinition(
        key="rukongai_special_buried_cache",
        title="Buried Cache Below the Stone",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The opening is real, but unstable",
                description=(
                    "You force your way into the hidden pocket and find a cramped cache under cracked stone. "
                    "It is real. So is the noise you're making, and out here noise is just another way of inviting company."
                ),
                options=(
                    _option(
                        key="grab_fast",
                        label="Grab what you can",
                        style="primary",
                        outcome=_outcome(
                            title="Quick Hands, Hard-Won Prize",
                            description=(
                                "You snatch the best of the stash before the alley folds in on itself. It is not pretty, but it beats going hungry."
                            ),
                            event_type="reward",
                            xp_profile="special_base",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="hold_ground",
                        label="Hold the site",
                        style="danger",
                        outcome=_outcome(
                            title="You Hold the Cache",
                            description=(
                                "You plant your feet and fight for the hidden stash when the rush comes. It is brutal, loud, and exactly the kind of thing the district talks about after."
                            ),
                            event_type="combat",
                            xp_profile="special_combat_win",
                            reputation_change=-2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="pull_back",
                        label="Pull back with scraps",
                        style="secondary",
                        outcome=_outcome(
                            title="You Settle for Less",
                            description=(
                                "You abandon the deepest part of the stash before the danger peaks. The haul is smaller than it could have been, but you still leave with more than you started with."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_special_hollow_nest",
        title="Raider Hideout",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The reiatsu trail leads to a nest",
                description=(
                    "The strange pull resolves behind a line of wrecked walls, where raiders have been hiding out in the dark. "
                    "There is value here, but the whole place feels one bad move away from erupting."
                ),
                options=(
                    _option(
                        key="purge_nest",
                        label="Hit the hideout",
                        style="danger",
                        outcome=_outcome(
                            title="Hideout Broken Open",
                            description=(
                                "You hit the hideout head-on and tear it apart under a rain of splintered boards and shouted threats. The block will sleep easier for it, even if you do not."
                            ),
                            event_type="combat",
                            xp_profile="special_combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="lure_one_out",
                        label="Lure a few out",
                        style="primary",
                        outcome=_outcome(
                            title="Controlled Risk, Real Gain",
                            description=(
                                "You bait only part of the hideout into the open and take what you can from the opening. It is slower, safer, and still far richer than a routine street run."
                            ),
                            event_type="reward",
                            xp_profile="special_base",
                        ),
                    ),
                    _option(
                        key="retreat_scuffed",
                        label="Retreat when it spikes",
                        style="secondary",
                        outcome=_outcome(
                            title="The Chance Slips Away",
                            description=(
                                "You back off when the pressure grows ugly. The opportunity vanishes, and all you carry away is a partial read on what was hiding there."
                            ),
                            event_type="flavor",
                            xp_profile="special_combat_lose",
                            combat_outcome="Setback",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_special_gang_route",
        title="Gang Courier Route",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="You found the handoff lane",
                description=(
                    "The lead opens onto a handoff lane where local gangs move food, scrap, and every other stolen comfort worth guarding. "
                    "One bold move here could feed you for days, or get your name dragged through every block nearby."
                ),
                options=(
                    _option(
                        key="hit_courier",
                        label="Hit the courier",
                        style="danger",
                        outcome=_outcome(
                            title="Courier Broken, Street Watching",
                            description=(
                                "You smash the courier lane before it can slip through your fingers. The score is real, and so is the trouble your name will stir after."
                            ),
                            event_type="combat",
                            xp_profile="special_combat_win",
                            reputation_change=-2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="shadow_and_steal",
                        label="Shadow and steal",
                        style="primary",
                        outcome=_outcome(
                            title="You Peel Off the Best Cut",
                            description=(
                                "You tail the lane until it opens up, then peel off the best cut at the perfect moment. Clean for Rukongai, dirty everywhere else."
                            ),
                            event_type="reward",
                            xp_profile="special_high",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="take_small_piece",
                        label="Take a small piece",
                        style="success",
                        outcome=_outcome(
                            title="A Smaller Score, Still Worth It",
                            description=(
                                "You avoid the bloodiest version of the chance and settle for a safer cut. It is less than glory, but still better than an ordinary night."
                            ),
                            event_type="choice",
                            xp_profile="special_base",
                        ),
                    ),
                ),
            ),
        ),
    ),
)

RUKONGAI_STREETS_EVENTS = LocationEventPool(
    reward_events=RUKONGAI_STREETS_EVENTS.reward_events
    + (
        ExplorationEventTemplate(
            title="Washed-Up Bundle",
            description=(
                "Rainwater pushes a wrapped bundle against a broken curb and everyone else misses it for one blessed second. "
                "Inside is nothing fine, just salvage still worth the trouble of carrying home."
            ),
        ),
        ExplorationEventTemplate(
            title="Lantern Seller's Leftovers",
            description=(
                "A shuttered lantern stall gives up a forgotten little cache near the ash pit behind it. "
                "The district has already chewed through the best of it, but not quite all of it."
            ),
        ),
    ),
    combat_events=RUKONGAI_STREETS_EVENTS.combat_events
    + (
        ExplorationEventTemplate(
            title="Knife in the Queue",
            description=(
                "A food line turns jagged halfway through the run when someone decides hunger makes the rules now. "
                "By the time you see the blade, the crowd is already breaking around it."
            ),
        ),
        ExplorationEventTemplate(
            title="Dockside Stickup",
            description=(
                "A narrow lane choked with old crates goes still in the wrong way. "
                "The kind of silence that means somebody ahead has already picked a victim and is waiting to see if it's you."
            ),
        ),
    ),
    choice_events=RUKONGAI_STREETS_EVENTS.choice_events
    + (
        ExplorationEventTemplate(
            title="A Lead Passed Quietly",
            description=(
                "Someone brushes by with a warning too soft to repeat twice. "
                "There is a cache moving tonight, a debt changing hands, or a lie that will get somebody hurt unless the right soul follows it."
            ),
        ),
        ExplorationEventTemplate(
            title="Doorway Debt",
            description=(
                "A half-open doorway catches your eye at the wrong moment. "
                "Inside, fear and bargaining are already underway, and stepping closer means deciding whether this becomes your problem too."
            ),
        ),
    ),
    flavor_events=RUKONGAI_STREETS_EVENTS.flavor_events
    + (
        ExplorationEventTemplate(
            title="Smoke and Rain",
            description=(
                "Smoke from a dozen weak cookfires drifts low while rain starts thinking about falling. "
                "The whole district feels like it is bracing for one more bad turn and pretending not to."
            ),
        ),
        ExplorationEventTemplate(
            title="Lanterns Behind Paper",
            description=(
                "Thin paper windows glow in the dark with the kind of light that means people are still awake because they have too much to lose to sleep."
            ),
        ),
    ),
)

RUKONGAI_STREETS_SINGLE_CHOICE_EVENTS = RUKONGAI_STREETS_SINGLE_CHOICE_EVENTS + (
    ExplorationDecisionEventDefinition(
        key="rukongai_soup_line",
        title="Soup Line Trouble",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="One pot, too many hands",
                description=(
                    "A pot thin enough to insult the word soup still draws a crowd in Rukongai. "
                    "When the line starts to fold in on itself, everyone nearby has to decide what kind of hunger they answer first."
                ),
                options=(
                    _option(
                        key="share_bowl",
                        label="Keep it fair",
                        style="success",
                        outcome=_outcome(
                            title="A Bowl Shared Around",
                            description=(
                                "You help hold the line together long enough for everyone to get something small. Nobody leaves full, but the block remembers who stopped the scramble."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="eat_first",
                        label="Take your share first",
                        style="danger",
                        outcome=_outcome(
                            title="You Eat First",
                            description=(
                                "You shoulder in, take the thicker portion, and walk before anyone can stop you. It keeps you standing a little longer and leaves a sour taste that is not just the broth."
                            ),
                            event_type="choice",
                            xp_profile="approach_base",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="step_back",
                        label="Step back from it",
                        style="secondary",
                        outcome=_outcome(
                            title="Hunger Wins Quietly",
                            description=(
                                "You let the line sort itself out without you. Nobody thanks you, nobody curses you, and the district keeps scraping forward one thin bowl at a time."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_map_scrap",
        title="Map Scrap in the Mud",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A route someone tried to hide",
                description=(
                    "A half-ruined map scrap sticks to the mud under your sandal. "
                    "The markings are rough, but they look like the kind of hand-drawn route only desperate souls pass around when supplies need to move unseen."
                ),
                options=(
                    _option(
                        key="mark_safe_route",
                        label="Mark it for others",
                        style="success",
                        outcome=_outcome(
                            title="You Mark the Safe Route",
                            description=(
                                "You leave the route in a way the right eyes might catch it. It costs you the private advantage, but somebody else in this district gets to make it home cleaner than they would have."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="pocket_route",
                        label="Keep it to yourself",
                        style="danger",
                        outcome=_outcome(
                            title="Lead Kept Close",
                            description=(
                                "You fold the map scrap into your sleeve and keep moving. A private route is worth more than goodwill on a hungry night."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="let_mud_take_it",
                        label="Leave it in the mud",
                        style="secondary",
                        outcome=_outcome(
                            title="The Street Keeps Its Secret",
                            description=(
                                "You leave the scrap where it lies. Maybe it was a trap. Maybe it was a lifeline. Either way, it stops being yours the second you walk on."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_breathless_courier",
        title="A Breathless Courier",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The message matters to someone",
                description=(
                    "A runner nearly crashes into you with blood on one sleeve and panic in both eyes. "
                    "Whatever message they are carrying matters enough for people to chase it."
                ),
                options=(
                    _option(
                        key="help_message",
                        label="Help them through",
                        style="success",
                        outcome=_outcome(
                            title="The Message Gets Through",
                            description=(
                                "You cut the runner through the safer side of the block and buy them just enough room to keep moving. Somewhere ahead, a family or a friend gets warned in time."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="take_fee",
                        label="Take a fee first",
                        style="danger",
                        outcome=_outcome(
                            title="A Fee Taken in Fear",
                            description=(
                                "You make the runner pay before you point the way. They hand it over because fear has already done the arguing for you."
                            ),
                            event_type="choice",
                            xp_profile="approach_base",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="not_yours",
                        label="Let them run alone",
                        style="secondary",
                        outcome=_outcome(
                            title="Not Your Message",
                            description=(
                                "You leave the runner to their own luck. In Rukongai, there is always another desperate message and never enough souls willing to carry it."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
        ),
    ),
)

RUKONGAI_STREETS_MULTI_STEP_EVENTS = RUKONGAI_STREETS_MULTI_STEP_EVENTS + (
    ExplorationDecisionEventDefinition(
        key="rukongai_floorboard_cache",
        title="Lead Under the Floorboards",
        flow_type="multi_step",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="Something is hidden under the room",
                description=(
                    "A loose board inside a half-collapsed room thumps wrong under your weight. "
                    "Someone hid something here on purpose, and the old woman watching from the doorway definitely knows more than she wants to say."
                ),
                options=(
                    _option(key="pry_boards", label="Pry up the boards", style="primary", next_step_id="boards_step"),
                    _option(key="ask_watcher", label="Ask the watcher", style="success", next_step_id="watcher_step"),
                    _option(
                        key="leave_room",
                        label="Leave it alone",
                        style="secondary",
                        outcome=_outcome(
                            title="You Leave the Floor to Its Secret",
                            description=(
                                "You walk back out and leave the room to its silence. Some secrets in Rukongai stay alive because people know when not to touch them."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="boards_step",
                title="There is a cache, but not a private one",
                description=(
                    "The floor gives up a small hidden stash of preserved food and scrap cloth. "
                    "The room belonged to a dead family, and the nearby doors are open just enough to prove the block knows what you found."
                ),
                options=(
                    _option(
                        key="share_cache",
                        label="Share it with the block",
                        style="success",
                        outcome=_outcome(
                            title="The Cache Feeds Three Homes",
                            description=(
                                "You split the find instead of claiming it all. It is still too little for the need around you, but the block watches the choice and does not forget it."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=5,
                        ),
                    ),
                    _option(
                        key="strip_cache",
                        label="Clear it out and move",
                        style="danger",
                        outcome=_outcome(
                            title="You Clear the Hiding Place Out",
                            description=(
                                "You take everything before the watching doors can fully open. The haul is real. So is the story that starts spreading behind you."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                            reputation_change=-5,
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="watcher_step",
                title="The old woman sets a price",
                description=(
                    "The old woman tells you the room is tied to a family that still has kin on the block. "
                    "She can tell you what is safe to take and what is not, but only if she decides you deserve the truth."
                ),
                options=(
                    _option(
                        key="show_respect",
                        label="Show respect",
                        style="primary",
                        outcome=_outcome(
                            title="A Quiet Name Opens a Door",
                            description=(
                                "You lower your voice, mind your tongue, and let the old woman decide how much to share. In return, she points you toward the part of the stash nobody will call theft."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="push_hard",
                        label="Push her for the location",
                        style="danger",
                        outcome=_outcome(
                            title="You Learn It the Ugly Way",
                            description=(
                                "You press too hard, and the room answers with more than words. The block does not like being leaned on, even by someone desperate."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=-2,
                            combat_outcome="Victory",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_lantern_debt",
        title="Lantern Debt at Dusk",
        flow_type="multi_step",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A debt comes due under weak light",
                description=(
                    "A collector corners a debtor under two paper lanterns that are already burning low. "
                    "The whole stretch is listening through walls, waiting to see whether this ends in shame, blood, or somebody getting clever."
                ),
                options=(
                    _option(key="back_debtor", label="Back the debtor", style="success", next_step_id="debtor_step"),
                    _option(key="trail_collector", label="Trail the collector", style="primary", next_step_id="collector_step"),
                    _option(
                        key="pass_lane",
                        label="Keep moving",
                        style="secondary",
                        outcome=_outcome(
                            title="Lantern Light on Someone Else's Trouble",
                            description=(
                                "You leave the lane to its own bad ending. In Rukongai, walking away is not always cowardice. Sometimes it is math."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="debtor_step",
                title="Now everyone is looking at you too",
                description=(
                    "The second you step in, the collector has to decide whether your face means problem or opportunity. "
                    "Either way, the debtor is no longer the only one being measured."
                ),
                options=(
                    _option(
                        key="cover_cost",
                        label="Help settle it",
                        style="success",
                        outcome=_outcome(
                            title="Debt Eased for One Night",
                            description=(
                                "You keep the lane from turning vicious and buy the debtor one more night without a beating. It is not a clean victory, but it keeps the block from cracking open."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="throw_first",
                        label="Throw the first blow",
                        style="danger",
                        outcome=_outcome(
                            title="Collector Driven Off",
                            description=(
                                "You hit first and hard enough to end the question. The lane goes dead quiet after, which in Rukongai usually means people approved more than they will ever say."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="collector_step",
                title="The money changes hands in the dark",
                description=(
                    "You follow the collector long enough to see where the payment gets moved. "
                    "It is a smaller handoff than the fear around it suggested, but still enough to matter to someone hungry."
                ),
                options=(
                    _option(
                        key="steal_purse",
                        label="Lift the payment",
                        style="primary",
                        outcome=_outcome(
                            title="You Walk Off with the Payment",
                            description=(
                                "You take the purse in the shuffle and vanish before the shouting starts. Dirty work, clean exit, and a few days of easier breathing bought the hard way."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="sell_doorway",
                        label="Sell out the debtor's door",
                        style="danger",
                        outcome=_outcome(
                            title="You Sell a Doorway Cheap",
                            description=(
                                "You trade the last useful detail for a quick cut of the take. It pays better than dignity, which is exactly why the district keeps making this kind of soul."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=-5,
                        ),
                    ),
                ),
            ),
        ),
    ),
)

RUKONGAI_STREETS_SPECIAL_EVENTS = RUKONGAI_STREETS_SPECIAL_EVENTS + (
    ExplorationDecisionEventDefinition(
        key="rukongai_special_trusted_knock",
        title="A Trusted Knock After Dark",
        flow_type="single_choice",
        initial_step_id="step_one",
        min_rep=21,
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="Someone finally opens the door",
                description=(
                    "A quiet family pulls you into a doorway because your name has been spoken well enough to matter. "
                    "They have a problem bigger than fear and smaller than a miracle, which means it belongs to Rukongai."
                ),
                options=(
                    _option(
                        key="hide_family",
                        label="Help hide them",
                        style="success",
                        outcome=_outcome(
                            title="A Door Opens for the Worthy",
                            description=(
                                "You use your standing to move the family before the wrong men arrive. It is not glory. It is better than glory. It is trust paying something back."
                            ),
                            event_type="reward",
                            xp_profile="special_high",
                            reputation_change=5,
                        ),
                    ),
                    _option(
                        key="hold_watch",
                        label="Hold the alley mouth",
                        style="danger",
                        outcome=_outcome(
                            title="You Hold the Alley Mouth",
                            description=(
                                "You buy the family time with your own body and name, planting yourself where the lane narrows and making the problem come through you first."
                            ),
                            event_type="combat",
                            xp_profile="special_combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="refuse_risk",
                        label="Refuse the risk",
                        style="secondary",
                        outcome=_outcome(
                            title="Trust Left Unanswered",
                            description=(
                                "You step away even after the door opened for you. They do not curse you. Somehow that silence is worse."
                            ),
                            event_type="flavor",
                            xp_profile="special_base",
                            reputation_change=-2,
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_special_crooked_offer",
        title="Crooked Offer in the Smoke",
        flow_type="single_choice",
        initial_step_id="step_one",
        max_rep=-21,
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The wrong kind of name opens the wrong kind of door",
                description=(
                    "A back-room runner flags you down because your reputation says you might hear the rest of the sentence instead of spitting in his face. "
                    "There is a score on the table, but none of it comes clean."
                ),
                options=(
                    _option(
                        key="rob_cut",
                        label="Take the mean cut",
                        style="danger",
                        outcome=_outcome(
                            title="You Walk Off with the Mean Cut",
                            description=(
                                "You take the ugliest part of the score because it pays the fastest. Nobody involved mistakes you for decent after, least of all you."
                            ),
                            event_type="reward",
                            xp_profile="special_high",
                            reputation_change=-5,
                        ),
                    ),
                    _option(
                        key="sell_name",
                        label="Sell a name for supper",
                        style="primary",
                        outcome=_outcome(
                            title="A Name Sold for Supper",
                            description=(
                                "You give up the name they want and take the payment before conscience has time to get loud. The district will eat what is left of that choice later."
                            ),
                            event_type="choice",
                            xp_profile="special_base",
                            reputation_change=-5,
                        ),
                    ),
                    _option(
                        key="back_off",
                        label="Back off anyway",
                        style="secondary",
                        outcome=_outcome(
                            title="Even You Know Better Tonight",
                            description=(
                                "You walk away from the offer before it can stain you deeper. In a place like this, even a bad name sometimes finds one line it still refuses to cross."
                            ),
                            event_type="flavor",
                            xp_profile="special_base",
                        ),
                    ),
                ),
            ),
        ),
    ),
)

LEGACY_GENERIC_APPROACHES = (
    ExploreApproachDefinition(
        key="cautious_search",
        label="Cautious Search",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=40, combat=30, choice=20, flavor=10),
        menu_description="Legacy exploration option.",
        intro_text="You move carefully, listening for every shift in the spiritual air.",
    ),
    ExploreApproachDefinition(
        key="standard_patrol",
        label="Standard Patrol",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=40, combat=30, choice=20, flavor=10),
        menu_description="Legacy exploration option.",
        intro_text="You patrol with steady purpose, ready for whatever Rukongai throws at you.",
    ),
    ExploreApproachDefinition(
        key="risky_push",
        label="Risky Push",
        duration_minutes=4,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=40, combat=30, choice=20, flavor=10),
        menu_description="Legacy exploration option.",
        intro_text="You push deeper into danger, chasing growth through pressure and risk.",
    ),
)

LOCATION_EXPLORATION_DEFINITIONS = {
    "rukongai_streets": LocationExploreDefinition(
        location_key="rukongai_streets",
        menu_title="Rukongai Streets",
        menu_description=(
            "The streets never hand you anything. Choose what you are hunting, decide how long you are willing to stay out, and see what kind of answer Rukongai gives you."
        ),
        menu_footer='"If miracles only happen once, what are they called the second time?"',
        approach_pool=RUKONGAI_STREETS_APPROACHES,
        event_pool=RUKONGAI_STREETS_EVENTS,
        single_choice_events=RUKONGAI_STREETS_SINGLE_CHOICE_EVENTS,
        multi_step_events=RUKONGAI_STREETS_MULTI_STEP_EVENTS,
        special_offer_templates=RUKONGAI_STREETS_SPECIAL_OFFERS,
        special_events=RUKONGAI_STREETS_SPECIAL_EVENTS,
    ),
}

EXPLORE_APPROACHES = {
    approach.key: approach
    for approach in (
        *LEGACY_GENERIC_APPROACHES,
        *LEGACY_RUKONGAI_STREETS_APPROACHES,
        *(
            approach
            for location_definition in LOCATION_EXPLORATION_DEFINITIONS.values()
            for approach in location_definition.approach_pool
        ),
    )
}


def get_explore_approach(approach_key: str) -> ExploreApproachDefinition:
    try:
        return EXPLORE_APPROACHES[approach_key]
    except KeyError as error:
        raise ValueError(f"Unknown explore approach: {approach_key}") from error


def get_location_exploration_definition(location_key: str) -> LocationExploreDefinition:
    try:
        return LOCATION_EXPLORATION_DEFINITIONS[location_key]
    except KeyError as error:
        raise ValueError(f"Unknown exploration location: {location_key}") from error


def get_location_event_pool(location_key: str) -> LocationEventPool:
    return get_location_exploration_definition(location_key).event_pool


def get_location_approach_pool(location_key: str) -> tuple[ExploreApproachDefinition, ...]:
    return get_location_exploration_definition(location_key).approach_pool


def list_explore_focuses_for_location(location_key: str) -> tuple[ExploreFocusDefinition, ...]:
    if location_key == "rukongai_streets":
        return RUKONGAI_EXPLORE_FOCUSES
    return ()


def list_explore_durations() -> tuple[ExploreDurationDefinition, ...]:
    return RUKONGAI_EXPLORE_DURATIONS


def build_explore_approach_key(location_key: str, focus_key: str, duration_key: str) -> str:
    if location_key == "rukongai_streets":
        return f"rukongai_{focus_key}_{duration_key}"
    raise ValueError(f"Unsupported exploration location for focus selection: {location_key}")


def get_random_explore_options_for_location(
    location_key: str,
    *,
    count: int = 3,
) -> tuple[ExploreApproachDefinition, ...]:
    approach_pool = get_location_approach_pool(location_key)
    if count == 3:
        duration_buckets: dict[int, list[ExploreApproachDefinition]] = {}
        for approach in approach_pool:
            duration_buckets.setdefault(approach.duration_minutes, []).append(approach)

        required_durations = (2, 3, 5)
        if all(duration_buckets.get(duration) for duration in required_durations):
            selected = [
                random.choice(duration_buckets[duration])
                for duration in required_durations
            ]
            return tuple(selected)

    sample_size = min(count, len(approach_pool))
    return tuple(random.sample(approach_pool, k=sample_size))


def get_random_decision_event(
    location_key: str,
    flow_type: Literal["single_choice", "multi_step"],
    *,
    reputation_value: int | None = None,
) -> ExplorationDecisionEventDefinition:
    location_definition = get_location_exploration_definition(location_key)
    pool = (
        location_definition.single_choice_events
        if flow_type == "single_choice"
        else location_definition.multi_step_events
    )
    eligible_pool = tuple(
        event
        for event in pool
        if (event.min_rep is None or reputation_value is None or reputation_value >= event.min_rep)
        and (event.max_rep is None or reputation_value is None or reputation_value <= event.max_rep)
    )
    return random.choice(eligible_pool or pool)


def get_random_special_offer_template(location_key: str) -> ExplorationEventTemplate:
    location_definition = get_location_exploration_definition(location_key)
    return random.choice(location_definition.special_offer_templates)


def get_random_special_event(
    location_key: str,
    *,
    reputation_value: int | None = None,
) -> ExplorationDecisionEventDefinition:
    location_definition = get_location_exploration_definition(location_key)
    eligible_pool = tuple(
        event
        for event in location_definition.special_events
        if (event.min_rep is None or reputation_value is None or reputation_value >= event.min_rep)
        and (event.max_rep is None or reputation_value is None or reputation_value <= event.max_rep)
    )
    return random.choice(eligible_pool or location_definition.special_events)


def get_decision_event_definition(
    location_key: str,
    event_key: str,
) -> ExplorationDecisionEventDefinition:
    location_definition = get_location_exploration_definition(location_key)
    for event in (
        *location_definition.single_choice_events,
        *location_definition.multi_step_events,
        *location_definition.special_events,
    ):
        if event.key == event_key:
            return event

    raise ValueError(f"Unknown exploration decision event: {location_key}:{event_key}")


def get_decision_step_definition(
    event: ExplorationDecisionEventDefinition,
    step_key: str,
) -> ExplorationDecisionStepDefinition:
    for step in event.steps:
        if step.key == step_key:
            return step

    raise ValueError(f"Unknown exploration decision step: {event.key}:{step_key}")
