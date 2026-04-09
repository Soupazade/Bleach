from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExploreApproachDefinition:
    key: str
    name: str
    duration_minutes: int
    stamina_cost: int
    xp_min: int
    xp_max: int
    flavor: str


@dataclass(frozen=True, slots=True)
class LocationEventPool:
    reward_events: tuple[str, ...]
    combat_events: tuple[str, ...]
    choice_events: tuple[str, ...]
    flavor_events: tuple[str, ...]


CAUTIOUS_SEARCH = ExploreApproachDefinition(
    key="cautious_search",
    name="Cautious Search",
    duration_minutes=2,
    stamina_cost=10,
    xp_min=6,
    xp_max=10,
    flavor="You move carefully, listening for every shift in the spiritual air.",
)

STANDARD_PATROL = ExploreApproachDefinition(
    key="standard_patrol",
    name="Standard Patrol",
    duration_minutes=3,
    stamina_cost=10,
    xp_min=10,
    xp_max=15,
    flavor="You patrol with steady purpose, ready for whatever Rukongai throws at you.",
)

RISKY_PUSH = ExploreApproachDefinition(
    key="risky_push",
    name="Risky Push",
    duration_minutes=4,
    stamina_cost=10,
    xp_min=15,
    xp_max=25,
    flavor="You push deeper into danger, chasing growth through pressure and risk.",
)

EXPLORE_APPROACHES = {
    CAUTIOUS_SEARCH.key: CAUTIOUS_SEARCH,
    STANDARD_PATROL.key: STANDARD_PATROL,
    RISKY_PUSH.key: RISKY_PUSH,
}

RUKONGAI_STREETS_EVENTS = LocationEventPool(
    reward_events=(
        "A wandering spirit points you toward a hidden stash of supplies buried beneath shattered wood.",
        "You discover a quiet rooftop where lost charms and coins have collected beneath the evening wind.",
        "A grateful soul rewards your help with a little knowledge and a little luck.",
    ),
    combat_events=(
        "A hostile presence stirs in the alleys, forcing you into a sudden clash.",
        "A violent soul lunges from the crowd and tests your nerve in the Rukongai haze.",
        "The pressure in the district spikes as a rough encounter finds you first.",
    ),
    choice_events=(
        "At a fork between lantern-lit alleys, your instincts guide you toward the path with the strongest spiritual trace.",
        "A whisper in the crowd draws you toward a side street where opportunity and danger mix together.",
        "A drifting rumor leads you into a tense corner of the district where one decision changes the tone of your patrol.",
    ),
    flavor_events=(
        "For a while, the streets are quiet. You walk beneath old lantern light and let your soul settle into the city.",
        "You catch fragments of distant laughter and steel your resolve, learning the rhythm of life in Rukongai.",
        "Nothing major happens, but every step teaches you how this district breathes.",
    ),
)

LOCATION_EVENT_POOLS = {
    "rukongai_streets": RUKONGAI_STREETS_EVENTS,
}


def get_explore_approach(approach_key: str) -> ExploreApproachDefinition:
    try:
        return EXPLORE_APPROACHES[approach_key]
    except KeyError as error:
        raise ValueError(f"Unknown explore approach: {approach_key}") from error


def get_location_event_pool(location_key: str) -> LocationEventPool:
    try:
        return LOCATION_EVENT_POOLS[location_key]
    except KeyError as error:
        raise ValueError(f"Unknown exploration location: {location_key}") from error
