from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from src.data.locations import RUKONGAI_MARKET
from src.services.location_service import format_location_room_reference
from src.services.shop_service import PurchaseResult, ShopSessionData, ShopListingViewData, get_shop_session_data, purchase_shop_listing
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color

if TYPE_CHECKING:
    from src.main import BleachBot


def _format_price_line(listing: ShopListingViewData) -> str:
    parts = [f"💰 Price: **{listing.final_price} Kan**"]
    if listing.reputation_modifier_pct != 0:
        parts.append(f"🎭 Rep: {listing.reputation_modifier_pct:+d}%")
    if listing.effect_discount_pct > 0:
        parts.append(f"✨ Discount: -{listing.effect_discount_pct}%")
    return " | ".join(parts)


def build_shop_unavailable_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🏪 Shop Unavailable",
        description="The market ledgers are out of reach right now. Give the stalls a moment to settle.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    return embed


def build_shop_missing_profile_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🏪 No Soul Record Found",
        description="Use `/start` before you try to buy anything in Rukongai.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    return embed


def build_shop_market_required_embed(current_location_name: str | None = None) -> discord.Embed:
    description = (
        "If you want to buy anything worth carrying, head to the market and open the stalls there."
    )
    if current_location_name is not None:
        description = (
            f"You're currently tied to **{current_location_name}**. "
            "Head to the market before you try to buy anything."
        )

    embed = discord.Embed(
        title="🏪 Market Only",
        description=description,
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Market: {RUKONGAI_MARKET.name}",
            f"🕓 Correct Room: {format_location_room_reference(RUKONGAI_MARKET)}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_shop_embed(session: ShopSessionData) -> discord.Embed:
    player = session.player
    embed = discord.Embed(
        title="🏪 Rukongai Market — Shop",
        description=(
            "The market never really quiets down. Hungry voices, rough hands, and quick trades keep the whole place breathing."
        ),
        color=get_explore_color("explore"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Location: {player.location_data.name}",
            f"💰 Kan: {player.kan}",
            f"🎭 Reputation: {session.reputation_title}",
            f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
        ),
        inline=False,
    )
    embed.add_field(
        name="What Are They Selling?",
        value="Pick through the stall stock below.",
        inline=False,
    )
    add_explore_divider(embed)

    for listing in session.listings:
        embed.add_field(
            name=f"🩹 {listing.listing.item.name}",
            value=build_explore_info_lines(
                listing.listing.item.description,
                listing.listing.flavor_text,
                _format_price_line(listing),
                f"🎒 Owned: {listing.owned_quantity}",
            ),
            inline=False,
        )

    embed.set_footer(text="Every clean supply in Rukongai has a price on it.")
    return embed


def build_shop_purchase_embed(result: PurchaseResult) -> discord.Embed:
    player = result.player
    listing = result.listing
    assert player is not None
    assert listing is not None

    embed = discord.Embed(
        title="🟩 Purchase Made",
        description=(
            f"You pay the stall and take **{listing.listing.item.name}** before somebody else reaches for it."
        ),
        color=get_explore_color("reward"),
    )
    embed.add_field(
        name="What Changed",
        value=build_explore_info_lines(
            f"🎒 Bought: {listing.listing.item.name} x1",
            f"💰 Spent: {listing.final_price} Kan",
            f"💰 Remaining: {player.kan} Kan",
            f"🎒 Owned Now: {listing.owned_quantity}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    embed.set_footer(text="Some days the smartest thing you can buy is the chance to stay standing.")
    return embed


def build_shop_insufficient_kan_embed(result: PurchaseResult) -> discord.Embed:
    player = result.player
    listing = result.listing
    assert player is not None
    assert listing is not None

    embed = discord.Embed(
        title="🏪 Not Enough Kan",
        description="The stall keeper does not even look offended. In this market, empty hands are normal.",
        color=get_explore_color("combat"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"💰 Your Kan: {player.kan}",
            f"💰 Needed: {listing.final_price}",
            f"🎒 Item: {listing.listing.item.name}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


class BuyBandagesButton(discord.ui.Button["ShopView"]):
    def __init__(self, price: int) -> None:
        super().__init__(
            label=f"Buy Bandages — {price} Kan",
            style=discord.ButtonStyle.success,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.buy_bandages(interaction)


class RefreshShopButton(discord.ui.Button["ShopView"]):
    def __init__(self) -> None:
        super().__init__(
            label="Refresh Stock",
            style=discord.ButtonStyle.secondary,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.refresh(interaction)


class ShopView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BleachBot",
        owner_id: int,
        session: ShopSessionData,
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.session = session
        self.message: discord.Message | None = None
        bandages_listing = next(
            listing for listing in session.listings if listing.listing.key == "bandages"
        )
        self.buy_bandages_button = BuyBandagesButton(bandages_listing.final_price)
        self.refresh_button = RefreshShopButton()
        self.add_item(self.buy_bandages_button)
        self.add_item(self.refresh_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "This shop prompt belongs to another player. Use `/shop` to open your own.",
            ephemeral=True,
        )
        return False

    async def _reload_session(self) -> ShopSessionData | None:
        session = await get_shop_session_data(self.bot.db_pool, self.owner_id)
        if session is None:
            return None
        self.session = session
        for child in list(self.children):
            self.remove_item(child)
        bandages_listing = next(
            listing for listing in session.listings if listing.listing.key == "bandages"
        )
        self.buy_bandages_button = BuyBandagesButton(bandages_listing.final_price)
        self.refresh_button = RefreshShopButton()
        self.add_item(self.buy_bandages_button)
        self.add_item(self.refresh_button)
        return session

    async def refresh(self, interaction: discord.Interaction) -> None:
        session = await self._reload_session()
        if session is None:
            self.stop()
            await interaction.response.edit_message(
                embed=build_shop_unavailable_embed(),
                view=None,
            )
            return
        await interaction.response.edit_message(
            embed=build_shop_embed(session),
            view=self,
        )

    async def buy_bandages(self, interaction: discord.Interaction) -> None:
        result = await purchase_shop_listing(
            self.bot.db_pool,
            user_id=self.owner_id,
            listing_key="bandages",
        )

        if result.status == "purchased":
            session = await self._reload_session()
            await interaction.response.edit_message(
                embed=build_shop_embed(session or self.session),
                view=self if session is not None else None,
            )
            await interaction.followup.send(
                embed=build_shop_purchase_embed(result),
                ephemeral=True,
            )
            return

        if result.status == "insufficient_kan":
            await interaction.response.send_message(
                embed=build_shop_insufficient_kan_embed(result),
                ephemeral=True,
            )
            return

        if result.status == "wrong_location":
            self.stop()
            await interaction.response.edit_message(
                embed=build_shop_market_required_embed(
                    result.player.location_data.name if result.player is not None else None
                ),
                view=None,
            )
            return

        self.stop()
        await interaction.response.edit_message(
            embed=build_shop_unavailable_embed(),
            view=None,
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
