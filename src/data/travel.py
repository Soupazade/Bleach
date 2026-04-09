from __future__ import annotations

from dataclasses import dataclass

from src.data.locations import (
    RUKONGAI_MARKET,
    RUKONGAI_OUTSKIRTS,
    RUKONGAI_STREETS,
    RUKONGAI_TRAINING_YARD,
)


@dataclass(frozen=True, slots=True)
class TravelRouteDefinition:
    source: str
    destination: str
    duration_minutes: int
    stamina_cost: int
    label: str
    dropdown_label: str
    description: str


# Early Rukongai travel is meant to feel lighter than exploration.
# Keep routes short and stamina costs modest so movement matters without becoming a chore.
RUKONGAI_TRAVEL_ROUTES = (
    TravelRouteDefinition(
        source=RUKONGAI_STREETS.key,
        destination=RUKONGAI_MARKET.key,
        duration_minutes=1,
        stamina_cost=4,
        label="Head to the market",
        dropdown_label="Rukongai Market [1m]",
        description="Follow the noise and the hunger toward the market lanes.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_STREETS.key,
        destination=RUKONGAI_TRAINING_YARD.key,
        duration_minutes=2,
        stamina_cost=6,
        label="Make for the training yard",
        dropdown_label="Rukongai Training Yard [2m]",
        description="Cut across the district where restless souls go to harden themselves.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_STREETS.key,
        destination=RUKONGAI_OUTSKIRTS.key,
        duration_minutes=3,
        stamina_cost=8,
        label="Push toward the outskirts",
        dropdown_label="Rukongai Outskirts [3m]",
        description="Leave the denser blocks behind and drift toward rougher ground.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_MARKET.key,
        destination=RUKONGAI_STREETS.key,
        duration_minutes=1,
        stamina_cost=4,
        label="Slip back to the streets",
        dropdown_label="Rukongai Streets [1m]",
        description="Step away from the crowds and return to the main street flow.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_MARKET.key,
        destination=RUKONGAI_TRAINING_YARD.key,
        duration_minutes=2,
        stamina_cost=6,
        label="Leave the stalls for the yard",
        dropdown_label="Rukongai Training Yard [2m]",
        description="Trade market noise for the open strain of the training ground.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_MARKET.key,
        destination=RUKONGAI_OUTSKIRTS.key,
        duration_minutes=3,
        stamina_cost=8,
        label="Work your way out to the outskirts",
        dropdown_label="Rukongai Outskirts [3m]",
        description="Follow the thinner trade lines until the district starts to fray.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_TRAINING_YARD.key,
        destination=RUKONGAI_STREETS.key,
        duration_minutes=2,
        stamina_cost=6,
        label="Return to the streets",
        dropdown_label="Rukongai Streets [2m]",
        description="Leave the yard and head back into the crowded blocks.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_TRAINING_YARD.key,
        destination=RUKONGAI_MARKET.key,
        duration_minutes=2,
        stamina_cost=6,
        label="Cut across to the market",
        dropdown_label="Rukongai Market [2m]",
        description="Trade bruises and dust for the market's noise and barter.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_TRAINING_YARD.key,
        destination=RUKONGAI_OUTSKIRTS.key,
        duration_minutes=2,
        stamina_cost=6,
        label="Walk out toward the outskirts",
        dropdown_label="Rukongai Outskirts [2m]",
        description="Leave the practice ground and drift toward the edges of the district.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_OUTSKIRTS.key,
        destination=RUKONGAI_STREETS.key,
        duration_minutes=3,
        stamina_cost=8,
        label="Come back in from the outskirts",
        dropdown_label="Rukongai Streets [3m]",
        description="Work your way back from the district edge into denser streets.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_OUTSKIRTS.key,
        destination=RUKONGAI_MARKET.key,
        duration_minutes=3,
        stamina_cost=8,
        label="Follow the road to the market",
        dropdown_label="Rukongai Market [3m]",
        description="Follow the rough route back toward trade and noise.",
    ),
    TravelRouteDefinition(
        source=RUKONGAI_OUTSKIRTS.key,
        destination=RUKONGAI_TRAINING_YARD.key,
        duration_minutes=2,
        stamina_cost=6,
        label="Cut inward to the yard",
        dropdown_label="Rukongai Training Yard [2m]",
        description="Take the inward route where the district hardens itself.",
    ),
)


def get_travel_route(source_location: str, destination_location: str) -> TravelRouteDefinition:
    for route in RUKONGAI_TRAVEL_ROUTES:
        if route.source == source_location and route.destination == destination_location:
            return route

    raise ValueError(f"Unknown travel route: {source_location} -> {destination_location}")


def get_available_travel_routes(source_location: str) -> tuple[TravelRouteDefinition, ...]:
    routes = [route for route in RUKONGAI_TRAVEL_ROUTES if route.source == source_location]
    return tuple(sorted(routes, key=lambda route: (route.duration_minutes, route.destination)))
