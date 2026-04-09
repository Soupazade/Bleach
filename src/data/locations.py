from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocationDefinition:
    key: str
    name: str
    room_id: int
    role_id: int


RUKONGAI_STREETS = LocationDefinition(
    key="rukongai_streets",
    name="Rukongai Streets",
    room_id=1491604332594860032,
    role_id=1491603816590872606,
)

LOCATIONS = {
    RUKONGAI_STREETS.key: RUKONGAI_STREETS,
}


def get_location_definition(location_key: str) -> LocationDefinition:
    try:
        return LOCATIONS[location_key]
    except KeyError as error:
        raise ValueError(f"Unknown location key: {location_key}") from error
