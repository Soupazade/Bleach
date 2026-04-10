from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ItemDefinition:
    key: str
    name: str
    description: str
    item_type: str
    rarity: str
    stackable: bool = True
    usable: bool = False
    use_out_of_combat_only: bool = False
    heal_hp_pct: int = 0


BANDAGES = ItemDefinition(
    key="bandages",
    name="Bandages",
    description="Clean wraps scavenged together well enough to keep blood loss from getting worse.",
    item_type="consumable",
    rarity="common",
    stackable=True,
    usable=True,
    use_out_of_combat_only=True,
    heal_hp_pct=25,
)


ITEM_DEFINITIONS: dict[str, ItemDefinition] = {
    BANDAGES.key: BANDAGES,
}


def get_item_definition(item_key: str) -> ItemDefinition:
    try:
        return ITEM_DEFINITIONS[item_key]
    except KeyError as error:
        raise ValueError(f"Unknown item definition: {item_key}") from error


def list_usable_items() -> tuple[ItemDefinition, ...]:
    return tuple(item for item in ITEM_DEFINITIONS.values() if item.usable)
