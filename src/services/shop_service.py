from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncpg import Pool

from src.data.items import get_item_definition
from src.data.locations import RUKONGAI_MARKET
from src.data.shop import ShopListingDefinition, get_market_listings, get_shop_listing
from src.models.inventory import PlayerInventoryItem
from src.models.player import PlayerProfile
from src.services.effect_service import (
    apply_shop_discount_effect,
    get_shop_discount_pct,
    list_active_player_effects_for_connection,
)
from src.services.inventory_service import (
    grant_inventory_item_for_connection,
    list_player_inventory_for_connection,
)
from src.services.player_service import get_or_sync_player_record, update_player_record
from src.services.reputation_service import (
    apply_rep_shop_price,
    get_location_reputation_title,
    get_location_reputation_value,
    get_reputation_modifiers,
)


@dataclass(frozen=True, slots=True)
class ShopListingViewData:
    listing: ShopListingDefinition
    final_price: int
    reputation_price: int
    reputation_modifier_pct: int
    effect_discount_pct: int
    owned_quantity: int


@dataclass(slots=True)
class ShopSessionData:
    player: PlayerProfile
    listings: tuple[ShopListingViewData, ...]
    reputation_title: str


@dataclass(slots=True)
class PurchaseResult:
    status: Literal["purchased", "missing_profile", "wrong_location", "missing_listing", "insufficient_kan"]
    player: PlayerProfile | None = None
    listing: ShopListingViewData | None = None
    purchased_item: PlayerInventoryItem | None = None


def _count_owned_quantity(items: list[PlayerInventoryItem], item_key: str) -> int:
    return sum(item.quantity for item in items if item.item_key == item_key)


def _build_listing_view_data(
    *,
    player: PlayerProfile,
    listing: ShopListingDefinition,
    owned_quantity: int,
    effect_discount_pct: int,
) -> ShopListingViewData:
    reputation_value = get_location_reputation_value(player, player.location)
    reputation_price = apply_rep_shop_price(listing.base_price, reputation_value)
    final_price = apply_shop_discount_effect(
        reputation_price,
        [
            effect
            for effect in []
        ],
    )
    # The effect-adjusted price is set by the caller with the active effect snapshot.
    return ShopListingViewData(
        listing=listing,
        final_price=final_price,
        reputation_price=reputation_price,
        reputation_modifier_pct=int(get_reputation_modifiers(reputation_value)["shop_price_modifier"]),
        effect_discount_pct=effect_discount_pct,
        owned_quantity=owned_quantity,
    )


async def get_shop_session_data(pool: Pool | None, user_id: int) -> ShopSessionData | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        player_sync = await get_or_sync_player_record(connection, user_id)
        if player_sync is None:
            return None

        player = PlayerProfile.from_record(player_sync.record)
        inventory_items = await list_player_inventory_for_connection(connection, user_id)
        active_effects = await list_active_player_effects_for_connection(connection, user_id)
        effect_discount_pct = get_shop_discount_pct(active_effects)
        reputation_value = get_location_reputation_value(player, player.location)
        reputation_title = get_location_reputation_title(player, player.location)
        reputation_modifier_pct = int(get_reputation_modifiers(reputation_value)["shop_price_modifier"])

        listings: list[ShopListingViewData] = []
        for listing in get_market_listings():
            owned_quantity = _count_owned_quantity(inventory_items, listing.item.key)
            reputation_price = apply_rep_shop_price(listing.base_price, reputation_value)
            final_price = apply_shop_discount_effect(reputation_price, active_effects)
            listings.append(
                ShopListingViewData(
                    listing=listing,
                    final_price=final_price,
                    reputation_price=reputation_price,
                    reputation_modifier_pct=reputation_modifier_pct,
                    effect_discount_pct=effect_discount_pct,
                    owned_quantity=owned_quantity,
                )
            )

        return ShopSessionData(
            player=player,
            listings=tuple(listings),
            reputation_title=reputation_title,
        )


async def purchase_shop_listing(
    pool: Pool | None,
    *,
    user_id: int,
    listing_key: str,
) -> PurchaseResult:
    if pool is None:
        return PurchaseResult(status="missing_profile")

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return PurchaseResult(status="missing_profile")

            player = PlayerProfile.from_record(player_sync.record)
            if player.location != RUKONGAI_MARKET.key:
                return PurchaseResult(status="wrong_location", player=player)

            try:
                listing = get_shop_listing(listing_key)
            except ValueError:
                return PurchaseResult(status="missing_listing", player=player)

            inventory_items = await list_player_inventory_for_connection(connection, user_id, for_update=True)
            active_effects = await list_active_player_effects_for_connection(connection, user_id, for_update=True)
            reputation_value = get_location_reputation_value(player, player.location)
            reputation_modifier_pct = int(get_reputation_modifiers(reputation_value)["shop_price_modifier"])
            effect_discount_pct = get_shop_discount_pct(active_effects)
            reputation_price = apply_rep_shop_price(listing.base_price, reputation_value)
            final_price = apply_shop_discount_effect(reputation_price, active_effects)
            owned_quantity = _count_owned_quantity(inventory_items, listing.item.key)
            listing_view = ShopListingViewData(
                listing=listing,
                final_price=final_price,
                reputation_price=reputation_price,
                reputation_modifier_pct=reputation_modifier_pct,
                effect_discount_pct=effect_discount_pct,
                owned_quantity=owned_quantity,
            )

            if player.kan < final_price:
                return PurchaseResult(
                    status="insufficient_kan",
                    player=player,
                    listing=listing_view,
                )

            purchased_item = await grant_inventory_item_for_connection(
                connection,
                user_id=user_id,
                item_key=listing.item.key,
                item_name=listing.item.name,
                quantity=1,
                item_description=listing.item.description,
                item_type=listing.item.item_type,
                rarity=listing.item.rarity,
                stackable=listing.item.stackable,
                source_text="Rukongai Market",
            )
            updated_record = await update_player_record(
                connection,
                user_id,
                {
                    "kan": player.kan - final_price,
                },
            )
            updated_player = PlayerProfile.from_record(updated_record)
            updated_listing = ShopListingViewData(
                listing=listing,
                final_price=final_price,
                reputation_price=reputation_price,
                reputation_modifier_pct=reputation_modifier_pct,
                effect_discount_pct=effect_discount_pct,
                owned_quantity=purchased_item.quantity,
            )
            return PurchaseResult(
                status="purchased",
                player=updated_player,
                listing=updated_listing,
                purchased_item=purchased_item,
            )
