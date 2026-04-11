from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncpg import Pool

from src.data.items import ItemDefinition, get_item_definition
from src.models.inventory import PlayerInventoryItem
from src.models.player import PlayerProfile
from src.services.inventory_service import (
    consume_inventory_item_for_connection,
    fetch_inventory_records,
    grant_inventory_item_for_connection,
)
from src.services.player_service import get_or_sync_player_record


@dataclass(frozen=True, slots=True)
class CraftRecipe:
    key: str
    label: str
    ingredient_item_key: str
    ingredient_quantity: int
    output_item_key: str
    output_quantity: int = 1


RATIO_PACK_RECIPE = CraftRecipe(
    key="ration_pack",
    label="Ration Pack",
    ingredient_item_key="food_scraps",
    ingredient_quantity=5,
    output_item_key="ration_pack",
)

BANDAGES_RECIPE = CraftRecipe(
    key="bandages",
    label="Bandages",
    ingredient_item_key="cloth_scraps",
    ingredient_quantity=5,
    output_item_key="bandages",
)


CRAFT_RECIPE_MAP: dict[str, CraftRecipe] = {
    RATIO_PACK_RECIPE.key: RATIO_PACK_RECIPE,
    BANDAGES_RECIPE.key: BANDAGES_RECIPE,
}


@dataclass(slots=True)
class CraftResult:
    status: Literal["crafted", "missing_profile", "invalid_recipe", "missing_ingredients"]
    player: PlayerProfile | None = None
    recipe: CraftRecipe | None = None
    ingredient_item: ItemDefinition | None = None
    output_item: ItemDefinition | None = None
    ingredient_owned: int = 0
    ingredient_remaining: int = 0
    crafted_item: PlayerInventoryItem | None = None


def list_craft_recipes() -> tuple[CraftRecipe, ...]:
    return tuple(CRAFT_RECIPE_MAP.values())


def get_craft_recipe(recipe_key: str) -> CraftRecipe:
    try:
        return CRAFT_RECIPE_MAP[recipe_key]
    except KeyError as error:
        raise ValueError(f"Unknown craft recipe: {recipe_key}") from error


async def craft_item(
    pool: Pool | None,
    *,
    user_id: int,
    recipe_key: str,
) -> CraftResult:
    if pool is None:
        return CraftResult(status="missing_profile")

    try:
        recipe = get_craft_recipe(recipe_key)
    except ValueError:
        return CraftResult(status="invalid_recipe")

    ingredient_item = get_item_definition(recipe.ingredient_item_key)
    output_item = get_item_definition(recipe.output_item_key)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return CraftResult(
                    status="missing_profile",
                    recipe=recipe,
                    ingredient_item=ingredient_item,
                    output_item=output_item,
                )

            player = PlayerProfile.from_record(player_sync.record)
            inventory_records = await fetch_inventory_records(connection, user_id, for_update=True)
            inventory_items = [PlayerInventoryItem.from_record(record) for record in inventory_records]
            ingredient_stack = next(
                (item for item in inventory_items if item.item_key == recipe.ingredient_item_key),
                None,
            )
            ingredient_owned = 0 if ingredient_stack is None else ingredient_stack.quantity
            if ingredient_owned < recipe.ingredient_quantity:
                return CraftResult(
                    status="missing_ingredients",
                    player=player,
                    recipe=recipe,
                    ingredient_item=ingredient_item,
                    output_item=output_item,
                    ingredient_owned=ingredient_owned,
                    ingredient_remaining=ingredient_owned,
                )

            consumed = await consume_inventory_item_for_connection(
                connection,
                user_id=user_id,
                item_key=recipe.ingredient_item_key,
                quantity=recipe.ingredient_quantity,
            )
            if consumed < recipe.ingredient_quantity:
                return CraftResult(
                    status="missing_ingredients",
                    player=player,
                    recipe=recipe,
                    ingredient_item=ingredient_item,
                    output_item=output_item,
                    ingredient_owned=ingredient_owned,
                    ingredient_remaining=max(0, ingredient_owned - consumed),
                )

            crafted_item = await grant_inventory_item_for_connection(
                connection,
                user_id=user_id,
                item_key=output_item.key,
                item_name=output_item.name,
                quantity=recipe.output_quantity,
                item_description=output_item.description,
                item_type=output_item.item_type,
                rarity=output_item.rarity,
                stackable=output_item.stackable,
                source_text="Crafted",
            )
            return CraftResult(
                status="crafted",
                player=player,
                recipe=recipe,
                ingredient_item=ingredient_item,
                output_item=output_item,
                ingredient_owned=ingredient_owned,
                ingredient_remaining=max(0, ingredient_owned - recipe.ingredient_quantity),
                crafted_item=crafted_item,
            )
