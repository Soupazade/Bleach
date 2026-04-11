from __future__ import annotations

import discord

from src.data.items import ItemDefinition
from src.models.inventory import PlayerInventoryItem
from src.models.player import PlayerProfile
from src.services.reputation_service import get_location_reputation_label, get_location_reputation_title
from src.ui.explore_embed_style import add_explore_divider, build_explore_info_lines, get_explore_color


def _format_inventory_entry(item: PlayerInventoryItem) -> str:
    detail_bits = [f"Type: {item.item_type.replace('_', ' ').title()}"]
    rarity_label = item.rarity.replace("_", " ").title()
    if item.rarity.lower() != "common":
        detail_bits.append(f"Rarity: {rarity_label}")
    if item.source_text:
        detail_bits.append(f"Source: {item.source_text}")

    lines = [f"**x{item.quantity} {item.item_name}**"]
    if item.item_description:
        lines.append(item.item_description)
    if item.item_key == "bandages":
        lines.append("Use with `/use` to restore 25% HP outside combat.")
    if item.item_key == "ration_pack":
        lines.append("Use with `/use` to restore 10 stamina outside combat.")
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
        title="🎒 Soul Record - Inventory",
        description=(
            "Everything you managed to keep, hide, or drag out of the district ends up here. "
            "In Rukongai, what stays in your hands matters almost as much as what stays in your lungs."
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
            f"❤️ HP: {player.hp_current}/{player.hp_max}",
            f"🔷 Mana: {player.mana_current}/{player.mana_max}",
            f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
            f"💰 Kan: {player.kan}",
            f"📈 Level: {player.level}",
            f"🎭 {reputation_label}: {reputation_title}",
        ),
        inline=False,
    )
    embed.add_field(
        name="Bag State",
        value=build_explore_info_lines(
            f"🎒 Item Stacks: {len(items)}",
            f"📦 Total Quantity: {total_quantity}",
            "Use `/use` on consumables once real supplies start piling up.",
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
        embed.set_footer(text="Even an empty bag starts feeling heavy once the district teaches you what you need.")
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
    embed.set_footer(text="What survives the streets has value long before anyone calls it treasure.")
    return embed


def build_item_use_unavailable_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🩹 Item Use Unavailable",
        description="The inventory records are out of reach right now. Try again when the shelves settle.",
        color=get_explore_color("combat"),
    )
    add_explore_divider(embed)
    return embed


def build_item_use_blocked_embed(title: str, description: str, *, kind: str = "combat") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=get_explore_color(kind),
    )
    add_explore_divider(embed)
    return embed


def build_item_use_empty_embed(
    *,
    player: PlayerProfile,
    item_definition: ItemDefinition,
    reason: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"🩹 {item_definition.name}",
        description=reason,
        color=get_explore_color("flavor"),
    )
    embed.add_field(
        name="Current State",
        value=build_explore_info_lines(
            f"❤️ HP: {player.hp_current}/{player.hp_max}",
            f"🔷 Mana: {player.mana_current}/{player.mana_max}",
            f"⚡ Stamina: {player.stamina_current}/{player.stamina_max}",
        ),
        inline=False,
    )
    add_explore_divider(embed)
    return embed


def build_item_use_success_embed(
    *,
    player: PlayerProfile,
    item_definition: ItemDefinition,
    healed_amount: int,
    restored_stamina: int,
    quantity_remaining: int,
) -> discord.Embed:
    description = (
        "You force yourself to eat, let the weight settle, and feel a little strength return to your limbs."
        if restored_stamina > 0
        else "You work the wraps tight, slow your breathing, and get the worst of the damage back under control."
    )
    embed = discord.Embed(
        title=f"🩹 {item_definition.name} Used",
        description=description,
        color=get_explore_color("reward"),
    )

    change_lines = [f"🎒 Remaining: {quantity_remaining}"]
    if healed_amount > 0:
        change_lines = [
            f"❤️ HP Restored: {healed_amount}",
            f"❤️ Current HP: {player.hp_current}/{player.hp_max}",
            *change_lines,
        ]
    if restored_stamina > 0:
        change_lines = [
            f"⚡ Stamina Restored: {restored_stamina}",
            f"⚡ Current Stamina: {player.stamina_current}/{player.stamina_max}",
            *change_lines,
        ]

    embed.add_field(
        name="What Changed",
        value=build_explore_info_lines(*change_lines),
        inline=False,
    )
    effect_text = "Bandages restore **25% of your max HP** outside combat."
    if item_definition.restore_stamina_flat > 0:
        effect_text = f"{item_definition.name} restores **{item_definition.restore_stamina_flat} stamina** outside combat."
    embed.add_field(
        name="Item Effect",
        value=effect_text,
        inline=False,
    )
    add_explore_divider(embed)
    footer_text = "Even rough treatment is better than bleeding into the dirt."
    if restored_stamina > 0:
        footer_text = "A little fuel still matters when the streets keep taking from you."
    embed.set_footer(text=footer_text)
    return embed
