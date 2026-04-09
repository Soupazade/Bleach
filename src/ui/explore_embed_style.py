from __future__ import annotations

import discord


EXPLORE_DIVIDER = "━━━━━━━━━━━━━━━"
EXPLORE_BLUE = discord.Color.from_rgb(72, 118, 214)
CHOICE_GOLD = discord.Color.from_rgb(214, 176, 58)
COMBAT_RED = discord.Color.from_rgb(196, 59, 59)
SPECIAL_PURPLE = discord.Color.from_rgb(138, 94, 214)
REWARD_GREEN = discord.Color.from_rgb(72, 170, 96)
FLAVOR_GREY = discord.Color.from_rgb(140, 146, 156)


def get_explore_color(kind: str) -> discord.Color:
    return {
        "explore": EXPLORE_BLUE,
        "choice": CHOICE_GOLD,
        "combat": COMBAT_RED,
        "special": SPECIAL_PURPLE,
        "reward": REWARD_GREEN,
        "flavor": FLAVOR_GREY,
    }.get(kind, EXPLORE_BLUE)


def add_explore_divider(embed: discord.Embed) -> None:
    embed.add_field(name=EXPLORE_DIVIDER, value="\u200b", inline=False)


def build_explore_info_lines(*lines: str) -> str:
    return "\n".join(line for line in lines if line)


def format_option_preview(label: str, style: str) -> str:
    emoji = {
        "primary": "🧭",
        "secondary": "▫️",
        "success": "✨",
        "danger": "⚔",
    }.get(style, "▫️")
    return f"{emoji} {label}"
