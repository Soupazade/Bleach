from __future__ import annotations

import random
from typing import Any, Literal

from asyncpg import Connection

from src.data.combat import get_enemy_for_exploration_combat
from src.data.effects import get_exploration_effect_template
from src.data.exploration import (
    ExploreApproachDefinition,
    ExploreEventType,
    ExploreFlowType,
    ExplorationEventTemplate,
    get_explore_approach,
    get_location_event_pool,
    get_random_special_event,
)
from src.data.items import ItemDefinition, get_item_definition
from src.data.locations import get_location_definition
from src.models.combat import ActiveExplorationCombat
from src.models.effects import PlayerEffect
from src.models.exploration import ActiveExploration, PendingExplorationChoice
from src.models.player import PlayerProfile
from src.services.combat_service import (
    create_active_exploration_combat,
    delete_active_exploration_combat,
    project_profile_hp_from_combat,
    project_profile_mana_from_combat,
)
from src.services.effect_service import (
    apply_explore_xp_effects,
    build_effective_combat_snapshot,
    describe_effect_for_embed,
    get_blocked_stat_effect_types,
    get_special_trigger_bonus_pct,
    grant_player_effect,
    list_active_player_effects_for_connection,
)
from src.services.exploration.repository import create_pending_exploration_choice
from src.services.exploration.types import (
    AppliedExploreEffect,
    AppliedExploreLoot,
    ExplorationDecisionPrompt,
    ExplorationResolution,
)
from src.services.inventory_service import grant_inventory_item_for_connection
from src.services.player_service import get_or_sync_player_record, update_player_record
from src.services.reputation_service import (
    apply_rep_stamina_cost,
    apply_rep_xp,
    apply_reputation_change,
    get_location_reputation_field,
    get_location_reputation_value,
    get_reputation_modifiers,
)
from src.services.status_service import grant_wounded_status


def _get_loot_definition(
    *,
    item_key: str,
    fallback_name: str,
    fallback_description: str,
) -> ItemDefinition:
    try:
        return get_item_definition(item_key)
    except ValueError:
        return ItemDefinition(
            key=item_key,
            name=fallback_name,
            description=fallback_description,
            item_type="material",
            rarity="common",
            stackable=True,
        )


def _format_text(
    text: str,
    *,
    approach: ExploreApproachDefinition,
    location_name: str,
) -> str:
    return text.format(
        approach=approach.label,
        location=location_name,
    )


def _weighted_event_type(exploration: ActiveExploration) -> ExploreEventType:
    approach = get_explore_approach(exploration.approach)
    event_types = tuple(approach.event_biases.keys())
    weights = tuple(approach.event_biases.values())
    return random.choices(event_types, weights=weights, k=1)[0]


def roll_resolution_flow(approach: ExploreApproachDefinition) -> ExploreFlowType:
    weights_by_risk = {
        "low": (45, 40, 15),
        "medium": (38, 42, 20),
        "high": (30, 45, 25),
    }
    instant_weight, single_weight, multi_weight = weights_by_risk.get(
        approach.risk_tier,
        (60, 30, 10),
    )
    if approach.focus_key == "chase_rumors":
        instant_weight -= 8
        single_weight += 3
        multi_weight += 5
    elif approach.focus_key == "look_for_fight":
        instant_weight += 10
        single_weight -= 4
        multi_weight -= 6
    elif approach.focus_key == "explore_streets":
        single_weight += 2
        multi_weight += 1
        instant_weight -= 3

    if approach.duration_minutes >= 10:
        instant_weight -= 10
        single_weight += 2
        multi_weight += 8
    elif approach.duration_minutes >= 5:
        instant_weight -= 4
        multi_weight += 4

    instant_weight = max(5, instant_weight)
    single_weight = max(5, single_weight)
    multi_weight = max(5, multi_weight)
    return random.choices(
        ("instant", "single_choice", "multi_step"),
        weights=(instant_weight, single_weight, multi_weight),
        k=1,
    )[0]


def _roll_special_trigger(approach: ExploreApproachDefinition, *, bonus_pct: int = 0) -> bool:
    chance_by_risk = {
        "low": 0.10,
        "medium": 0.12,
        "high": 0.15,
    }
    total_chance = chance_by_risk.get(approach.risk_tier, 0.12) + (bonus_pct / 100)
    if approach.focus_key == "chase_rumors":
        total_chance += 0.08
    elif approach.focus_key == "explore_streets":
        total_chance += 0.02

    if approach.duration_minutes >= 10:
        total_chance += 0.08
    elif approach.duration_minutes >= 5:
        total_chance += 0.04
    return random.random() < min(0.85, total_chance)


def _format_event_description(
    template: ExplorationEventTemplate,
    exploration: ActiveExploration,
) -> str:
    approach = get_explore_approach(exploration.approach)
    location = get_location_definition(exploration.location)
    return _format_text(
        template.description,
        approach=approach,
        location_name=location.name,
    )


def _resolve_reward_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.reward_events)
    xp_gained = random.randint(approach.xp_min, approach.xp_max)
    description = _format_event_description(event, exploration)
    return event.title, description, xp_gained


def _resolve_combat_event(exploration: ActiveExploration) -> tuple[str, str, int, str]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.combat_events)
    description = _format_event_description(event, exploration)
    win_chance_by_risk = {
        "low": 0.75,
        "medium": 0.64,
        "high": 0.55,
    }
    won = random.random() < win_chance_by_risk.get(approach.risk_tier, 0.64)
    victory_followups = (
        "You meet it head-on and come out the other side still breathing.",
        "You answer the rush with your own and force the street to blink first.",
        "It gets ugly fast, but you are the one left standing when the dust settles.",
    )
    setback_followups = (
        "You get out, but not clean. The street makes sure you feel the price of it.",
        "You survive it, bruised and breathing hard, with enough sense to know how close it got.",
        "You stagger clear with your life and a fresh reminder that Rukongai never swings light.",
    )

    if won:
        xp_gained = random.randint(12, 20)
        outcome = "Victory"
        description = f"{description} {random.choice(victory_followups)}"
        title = f"{event.title} Won"
    else:
        xp_gained = 5
        outcome = "Setback"
        description = f"{description} {random.choice(setback_followups)}"
        title = f"{event.title} Lost"

    return title, description, xp_gained, outcome


def _resolve_choice_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.choice_events)
    xp_floor = max(3, approach.xp_min - 1)
    xp_ceiling = max(xp_floor, approach.xp_max - 2)
    xp_gained = random.randint(xp_floor, xp_ceiling)
    description = _format_event_description(event, exploration)
    return event.title, description, xp_gained


def _resolve_flavor_event(exploration: ActiveExploration) -> tuple[str, str, int]:
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.flavor_events)
    description = _format_event_description(event, exploration)
    return event.title, description, random.randint(2, 4)


def roll_instant_exploration_event(
    exploration: ActiveExploration,
) -> tuple[Literal["reward", "combat", "choice", "flavor"], str, str, int, str | None]:
    event_type = _weighted_event_type(exploration)

    if event_type == "reward":
        title, description, xp_gained = _resolve_reward_event(exploration)
        return "reward", title, description, xp_gained, None

    if event_type == "combat":
        title, description, xp_gained, outcome = _resolve_combat_event(exploration)
        return "combat", title, description, xp_gained, outcome

    if event_type == "choice":
        title, description, xp_gained = _resolve_choice_event(exploration)
        return "choice", title, description, xp_gained, None

    title, description, xp_gained = _resolve_flavor_event(exploration)
    return "flavor", title, description, xp_gained, None


def resolve_outcome_xp(
    approach: ExploreApproachDefinition,
    xp_profile: Literal[
        "none",
        "approach_low",
        "approach_base",
        "approach_high",
        "combat_win",
        "combat_lose",
        "special_base",
        "special_high",
        "special_combat_win",
        "special_combat_lose",
    ],
) -> int:
    if xp_profile == "none":
        return 0
    if xp_profile == "combat_win":
        return random.randint(12, 20)
    if xp_profile == "combat_lose":
        return 5
    if xp_profile == "special_combat_win":
        return random.randint(max(20, approach.xp_min * 2), max(30, approach.xp_max * 2 + 4))
    if xp_profile == "special_combat_lose":
        return random.randint(max(4, approach.xp_min - 1), max(8, approach.xp_min + 2))
    if xp_profile == "approach_low":
        xp_floor = max(1, approach.xp_min - 3)
        xp_ceiling = max(xp_floor, approach.xp_min)
        return random.randint(xp_floor, xp_ceiling)
    if xp_profile == "approach_high":
        xp_floor = approach.xp_min + 2
        xp_ceiling = max(xp_floor, approach.xp_max + 4)
        return random.randint(xp_floor, xp_ceiling)
    if xp_profile == "special_high":
        xp_floor = max(approach.xp_min * 2, approach.xp_max + 6)
        xp_ceiling = max(xp_floor, approach.xp_max * 2 + 8)
        return random.randint(xp_floor, xp_ceiling)
    if xp_profile == "special_base":
        xp_floor = max(approach.xp_min * 2 - 2, approach.xp_max + 2)
        xp_ceiling = max(xp_floor, approach.xp_max * 2)
        return random.randint(xp_floor, xp_ceiling)

    return random.randint(approach.xp_min, approach.xp_max)


async def _apply_progression_and_reputation(
    connection: Connection,
    user_id: int,
    *,
    location_key: str,
    xp_gained: int,
    reputation_change: int = 0,
) -> tuple[PlayerProfile, int, int, int]:
    from src.services.formulas import apply_experience_gain

    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        raise ValueError(f"Missing player profile for user {user_id}")

    current_player = PlayerProfile.from_record(player_sync.record)
    new_level, new_xp, levels_gained, applied_xp = apply_experience_gain(
        current_level=current_player.level,
        current_xp=current_player.xp,
        xp_gain=xp_gained,
    )

    updates: dict[str, Any] = {
        "level": new_level,
        "xp": new_xp,
    }

    applied_reputation_change = 0
    if reputation_change != 0:
        reputation_field = get_location_reputation_field(location_key)
        current_reputation = get_location_reputation_value(current_player, location_key)
        updated_reputation = apply_reputation_change(current_reputation, reputation_change)
        applied_reputation_change = updated_reputation - current_reputation
        updates[reputation_field] = updated_reputation

    updated_player_record = await update_player_record(connection, user_id, updates)
    return PlayerProfile.from_record(updated_player_record), levels_gained, applied_reputation_change, applied_xp


async def get_current_player(
    connection: Connection,
    user_id: int,
) -> PlayerProfile:
    player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
    if player_sync is None:
        raise ValueError(f"Missing player profile for user {user_id}")

    return PlayerProfile.from_record(player_sync.record)


def apply_location_xp_modifier(
    player: PlayerProfile,
    location_key: str,
    base_xp: int,
) -> tuple[int, int]:
    rep_value = get_location_reputation_value(player, location_key)
    return apply_rep_xp(base_xp, rep_value), int(get_reputation_modifiers(rep_value)["xp_modifier"])


def apply_location_stamina_cost_modifier(
    player: PlayerProfile,
    location_key: str,
    base_cost: int,
) -> tuple[int, int]:
    rep_value = get_location_reputation_value(player, location_key)
    adjusted_cost = apply_rep_stamina_cost(base_cost, rep_value)
    return adjusted_cost, adjusted_cost - base_cost


async def _apply_explore_xp_bonus(
    connection: Connection,
    user_id: int,
    base_xp: int,
) -> tuple[int, str | None]:
    xp_boost = await apply_explore_xp_effects(connection, user_id, base_xp)
    return xp_boost.adjusted_xp, xp_boost.summary_text


async def _apply_explore_bonus_effect(
    connection: Connection,
    player: PlayerProfile,
    *,
    event_type: Literal["reward", "combat", "choice", "flavor"],
    combat_outcome: str | None,
    reputation_change: int,
) -> tuple[PlayerProfile, AppliedExploreEffect | None]:
    active_effects = await list_active_player_effects_for_connection(
        connection,
        player.user_id,
        for_update=True,
    )
    template = get_exploration_effect_template(
        event_type=event_type,
        combat_outcome=combat_outcome,
        reputation_change=reputation_change,
        blocked_effect_types=get_blocked_stat_effect_types(active_effects),
    )
    if template is None:
        return player, None

    if template.effect_type == "stamina_flat":
        updated_stamina = max(
            0,
            min(player.stamina_max, player.stamina_current + template.magnitude),
        )
        updated_record = await update_player_record(
            connection,
            player.user_id,
            {"stamina_current": updated_stamina},
        )
        updated_player = PlayerProfile.from_record(updated_record)
        delta_applied = updated_player.stamina_current - player.stamina_current
        summary = (
            f"{template.title} - "
            f"{delta_applied:+d} stamina"
            if delta_applied != 0
            else f"{template.title} - no stamina change"
        )
        return updated_player, AppliedExploreEffect(
            title=template.title,
            description=template.description,
            summary_text=summary,
        )

    granted_effect = await grant_player_effect(
        connection,
        player.user_id,
        template,
        source_text="Rukongai Streets",
    )
    return player, AppliedExploreEffect(
        title=granted_effect.title,
        description=granted_effect.description,
        summary_text=describe_effect_for_embed(granted_effect),
    )


def _get_reward_loot_item(
    *,
    event_type: Literal["reward", "choice", "flavor"],
    title: str,
    reputation_change: int,
    approach: ExploreApproachDefinition,
) -> ItemDefinition | None:
    cloth_scraps = _get_loot_definition(
        item_key="cloth_scraps",
        fallback_name="Cloth Scraps",
        fallback_description="Worn fabric with just enough life left to trade, patch, or repurpose.",
    )
    food_scraps = _get_loot_definition(
        item_key="food_scraps",
        fallback_name="Food Scraps",
        fallback_description="A rough collection of edible leftovers. Not dignified, but still worth something.",
    )

    if reputation_change < 0:
        return food_scraps

    if event_type == "reward":
        if title in {"Scrap Luck", "Rumor Turned Reward", "You Find the Hideout"}:
            return cloth_scraps
        if title in {"A Kind Hand in a Hard Place", "Mercy Before Escape"}:
            return food_scraps
        if title in {
            "Market Edge Score",
            "The Crowd Holds the Line",
            "Quick Hands, Hard-Won Prize",
            "Controlled Risk, Real Gain",
            "You Peel Off the Best Cut",
        }:
            return random.choice((cloth_scraps, food_scraps))
        return random.choice((cloth_scraps, food_scraps))

    if event_type == "choice":
        if approach.focus_key == "chase_rumors":
            return random.choice((cloth_scraps, food_scraps))
        if title == "A Lead in the Dust":
            return cloth_scraps
        if title == "Need Versus Opportunity":
            return food_scraps
        if title in {
            "A Whisper Worth Chasing",
            "Knowledge Carried Forward",
            "You Settle for Less",
            "A Smaller Score, Still Worth It",
        }:
            return random.choice((cloth_scraps, food_scraps))

    if event_type == "flavor":
        if title in {"Hunger in the Air", "Small Mercy, Small Hope"}:
            return food_scraps
        if title in {"Another Night in Rukongai", "The District Watches Back"}:
            return cloth_scraps

    return None


def _roll_loot_quantity(
    player: PlayerProfile,
    *,
    approach: ExploreApproachDefinition,
    event_type: Literal["reward", "choice", "flavor"],
    reputation_change: int,
) -> int:
    luck_bonus = int(round(player.trait_data.bonuses.event_reward_pct * 100))
    luck_bonus += max(0, player.rukongai_rep // 25)
    if approach.focus_key == "scavenge_supplies":
        luck_bonus += 12
    if approach.duration_minutes >= 5:
        luck_bonus += 6
    if approach.duration_minutes >= 10:
        luck_bonus += 10
    if event_type == "reward":
        luck_bonus += 6
    elif event_type == "choice":
        luck_bonus += 3
    roll = random.randint(1, 100) + luck_bonus
    if roll >= 96:
        return 3
    if roll >= 54:
        return 2
    quantity = 1
    if reputation_change < 0:
        quantity = max(quantity, 2)
    return quantity


async def _apply_explore_loot_reward(
    connection: Connection,
    *,
    player: PlayerProfile,
    approach: ExploreApproachDefinition,
    event_type: Literal["reward", "choice", "flavor"],
    title: str,
    reputation_change: int,
) -> AppliedExploreLoot | None:
    item_definition = _get_reward_loot_item(
        event_type=event_type,
        title=title,
        reputation_change=reputation_change,
        approach=approach,
    )
    if item_definition is None:
        return None

    quantity = _roll_loot_quantity(
        player,
        approach=approach,
        event_type=event_type,
        reputation_change=reputation_change,
    )
    granted_item = await grant_inventory_item_for_connection(
        connection,
        user_id=player.user_id,
        item_key=item_definition.key,
        item_name=item_definition.name,
        quantity=quantity,
        item_description=item_definition.description,
        item_type=item_definition.item_type,
        rarity=item_definition.rarity,
        stackable=item_definition.stackable,
        source_text="Rukongai Streets",
    )
    return AppliedExploreLoot(
        item_key=granted_item.item_key,
        item_name=granted_item.item_name,
        quantity=quantity,
        description=item_definition.description,
        summary_text=f"Found **{quantity}x {granted_item.item_name}**",
    )


def get_instant_reputation_change(
    event_type: Literal["reward", "combat", "choice", "flavor"],
    combat_outcome: str | None,
) -> int:
    return 0


def should_trigger_special_opportunity(
    approach: ExploreApproachDefinition,
    effects: list[PlayerEffect] | None = None,
) -> bool:
    bonus_pct = 0 if effects is None else get_special_trigger_bonus_pct(effects)
    return _roll_special_trigger(approach, bonus_pct=bonus_pct)


async def create_special_offer(
    connection: Connection,
    base_resolution: ExplorationResolution,
    *,
    message_id: int | None = None,
) -> ExplorationDecisionPrompt:
    from src.services.exploration.choices import build_decision_prompt

    special_event = get_random_special_event(base_resolution.exploration.location)
    session = await create_pending_exploration_choice(
        connection,
        base_resolution.exploration,
        message_id=message_id,
        event_key=special_event.key,
        event_flow=special_event.flow_type,
        current_step=special_event.initial_step_id,
        session_kind="special_offer",
        special_event_key=special_event.key,
        base_resolution=base_resolution,
    )
    return build_decision_prompt(session, base_resolution.player)


def build_resolution_from_pending_base(
    session: PendingExplorationChoice,
    player: PlayerProfile,
    levels_gained: int,
) -> ExplorationResolution:
    if (
        session.base_event_type is None
        or session.base_title is None
        or session.base_description is None
        or session.base_xp is None
    ):
        raise ValueError("Pending special offer is missing its stored base resolution.")

    adjusted_xp, xp_modifier_pct = apply_location_xp_modifier(
        player,
        session.location,
        session.base_xp,
    )
    base_rep_change = session.base_rep_change or 0

    return ExplorationResolution(
        exploration=session.to_active_exploration(),
        player=player,
        event_type=session.base_event_type,  # type: ignore[arg-type]
        title=session.base_title,
        description=session.base_description,
        xp_gained=adjusted_xp,
        levels_gained=levels_gained,
        base_xp=session.base_xp,
        reputation_xp_modifier_pct=xp_modifier_pct,
        reputation_change=base_rep_change,
        combat_outcome=session.base_combat_outcome,
    )


async def finalize_non_combat_resolution(
    connection: Connection,
    *,
    user_id: int,
    exploration: ActiveExploration,
    event_type: Literal["reward", "choice", "flavor"],
    title: str,
    description: str,
    base_xp: int,
    reputation_change: int = 0,
    combat_outcome: str | None = None,
) -> ExplorationResolution:
    current_player = await get_current_player(connection, user_id)
    adjusted_xp, xp_modifier_pct = apply_location_xp_modifier(
        current_player,
        exploration.location,
        base_xp,
    )
    final_xp, xp_effect_text = await _apply_explore_xp_bonus(
        connection,
        user_id,
        adjusted_xp,
    )
    player, levels_gained, applied_reputation_change, applied_xp = await _apply_progression_and_reputation(
        connection,
        user_id,
        location_key=exploration.location,
        xp_gained=final_xp,
        reputation_change=reputation_change,
    )
    player, applied_effect = await _apply_explore_bonus_effect(
        connection,
        player,
        event_type=event_type,
        combat_outcome=combat_outcome,
        reputation_change=applied_reputation_change,
    )
    applied_loot = await _apply_explore_loot_reward(
        connection,
        player=player,
        approach=get_explore_approach(exploration.approach),
        event_type=event_type,
        title=title,
        reputation_change=applied_reputation_change,
    )
    return ExplorationResolution(
        exploration=exploration,
        player=player,
        event_type=event_type,
        title=title,
        description=description,
        xp_gained=applied_xp,
        levels_gained=levels_gained,
        base_xp=base_xp,
        reputation_xp_modifier_pct=xp_modifier_pct,
        reputation_change=applied_reputation_change,
        combat_outcome=combat_outcome,
        explore_xp_effect_text=xp_effect_text,
        applied_effect=applied_effect,
        applied_loot=applied_loot,
    )


def get_combat_lose_profile(xp_profile: str) -> Literal["combat_lose", "special_combat_lose"]:
    return "special_combat_lose" if xp_profile == "special_combat_win" else "combat_lose"


async def start_instant_combat(
    connection: Connection,
    *,
    exploration: ActiveExploration,
    player: PlayerProfile,
) -> ActiveExplorationCombat:
    approach = get_explore_approach(exploration.approach)
    event_pool = get_location_event_pool(exploration.location)
    event = random.choice(event_pool.combat_events)
    encounter_description = _format_event_description(event, exploration)
    enemy = get_enemy_for_exploration_combat(
        exploration.location,
        encounter_title=event.title,
        approach_risk=approach.risk_tier,
        player_level=player.level,
    )
    active_effects = await list_active_player_effects_for_connection(connection, player.user_id)
    combat_snapshot = build_effective_combat_snapshot(player, active_effects)
    return await create_active_exploration_combat(
        connection,
        exploration=exploration,
        player=player,
        combat_snapshot=combat_snapshot,
        encounter_title=event.title,
        encounter_description=encounter_description,
        resolution_title=event.title,
        resolution_description=(
            f"The clash in **{get_location_definition(exploration.location).name}** breaks your way. "
            "You force the threat down and keep moving before the block can close around you."
        ),
        reward_xp_win=enemy.reward_xp_win,
        reward_xp_lose=enemy.reward_xp_lose,
        enemy_template=enemy,
    )


async def start_decision_combat(
    connection: Connection,
    *,
    session: PendingExplorationChoice,
    player: PlayerProfile,
    event_title: str,
    step_description: str,
    selected_label: str,
    resolution_title: str,
    resolution_description: str,
    reward_xp_win: int,
    reward_xp_lose: int,
    reputation_change: int,
    message_id: int | None,
) -> ActiveExplorationCombat:
    exploration = session.to_active_exploration()
    approach = get_explore_approach(session.approach)
    encounter_title = event_title
    encounter_description = (
        f"{step_description}\n\n"
        f"You commit to **{selected_label}**. The next breath turns into a live fight."
    )
    enemy = get_enemy_for_exploration_combat(
        session.location,
        encounter_title=event_title,
        approach_risk=approach.risk_tier,
        player_level=player.level,
    )
    active_effects = await list_active_player_effects_for_connection(connection, player.user_id)
    combat_snapshot = build_effective_combat_snapshot(player, active_effects)
    return await create_active_exploration_combat(
        connection,
        exploration=exploration,
        player=player,
        combat_snapshot=combat_snapshot,
        encounter_title=encounter_title,
        encounter_description=encounter_description,
        resolution_title=resolution_title,
        resolution_description=resolution_description,
        reward_xp_win=reward_xp_win,
        reward_xp_lose=reward_xp_lose,
        reputation_change=reputation_change,
        enemy_template=enemy,
        message_id=message_id,
    )


async def finalize_combat_resolution(
    connection: Connection,
    *,
    combat: ActiveExplorationCombat,
    base_xp: int,
    combat_outcome: str,
    title: str,
    description: str,
    reputation_change: int,
) -> ExplorationResolution:
    current_player = await get_current_player(connection, combat.user_id)
    adjusted_xp, xp_modifier_pct = apply_location_xp_modifier(
        current_player,
        combat.location,
        base_xp,
    )
    final_xp, xp_effect_text = await _apply_explore_xp_bonus(
        connection,
        combat.user_id,
        adjusted_xp,
    )
    player, levels_gained, applied_reputation_change, applied_xp = await _apply_progression_and_reputation(
        connection,
        combat.user_id,
        location_key=combat.location,
        xp_gained=final_xp,
        reputation_change=reputation_change,
    )

    blackout_applied = combat_outcome == "Setback"
    player_updates: dict[str, Any] = {
        "hp_current": project_profile_hp_from_combat(player, combat),
        "mana_current": project_profile_mana_from_combat(player, combat),
        "has_minor_setback": False,
        "setback_source": None,
        "setback_at": None,
    }
    if blackout_applied:
        player_updates["hp_current"] = 1
        player_updates["location"] = "rukongai_streets"

    updated_player_record = await update_player_record(connection, combat.user_id, player_updates)
    updated_player = PlayerProfile.from_record(updated_player_record)
    if blackout_applied:
        await grant_wounded_status(connection, combat.user_id)
    updated_player, applied_effect = await _apply_explore_bonus_effect(
        connection,
        updated_player,
        event_type="combat",
        combat_outcome=combat_outcome,
        reputation_change=applied_reputation_change,
    )
    await delete_active_exploration_combat(connection, combat.user_id)
    return ExplorationResolution(
        exploration=combat.to_active_exploration(),
        player=updated_player,
        event_type="combat",
        title=title,
        description=description,
        xp_gained=applied_xp,
        levels_gained=levels_gained,
        base_xp=base_xp,
        reputation_xp_modifier_pct=xp_modifier_pct,
        reputation_change=applied_reputation_change,
        combat_outcome=combat_outcome,
        explore_xp_effect_text=xp_effect_text,
        applied_effect=applied_effect,
    )
