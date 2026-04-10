from __future__ import annotations

from dataclasses import dataclass

from src.data.items import BANDAGES, ItemDefinition


@dataclass(frozen=True, slots=True)
class ShopListingDefinition:
    key: str
    item: ItemDefinition
    base_price: int
    flavor_text: str


RUKONGAI_MARKET_LISTINGS: tuple[ShopListingDefinition, ...] = (
    ShopListingDefinition(
        key="bandages",
        item=BANDAGES,
        base_price=100,
        flavor_text="Clean enough to matter. In Rukongai, that already makes them valuable.",
    ),
)


SHOP_LISTING_MAP = {listing.key: listing for listing in RUKONGAI_MARKET_LISTINGS}


def get_market_listings() -> tuple[ShopListingDefinition, ...]:
    return RUKONGAI_MARKET_LISTINGS


def get_shop_listing(listing_key: str) -> ShopListingDefinition:
    try:
        return SHOP_LISTING_MAP[listing_key]
    except KeyError as error:
        raise ValueError(f"Unknown shop listing: {listing_key}") from error
