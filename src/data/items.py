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
    restore_stamina_flat: int = 0


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

CLOTH_SCRAPS = ItemDefinition(
    key="cloth_scraps",
    name="Cloth Scraps",
    description="Worn fabric with just enough life left to trade, patch, or repurpose.",
    item_type="material",
    rarity="common",
    stackable=True,
)

FOOD_SCRAPS = ItemDefinition(
    key="food_scraps",
    name="Food Scraps",
    description="A rough collection of edible leftovers. Not dignified, but still worth something.",
    item_type="material",
    rarity="common",
    stackable=True,
)

RATION_PACK = ItemDefinition(
    key="ration_pack",
    name="Ration Pack",
    description="A tightly bundled meal put together from whatever could be salvaged and kept edible.",
    item_type="supply",
    rarity="common",
    stackable=True,
    usable=True,
    use_out_of_combat_only=True,
    restore_stamina_flat=10,
)


ITEM_DEFINITIONS: dict[str, ItemDefinition] = {
    BANDAGES.key: BANDAGES,
    CLOTH_SCRAPS.key: CLOTH_SCRAPS,
    FOOD_SCRAPS.key: FOOD_SCRAPS,
    RATION_PACK.key: RATION_PACK,
}


def get_item_definition(item_key: str) -> ItemDefinition:
    try:
        return ITEM_DEFINITIONS[item_key]
    except KeyError as error:
        raise ValueError(f"Unknown item definition: {item_key}") from error


def list_usable_items() -> tuple[ItemDefinition, ...]:
    return tuple(item for item in ITEM_DEFINITIONS.values() if item.usable)
