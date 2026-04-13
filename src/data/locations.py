from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocationDefinition:
    key: str
    name: str
    room_id: int | None = None
    role_id: int | None = None
    room_name: str | None = None
    role_name: str | None = None


RUKONGAI_STREETS = LocationDefinition(
    key="rukongai_streets",
    name="Rukongai Streets",
    room_id=1491604332594860032,
    role_id=1491603816590872606,
    room_name="rukongai-streets",
    role_name="Rukongai Streets",
)

RUKONGAI_MARKET = LocationDefinition(
    key="rukongai_market",
    name="Rukongai Market",
    room_id=1491604383958306877,
    role_id=1491604030860824687,
    room_name="rukongai-market",
    role_name="Rukongai Market",
)

RUKONGAI_OUTSKIRTS = LocationDefinition(
    key="rukongai_outskirts",
    name="Rukongai Outskirts",
    room_id=1491604560303624263,
    role_id=1491604131855732949,
    room_name="rukongai-outskirts",
    role_name="Rukongai Outskirts",
)

RUKONGAI_TRAINING_YARD = LocationDefinition(
    key="rukongai_training_yard",
    name="Rukongai Training Yard",
    room_id=1491604605627273427,
    role_id=1491604211820003520,
    room_name="rukongai-training-yard",
    role_name="Rukongai Training Yard",
)

LOCATIONS = {
    RUKONGAI_STREETS.key: RUKONGAI_STREETS,
    RUKONGAI_MARKET.key: RUKONGAI_MARKET,
    RUKONGAI_OUTSKIRTS.key: RUKONGAI_OUTSKIRTS,
    RUKONGAI_TRAINING_YARD.key: RUKONGAI_TRAINING_YARD,
}


def get_location_definition(location_key: str) -> LocationDefinition:
    try:
        return LOCATIONS[location_key]
    except KeyError as error:
        raise ValueError(f"Unknown location key: {location_key}") from error
