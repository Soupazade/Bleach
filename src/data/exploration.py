from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Literal


ExploreEventType = Literal["reward", "combat", "choice", "flavor"]


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
        event_biases=_biases(reward=46, combat=16, choice=18, flavor=20),
        menu_description="Low risk. Quick scavenging through the leftovers.",
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

RUKONGAI_STREETS_EVENTS = LocationEventPool(
    reward_events=(
        ExplorationEventTemplate(
            title="Scrap Luck",
            description=(
                "During **{approach}**, you turn up a knot of salvage tucked beneath rotting boards. "
                "It is not much, but in Rukongai even a fistful of scraps feels like a victory."
            ),
        ),
        ExplorationEventTemplate(
            title="A Kind Hand in a Hard Place",
            description=(
                "While moving through **{approach}**, an exhausted soul repays your decency with a wrapped ration and a useful lead. "
                "Brief kindness still survives in these streets."
            ),
        ),
        ExplorationEventTemplate(
            title="Market Edge Score",
            description=(
                "Your **{approach}** pays off near the market fringe. After the shouting dies down, you collect what others were too tired or too scared to fight over."
            ),
        ),
        ExplorationEventTemplate(
            title="Rumor Turned Reward",
            description=(
                "A rumor tied to **{approach}** leads you to a hidden cache behind split stone and damp cloth. "
                "For once, the whispers were worth following."
            ),
        ),
    ),
    combat_events=(
        ExplorationEventTemplate(
            title="Alley Ambush",
            description=(
                "The path opened by **{approach}** draws you into a narrow alley where hungry eyes and bad intent were already waiting."
            ),
        ),
        ExplorationEventTemplate(
            title="Weak Hollow Stirring",
            description=(
                "A thin spiritual shriek cuts through your **{approach}** as a weak hollow lashes out from the wreckage between homes."
            ),
        ),
        ExplorationEventTemplate(
            title="Gang Pressure",
            description=(
                "Your **{approach}** carries you into a block claimed by local toughs. They read your presence as a challenge and move first."
            ),
        ),
        ExplorationEventTemplate(
            title="Corner Turned Violent",
            description=(
                "What began as **{approach}** turns sharp when a desperate soul mistakes resolve for weakness and tries to take what little you have."
            ),
        ),
    ),
    choice_events=(
        ExplorationEventTemplate(
            title="A Whisper Worth Chasing",
            description=(
                "In the middle of **{approach}**, you catch a thread of rumor about a safer route, a hidden stash, and a gang collecting debts. "
                "You choose the lead that feels most alive."
            ),
        ),
        ExplorationEventTemplate(
            title="Need Versus Opportunity",
            description=(
                "**{approach}** puts you between a starving stranger and a risky opening elsewhere in the district. "
                "Whatever you choose, Rukongai makes sure you remember it."
            ),
        ),
        ExplorationEventTemplate(
            title="The Street Tests Your Instincts",
            description=(
                "A knot of frightened souls breaks around your **{approach}**, revealing two bad options and one narrow chance. "
                "You trust your judgment and move."
            ),
        ),
        ExplorationEventTemplate(
            title="A Lead in the Dust",
            description=(
                "The trail created by **{approach}** leaves you with a small decision: follow the noise, guard what you found, or disappear before the street notices. "
                "You read the moment right."
            ),
        ),
    ),
    flavor_events=(
        ExplorationEventTemplate(
            title="Another Night in Rukongai",
            description=(
                "**{approach}** brings no prize this time. You pass smoke, patched roofs, and tired faces, and learn again how survival sets the rhythm here."
            ),
        ),
        ExplorationEventTemplate(
            title="Hunger in the Air",
            description=(
                "There is no clean reward waiting at the end of **{approach}**. Just thin soup, low voices, and the heavy truth that most souls here are one bad day from breaking."
            ),
        ),
        ExplorationEventTemplate(
            title="Small Mercy, Small Hope",
            description=(
                "Your **{approach}** ends with nothing to claim, only the sight of neighbors sharing what little they have. "
                "In a place this hard, even that feels meaningful."
            ),
        ),
        ExplorationEventTemplate(
            title="The District Watches Back",
            description=(
                "By the end of **{approach}**, the alleys have given you nothing but scraped nerves and sharper awareness. "
                "Sometimes surviving the block is the whole result."
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
            "Nothing comes easy in these streets. Pick your next move carefully and chase a small edge before the district swallows the chance."
        ),
        menu_footer='"If miracles only happen once, what are they called the second time?"',
        approach_pool=RUKONGAI_STREETS_APPROACHES,
        event_pool=RUKONGAI_STREETS_EVENTS,
    ),
}

EXPLORE_APPROACHES = {
    approach.key: approach
    for approach in (
        *LEGACY_GENERIC_APPROACHES,
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
            random.shuffle(selected)
            return tuple(selected)

    sample_size = min(count, len(approach_pool))
    return tuple(random.sample(approach_pool, k=sample_size))
