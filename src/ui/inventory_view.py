from __future__ import annotations

import discord

from src.models.inventory import PlayerInventoryItem
from src.models.player import PlayerProfile
from src.services.reputation_service import get_location_reputation_label, get_location_reputation_title
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color


def _format_inventory_entry(item: PlayerInventoryItem) -> str:
    detail_bits = [
        f"Type: {item.item_type.replace('_', ' ').title()}",
        f"Rarity: {item.rarity.replace('_', ' ').title()}",
    ]
    if item.source_text:
        detail_bits.append(f"Source: {item.source_text}")

    lines = [f"**x{item.quantity} {item.item_name}**"]
    if item.item_description:
        lines.append(item.item_description)
    lines.append(" | ".join(detail_bits))
    return "\n".join(lines)


def build_inventory_missing_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎒 No Soul Record Found",
        description="You need to use `/start` before you can keep anything worth carrying.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    embed.set_footer(text="Empty hands come before a real inventory.")
    return embed


def build_inventory_unavailable_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎒 Inventory Unavailable",
        description="The archive shelves are out of reach right now. Give the records a moment to settle.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    embed.set_footer(text="What you carry is still there. I just cannot open the record yet.")
    return embed


def build_inventory_embed(
    *,
    player: PlayerProfile,
    discord_user: discord.abc.User,
    items: list[PlayerInventoryItem],
) -> discord.Embed:
    reputation_label = get_location_reputation_label(player.location)
    reputation_title = get_location_reputation_title(player, player.location)
    total_quantity = sum(item.quantity for item in items)

    embed = discord.Embed(
        title="🎒 Soul Record — Inventory",
        description=(
            "Everything you managed to keep, hide, or drag out of the district ends up here. "
            "It is not much yet, but even scraps matter in Rukongai."
        ),
        color=get_explore_color("explore"),
    )
    embed.set_author(
        name=discord_user.display_name,
        icon_url=discord_user.display_avatar.url,
    )
    embed.set_thumbnail(url=discord_user.display_avatar.url)
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"📍 Location: {player.location_data.name}",
            f"📈 Level: {player.level}",
            f"🎭 {reputation_label}: {reputation_title}",
            f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Inventory Overview",
        value=build_explore_info_lines(
            f"🎒 Item Stacks: {len(items)}",
            f"📦 Total Quantity: {total_quantity}",
            "More item systems can plug into this cleanly later.",
        ),
        inline=False,
    )
    add_explore_divider(embed)

    if not items:
        embed.add_field(
            name="What You're Carrying",
            value=(
                "Nothing yet.\n"
                "Once explore drops, shops, NPC rewards, and future systems start handing out real items, "
                "they will be stored here."
            ),
            inline=False,
        )
        embed.set_footer(text="Even an empty bag matters once the streets start paying out.")
        return embed

    preview_items = items[:10]
    embed.add_field(
        name="What You're Carrying",
        value="\n\n".join(_format_inventory_entry(item) for item in preview_items),
        inline=False,
    )
    remaining_items = len(items) - len(preview_items)
    if remaining_items > 0:
        embed.add_field(
            name="More",
            value=f"And {remaining_items} more stack(s) are packed into the record.",
            inline=False,
        )
    embed.set_footer(text="What survives the streets has value, even before the systems around it grow.")
    return embed
