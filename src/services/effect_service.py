from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

from asyncpg import Connection, Pool, Record

from src.data.effects import ExploreEffectTemplate
from src.models.effects import PlayerEffect
from src.models.player import PlayerProfile


PLAYER_EFFECT_COLUMNS = """
    id,
    user_id,
    effect_key,
    title,
    description,
    effect_type,
    magnitude,
    duration_minutes,
    expires_at,
    remaining_explores,
    source_text,
    created_at,
    updated_at
"""


@dataclass(slots=True)
class EffectiveCombatSnapshot:
    hp_current: int
    hp_max: int
    mana_current: int
    mana_max: int
    power: int
    defense: int
    speed: int
    reiatsu: int


@dataclass(slots=True)
class ExploreXpBoostResult:
    adjusted_xp: int
    modifier_pct: int
    summary_text: str | None = None


NON_STACKING_STAT_EFFECT_TYPES = {
    "power_pct",
    "defense_pct",
    "speed_pct",
    "reiatsu_pct",
    "hp_pct",
    "mana_pct",
}


async def fetch_player_effect_records(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> list[Record]:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetch(
        f"""
        SELECT {PLAYER_EFFECT_COLUMNS}
        FROM player_effects
        WHERE user_id = $1
        ORDER BY created_at ASC
        {lock_clause}
        """,
        user_id,
    )


async def _cleanup_expired_effects(connection: Connection, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    await connection.execute(
        """
        DELETE FROM player_effects
        WHERE user_id = $1
          AND (
              (expires_at IS NOT NULL AND expires_at <= $2)
              OR (remaining_explores IS NOT NULL AND remaining_explores <= 0)
          )
        """,
        user_id,
        now,
    )


async def list_active_player_effects_for_connection(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> list[PlayerEffect]:
    await _cleanup_expired_effects(connection, user_id)
    records = await fetch_player_effect_records(connection, user_id, for_update=for_update)
    return [PlayerEffect.from_record(record) for record in records]


async def list_active_player_effects(
    pool: Pool | None,
    user_id: int,
) -> list[PlayerEffect]:
    if pool is None:
        return []

    async with pool.acquire() as connection:
        return await list_active_player_effects_for_connection(connection, user_id)


async def grant_player_effect(
    connection: Connection,
    user_id: int,
    template: ExploreEffectTemplate,
    *,
    source_text: str,
) -> PlayerEffect:
    now = datetime.now(timezone.utc)
    expires_at = None
    if template.duration_minutes is not None:
        expires_at = now + timedelta(minutes=template.duration_minutes)

    record = await connection.fetchrow(
        f"""
        INSERT INTO player_effects (
            user_id,
            effect_key,
            title,
            description,
            effect_type,
            magnitude,
            duration_minutes,
            expires_at,
            remaining_explores,
            source_text
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING {PLAYER_EFFECT_COLUMNS}
        """,
        user_id,
        template.key,
        template.title,
        template.description,
        template.effect_type,
        template.magnitude,
        template.duration_minutes,
        expires_at,
        template.remaining_explores,
        source_text,
    )
    return PlayerEffect.from_record(record)


def _effect_sign_text(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def describe_effect_for_embed(effect: PlayerEffect) -> str:
    if effect.effect_type == "stamina_flat":
        return f"{effect.title} — {_effect_sign_text(effect.magnitude)} stamina"
    if effect.effect_type == "stamina_regen_pct":
        duration = f" for {effect.duration_minutes}m" if effect.duration_minutes is not None else ""
        return f"{effect.title} — {_effect_sign_text(effect.magnitude)}% stamina regen{duration}"
    if effect.effect_type == "xp_boost_pct":
        uses = effect.remaining_explores if effect.remaining_explores is not None else 0
        return f"{effect.title} — {_effect_sign_text(effect.magnitude)}% XP for {uses} explore(s)"
    if effect.effect_type == "shop_discount_pct":
        duration = f" for {effect.duration_minutes}m" if effect.duration_minutes is not None else ""
        return f"{effect.title} — {abs(effect.magnitude)}% shop discount{duration}"
    if effect.effect_type == "travel_time_flat":
        duration = f" for {effect.duration_minutes}m" if effect.duration_minutes is not None else ""
        return f"{effect.title} — {abs(effect.magnitude)} minute faster travel{duration}"
    if effect.effect_type == "combat_focus_flat":
        duration = f" for {effect.duration_minutes}m" if effect.duration_minutes is not None else ""
        return f"{effect.title} — {_effect_sign_text(effect.magnitude)} opening focus{duration}"
    if effect.effect_type == "special_trigger_pct":
        duration = f" for {effect.duration_minutes}m" if effect.duration_minutes is not None else ""
        return f"{effect.title} — {_effect_sign_text(effect.magnitude)}% special-event chance{duration}"

    label_map = {
        "power_pct": "Power",
        "defense_pct": "Defense",
        "speed_pct": "Speed",
        "reiatsu_pct": "Reiatsu",
        "hp_pct": "HP",
        "mana_pct": "Mana",
    }
    label = label_map.get(effect.effect_type, effect.effect_type)
    duration = f" for {effect.duration_minutes}m" if effect.duration_minutes is not None else ""
    return f"{effect.title} — {_effect_sign_text(effect.magnitude)}% {label}{duration}"


def summarize_active_effects(effects: list[PlayerEffect], *, limit: int = 4) -> list[str]:
    lines: list[str] = []
    for effect in effects[:limit]:
        lines.append(f"✨ {describe_effect_for_embed(effect)}")

    remaining = len(effects) - len(lines)
    if remaining > 0:
        lines.append(f"…and {remaining} more active effect(s)")
    return lines


def _total_modifier(effects: list[PlayerEffect], effect_type: str) -> int:
    return sum(effect.magnitude for effect in effects if effect.effect_type == effect_type)


def get_stamina_regen_modifier_pct(effects: list[PlayerEffect]) -> int:
    return _total_modifier(effects, "stamina_regen_pct")


def get_effective_stat_modifier_pct(effects: list[PlayerEffect], effect_type: str) -> int:
    return _total_modifier(effects, effect_type)


def get_shop_discount_pct(effects: list[PlayerEffect]) -> int:
    return max(0, _total_modifier(effects, "shop_discount_pct"))


def apply_shop_discount_effect(base_price: int, effects: list[PlayerEffect]) -> int:
    discount_pct = get_shop_discount_pct(effects)
    if discount_pct <= 0:
        return max(1, base_price)

    scaled = base_price * (1 - discount_pct / 100)
    return max(1, int(round(scaled)))


def get_travel_time_modifier_minutes(effects: list[PlayerEffect]) -> int:
    return _total_modifier(effects, "travel_time_flat")


def apply_travel_time_modifier(base_minutes: int, effects: list[PlayerEffect]) -> int:
    return max(1, base_minutes + get_travel_time_modifier_minutes(effects))


def get_initial_combat_focus_bonus(effects: list[PlayerEffect]) -> int:
    return max(0, _total_modifier(effects, "combat_focus_flat"))


def get_special_trigger_bonus_pct(effects: list[PlayerEffect]) -> int:
    return max(0, _total_modifier(effects, "special_trigger_pct"))


def get_blocked_stat_effect_types(effects: list[PlayerEffect]) -> set[str]:
    return {
        effect.effect_type
        for effect in effects
        if effect.effect_type in NON_STACKING_STAT_EFFECT_TYPES
    }


def apply_stamina_regen_modifier(base_gain: int, modifier_pct: int) -> int:
    if base_gain <= 0 or modifier_pct == 0:
        return max(0, base_gain)

    scaled = base_gain * (1 + modifier_pct / 100)
    adjusted = math.ceil(scaled) if modifier_pct > 0 else math.floor(scaled)
    return max(0, int(adjusted))


def _apply_percent_modifier(base_value: int, modifier_pct: int, *, minimum: int = 0) -> int:
    if modifier_pct == 0:
        return max(minimum, base_value)

    scaled = base_value * (1 + modifier_pct / 100)
    adjusted = math.ceil(scaled) if modifier_pct > 0 else math.floor(scaled)
    return max(minimum, int(adjusted))


def build_effective_combat_snapshot(
    player: PlayerProfile,
    effects: list[PlayerEffect],
) -> EffectiveCombatSnapshot:
    hp_modifier = get_effective_stat_modifier_pct(effects, "hp_pct")
    mana_modifier = get_effective_stat_modifier_pct(effects, "mana_pct")

    hp_max = _apply_percent_modifier(player.hp_max, hp_modifier, minimum=1)
    hp_current = min(
        hp_max,
        _apply_percent_modifier(player.hp_current, hp_modifier, minimum=0),
    )
    mana_max = _apply_percent_modifier(player.mana_max, mana_modifier, minimum=1)
    mana_current = min(
        mana_max,
        _apply_percent_modifier(player.mana_current, mana_modifier, minimum=0),
    )

    return EffectiveCombatSnapshot(
        hp_current=max(1, hp_current),
        hp_max=hp_max,
        mana_current=mana_current,
        mana_max=mana_max,
        power=_apply_percent_modifier(
            player.power,
            get_effective_stat_modifier_pct(effects, "power_pct"),
        ),
        defense=_apply_percent_modifier(
            player.defense,
            get_effective_stat_modifier_pct(effects, "defense_pct"),
        ),
        speed=_apply_percent_modifier(
            player.speed,
            get_effective_stat_modifier_pct(effects, "speed_pct"),
        ),
        reiatsu=_apply_percent_modifier(
            player.reiatsu,
            get_effective_stat_modifier_pct(effects, "reiatsu_pct"),
        ),
    )


async def apply_explore_xp_effects(
    connection: Connection,
    user_id: int,
    base_xp: int,
) -> ExploreXpBoostResult:
    effects = await list_active_player_effects_for_connection(connection, user_id, for_update=True)
    xp_effects = [effect for effect in effects if effect.effect_type == "xp_boost_pct"]
    if not xp_effects:
        return ExploreXpBoostResult(adjusted_xp=base_xp, modifier_pct=0)

    modifier_pct = sum(effect.magnitude for effect in xp_effects)
    scaled = base_xp * (1 + modifier_pct / 100)
    adjusted_xp = max(0, int(round(scaled)))

    for effect in xp_effects:
        if effect.remaining_explores is None:
            continue

        remaining = effect.remaining_explores - 1
        if remaining <= 0:
            await connection.execute(
                "DELETE FROM player_effects WHERE id = $1",
                effect.id,
            )
        else:
            await connection.execute(
                """
                UPDATE player_effects
                SET remaining_explores = $2, updated_at = NOW()
                WHERE id = $1
                """,
                effect.id,
                remaining,
            )

    summary_label = xp_effects[0].title if len(xp_effects) == 1 else "stacked effect"
    return ExploreXpBoostResult(
        adjusted_xp=adjusted_xp,
        modifier_pct=modifier_pct,
        summary_text=f"({_effect_sign_text(modifier_pct)}% {summary_label})",
    )
