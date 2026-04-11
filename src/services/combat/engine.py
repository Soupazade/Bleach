from __future__ import annotations

from dataclasses import replace
import math
import random
from typing import Iterable

from src.services.combat.abilities import get_combat_ability
from src.services.combat.types import (
    CombatChoice,
    CombatEntity,
    CombatLogEvent,
    CombatRoundOutcome,
    CombatSession,
)


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(low, min(high, value))


def _decrement_cooldowns(cooldowns: dict[str, int]) -> dict[str, int]:
    return {key: value - 1 for key, value in cooldowns.items() if value - 1 > 0}


def _regen_mana(entity: CombatEntity, *, guarded_breathing: bool = False) -> tuple[CombatEntity, int]:
    bonus_pct = 5.0 if guarded_breathing else 0.0
    regen_pct = entity.mana_regen_pct + bonus_pct
    regen_amount = max(0, math.ceil(entity.mana_max * (regen_pct / 100)))
    restored = min(entity.mana_max - entity.mana_current, regen_amount)
    return replace(entity, mana_current=entity.mana_current + restored), restored


def _initiative_score(entity: CombatEntity) -> float:
    return entity.speed + random.uniform(0.0, 3.0)


def _bonus_turn_triggered(entity: CombatEntity) -> bool:
    return random.random() < _clamp(entity.speed * 0.0002, low=0.0, high=0.35)


def _final_hit_chance(base_hit_pct: float, defender: CombatEntity) -> float:
    return _clamp(base_hit_pct - defender.dodge_chance_pct, low=5.0, high=100.0)


def _damage_after_modifiers(
    *,
    base_damage: float,
    defender: CombatEntity,
) -> tuple[int, dict[str, float | int | bool]]:
    swing_pct = random.uniform(0.90, 1.10)
    crit = random.random() < 0.05
    damage = base_damage * swing_pct
    if crit:
        damage *= 2.0
    damage *= max(0.0, 1 - (defender.damage_reduction_pct / 100))
    final_damage = max(1, int(round(damage)))
    return final_damage, {
        "base_damage": round(base_damage, 2),
        "swing_pct": round(swing_pct * 100, 2),
        "crit": crit,
        "defender_reduction_pct": round(defender.damage_reduction_pct, 2),
        "final_damage": final_damage,
    }


def _resolve_hit(
    *,
    attacker: CombatEntity,
    defender: CombatEntity,
    base_damage: float,
    base_hit_pct: float,
    label: str,
) -> tuple[CombatEntity, str, dict[str, object], bool]:
    hit_chance = _final_hit_chance(base_hit_pct, defender)
    roll = random.random() * 100
    if roll <= hit_chance:
        damage, details = _damage_after_modifiers(base_damage=base_damage, defender=defender)
        updated_defender = replace(defender, hp_current=max(0, defender.hp_current - damage))
        return (
            updated_defender,
            f"{label} hits for **{damage}** damage.",
            {
                "result": "hit",
                "hit_roll_pct": round(roll, 2),
                "final_hit_pct": round(hit_chance, 2),
                **details,
            },
            True,
        )

    graze = random.random() < 0.5
    damage, details = _damage_after_modifiers(base_damage=base_damage, defender=defender)
    graze_damage = max(1, int(round(damage * 0.25))) if graze else 0
    updated_defender = defender
    result_text = f"{label} misses."
    if graze_damage > 0:
        updated_defender = replace(defender, hp_current=max(0, defender.hp_current - graze_damage))
        result_text = f"{label} misses clean, but still grazes for **{graze_damage}** damage."
    return (
        updated_defender,
        result_text,
        {
            "result": "graze" if graze_damage > 0 else "miss",
            "hit_roll_pct": round(roll, 2),
            "final_hit_pct": round(hit_chance, 2),
            "graze_roll": graze,
            "graze_damage": graze_damage,
            **details,
        },
        False,
    )


def _perform_strike(
    *,
    attacker: CombatEntity,
    defender: CombatEntity,
    label: str,
    base_hit_pct: float,
    power_multiplier: float,
) -> tuple[CombatEntity, str, dict[str, object], bool]:
    return _resolve_hit(
        attacker=attacker,
        defender=defender,
        base_damage=attacker.power * power_multiplier,
        base_hit_pct=base_hit_pct,
        label=label,
    )


def _enemy_choice(enemy: CombatEntity) -> CombatChoice:
    available_abilities = [
        ability_key
        for ability_key in enemy.abilities
        if enemy.cooldowns.get(ability_key, 0) <= 0
        and enemy.mana_current >= get_combat_ability(ability_key).mana_cost
    ]
    ability_weight = enemy.ability_bias if available_abilities else 0
    attack_weight = max(0, enemy.attack_bias)
    guard_weight = max(0, enemy.guard_bias)
    total_weight = max(1, ability_weight + attack_weight + guard_weight)
    roll = random.randint(1, total_weight)
    if available_abilities and roll <= ability_weight:
        return CombatChoice(action="ability", ability_key=random.choice(available_abilities))
    if roll <= ability_weight + attack_weight:
        return CombatChoice(action="strike")
    return CombatChoice(action="guard")


def _apply_guard_reduction(damage: int) -> tuple[int, int]:
    reduction_pct = random.randint(40, 60)
    reduced_damage = max(1, int(round(damage * (1 - reduction_pct / 100))))
    return reduced_damage, reduction_pct


def _format_stats_line(entity: CombatEntity) -> str:
    return (
        f"{entity.name} | HP {entity.hp_current}/{entity.hp_max} | Mana {entity.mana_current}/{entity.mana_max} | "
        f"Pow {entity.power} Def {entity.defense} Spd {entity.speed} Rei {entity.reiatsu}"
    )


def _alive_enemies(enemies: Iterable[CombatEntity]) -> list[CombatEntity]:
    return [enemy for enemy in enemies if enemy.is_alive]


def _player_action_label(choice: CombatChoice) -> str:
    if choice.action == "strike":
        return "Strike"
    if choice.action == "guard":
        return "Guard"
    if choice.action == "bandage":
        return "Bandage"
    if choice.action == "retreat":
        return "Retreat"
    if choice.ability_key is not None:
        return get_combat_ability(choice.ability_key).name
    return "Ability"


def _compose_round_summary(player_lines: list[str], enemy_lines: list[str]) -> str:
    player_text = "\n".join(f"- {line}" for line in player_lines) if player_lines else "- Waiting on your move."
    enemy_text = "\n".join(f"- {line}" for line in enemy_lines) if enemy_lines else "- The enemy is reading you."
    return f"**Your Turn**\n{player_text}\n\n**Enemy Turn**\n{enemy_text}"


def _append_hit_breakdown(detail_lines: list[str], heading: str, details: dict[str, object]) -> None:
    detail_lines.append(f"{heading}:")
    detail_lines.append(
        "  "
        + (
            f"result={details['result']} "
            f"roll={details['hit_roll_pct']}% "
            f"chance={details['final_hit_pct']}%"
        )
    )
    detail_lines.append(
        "  "
        + (
            f"base={details['base_damage']} "
            f"swing={details['swing_pct']}% "
            f"crit={'yes' if details['crit'] else 'no'} "
            f"reduction={details['defender_reduction_pct']}% "
            f"final={details['final_damage']}"
        )
    )
    if int(details.get("graze_damage", 0)) > 0:
        detail_lines.append(f"  graze_damage={details['graze_damage']}")
    if "guard_reduction_pct" in details:
        detail_lines.append(
            f"  guard_reduction={details['guard_reduction_pct']}% guarded_damage={details['guarded_damage']}"
        )


def resolve_combat_round(
    session: CombatSession,
    player_choice: CombatChoice,
) -> CombatRoundOutcome:
    player = replace(session.player, cooldowns=dict(session.player.cooldowns))
    enemies = [replace(enemy, cooldowns=dict(enemy.cooldowns)) for enemy in session.enemies]
    detail_lines = [
        f"Round {session.round_number}",
        f"Player Action: {_player_action_label(player_choice)}",
        f"Player Before: {_format_stats_line(player)}",
    ]
    player_summary_parts: list[str] = []
    enemy_summary_parts: list[str] = []
    payload: dict[str, object] = {
        "player_action": {"action": player_choice.action, "ability_key": player_choice.ability_key},
        "events": [],
    }

    for enemy in enemies:
        detail_lines.append(f"Enemy Before: {_format_stats_line(enemy)}")

    if player_choice.action == "retreat" and player.cooldowns.get("retreat", 0) > 0:
        player_summary_parts.append("Retreat is still on cooldown, so you hold your ground instead.")
        detail_lines.append(f"Retreat blocked: cooldown {player.cooldowns['retreat']}")
        player_choice = CombatChoice(action="guard", reason="Retreat on cooldown")

    player_guarding = player_choice.action == "guard"
    player_was_hit = False

    if player_choice.action == "retreat":
        retreat_chance = _clamp(
            0.35 + (player.speed - max(enemy.speed for enemy in enemies)) * 0.05,
            low=0.15,
            high=0.75,
        )
        retreat_roll = random.random()
        payload["retreat"] = {
            "chance_pct": round(retreat_chance * 100, 2),
            "roll_pct": round(retreat_roll * 100, 2),
        }
        if retreat_roll <= retreat_chance:
            player_summary_parts.append("You find one narrow opening and break away clean.")
            detail_lines.append(
                f"Retreat: success with roll {round(retreat_roll * 100, 2)} <= {round(retreat_chance * 100, 2)}"
            )
            player, mana_restored = _regen_mana(player)
            detail_lines.append(f"End-turn mana regen: +{mana_restored}")
            updated_session = replace(
                session,
                player=player,
                enemies=tuple(enemies),
                last_round_summary=_compose_round_summary(player_summary_parts, enemy_summary_parts),
            )
            return CombatRoundOutcome(
                session=updated_session,
                log_event=CombatLogEvent(
                    turn_number=session.round_number,
                    summary_text=_compose_round_summary(player_summary_parts, enemy_summary_parts),
                    detail_text="\n".join(detail_lines),
                    payload=payload,
                ),
                resolution_type="retreated",
                resolution_title=f"You Break Away from {session.enemy_name}",
                resolution_description=f"You break away from **{session.enemy_name}** before the alley can swallow the whole fight.",
                xp_reward=session.reward_xp_lose,
            )
        player_summary_parts.append("You try to break away, but the enemy stays on you.")
        detail_lines.append(
            f"Retreat: failed with roll {round(retreat_roll * 100, 2)} > {round(retreat_chance * 100, 2)}"
        )
        player.cooldowns["retreat"] = 3

    enemy_choices = {enemy.entity_id: _enemy_choice(enemy) for enemy in enemies if enemy.is_alive}
    payload["enemy_actions"] = {enemy_id: {"action": choice.action} for enemy_id, choice in enemy_choices.items()}
    player_acts_first = _initiative_score(player) >= max(_initiative_score(enemy) for enemy in enemies if enemy.is_alive)
    player_bonus_turn = _bonus_turn_triggered(player)
    payload["player_initiative_first"] = player_acts_first
    payload["player_bonus_turn"] = player_bonus_turn
    detail_lines.append(f"Initiative: player_first={player_acts_first}")
    detail_lines.append(f"Bonus turn roll: triggered={player_bonus_turn}")

    def _resolve_player_action_once(action_choice: CombatChoice) -> None:
        nonlocal player, enemies
        alive_enemies = _alive_enemies(enemies)
        if not alive_enemies:
            return
        if action_choice.action == "guard":
            player_summary_parts.append("You brace yourself behind a guarded stance.")
            detail_lines.append("Player chooses Guard.")
            return
        if action_choice.action == "bandage":
            player_summary_parts.append(action_choice.reason or "You tighten a bandage and steal a breath.")
            detail_lines.append(f"Player uses bandage: {action_choice.reason or 'healed'}")
            return
        if action_choice.action == "retreat":
            return
        if action_choice.action == "strike":
            target = alive_enemies[0]
            updated_target, text, details, _ = _perform_strike(
                attacker=player,
                defender=target,
                label="You strike",
                base_hit_pct=100.0,
                power_multiplier=1.0,
            )
            enemies = [updated_target if enemy.entity_id == updated_target.entity_id else enemy for enemy in enemies]
            player_summary_parts.append(text)
            _append_hit_breakdown(detail_lines, "Player Strike", details)
            payload["events"].append({"kind": "player_strike", "target": target.entity_id, "details": details})
            return

        if action_choice.action == "ability" and action_choice.ability_key is not None:
            ability = get_combat_ability(action_choice.ability_key)
            if player.level < ability.unlock_level:
                player_summary_parts.append(f"You reach for {ability.name}, but you are not ready for it yet.")
                detail_lines.append(f"Ability blocked: level {player.level} < unlock {ability.unlock_level}")
                return
            if player.cooldowns.get(ability.key, 0) > 0:
                player_summary_parts.append(f"{ability.name} is still cooling down.")
                detail_lines.append(f"Ability blocked: cooldown {player.cooldowns[ability.key]}")
                return
            if player.mana_current < ability.mana_cost:
                player_summary_parts.append(f"You do not have enough mana for {ability.name}.")
                detail_lines.append(f"Ability blocked: mana {player.mana_current} < {ability.mana_cost}")
                return

            player = replace(player, mana_current=player.mana_current - ability.mana_cost)
            player.cooldowns[ability.key] = ability.cooldown_turns
            target_pool = _alive_enemies(enemies) if ability.targeting == "all" else [_alive_enemies(enemies)[0]]
            player_summary_parts.append(f"You unleash **{ability.name}**.")
            detail_lines.append(
                f"Ability cast: {ability.name} mana_cost={ability.mana_cost} cooldown={ability.cooldown_turns}"
            )
            for target in list(target_pool):
                current_target = next(enemy for enemy in enemies if enemy.entity_id == target.entity_id)
                for hit_index in range(ability.hits):
                    updated_target, text, details, _ = _perform_strike(
                        attacker=player,
                        defender=current_target,
                        label=f"{ability.name} hit {hit_index + 1} on {current_target.name}",
                        base_hit_pct=ability.hit_chance,
                        power_multiplier=ability.power_multiplier,
                    )
                    current_target = updated_target
                    player_summary_parts.append(text)
                    _append_hit_breakdown(detail_lines, f"Ability {ability.name} hit {hit_index + 1}", details)
                    payload["events"].append(
                        {
                            "kind": "player_ability_hit",
                            "ability": ability.key,
                            "target": current_target.entity_id,
                            "details": details,
                        }
                    )
                    if current_target.hp_current <= 0:
                        break
                enemies = [current_target if enemy.entity_id == current_target.entity_id else enemy for enemy in enemies]

    def _resolve_enemy_actions() -> None:
        nonlocal player, enemies, player_was_hit
        for enemy in _alive_enemies(enemies):
            enemy_choice = enemy_choices[enemy.entity_id]
            if enemy_choice.action == "guard":
                enemy_summary_parts.append(f"**{enemy.name}** guards and waits for an opening.")
                detail_lines.append(f"{enemy.name} chooses Guard.")
                continue
            if enemy_choice.action == "ability" and enemy_choice.ability_key is not None:
                ability = get_combat_ability(enemy_choice.ability_key)
                enemy = replace(
                    enemy,
                    mana_current=max(0, enemy.mana_current - ability.mana_cost),
                    cooldowns={**enemy.cooldowns, ability.key: ability.cooldown_turns},
                )
                enemies = [enemy if candidate.entity_id == enemy.entity_id else candidate for candidate in enemies]
                enemy_summary_parts.append(f"**{enemy.name}** uses **{ability.name}**.")
                detail_lines.append(
                    f"Enemy ability: {enemy.name} casts {ability.name} mana_cost={ability.mana_cost} cooldown={ability.cooldown_turns}"
                )
                for hit_index in range(ability.hits):
                    updated_player, text, details, hit_landed = _perform_strike(
                        attacker=enemy,
                        defender=player,
                        label=f"**{enemy.name}** {ability.name} hit {hit_index + 1}",
                        base_hit_pct=ability.hit_chance,
                        power_multiplier=ability.power_multiplier,
                    )
                    if hit_landed and player_guarding:
                        reduced_damage, reduction_pct = _apply_guard_reduction(int(details["final_damage"]))
                        updated_player = replace(player, hp_current=max(0, player.hp_current - reduced_damage))
                        text = f"**{enemy.name}** crashes into your guard for **{reduced_damage}** damage with {ability.name}."
                        details["guard_reduction_pct"] = reduction_pct
                        details["guarded_damage"] = reduced_damage
                        if random.random() < 0.10:
                            updated_enemy, counter_text, counter_details, _ = _perform_strike(
                                attacker=player,
                                defender=enemy,
                                label="You counter",
                                base_hit_pct=100.0,
                                power_multiplier=2.0,
                            )
                            enemy = updated_enemy
                            enemies = [enemy if candidate.entity_id == enemy.entity_id else candidate for candidate in enemies]
                            player_summary_parts.append(counter_text)
                            _append_hit_breakdown(detail_lines, "Guard Counter", counter_details)
                            payload["events"].append(
                                {"kind": "guard_counter", "target": enemy.entity_id, "details": counter_details}
                            )
                        player_was_hit = True
                    elif hit_landed:
                        player_was_hit = True
                    player = updated_player
                    enemy_summary_parts.append(text)
                    _append_hit_breakdown(detail_lines, f"Enemy Ability | {enemy.name} | {ability.name} | Hit {hit_index + 1}", details)
                    payload["events"].append(
                        {
                            "kind": "enemy_ability_hit",
                            "enemy": enemy.entity_id,
                            "ability": ability.key,
                            "details": details,
                        }
                    )
                    if player.hp_current <= 0:
                        return
                continue
            updated_player, text, details, hit_landed = _perform_strike(
                attacker=enemy,
                defender=player,
                label=f"**{enemy.name}** strikes",
                base_hit_pct=100.0,
                power_multiplier=1.0,
            )
            if hit_landed and player_guarding:
                reduced_damage, reduction_pct = _apply_guard_reduction(int(details["final_damage"]))
                updated_player = replace(player, hp_current=max(0, player.hp_current - reduced_damage))
                text = f"**{enemy.name}** breaks on your guard for **{reduced_damage}** damage."
                details["guard_reduction_pct"] = reduction_pct
                details["guarded_damage"] = reduced_damage
                if random.random() < 0.10:
                    updated_enemy, counter_text, counter_details, _ = _perform_strike(
                        attacker=player,
                        defender=enemy,
                        label="You counter",
                        base_hit_pct=100.0,
                        power_multiplier=2.0,
                    )
                    enemies = [updated_enemy if candidate.entity_id == updated_enemy.entity_id else candidate for candidate in enemies]
                    player_summary_parts.append(counter_text)
                    _append_hit_breakdown(detail_lines, "Guard Counter", counter_details)
                    payload["events"].append({"kind": "guard_counter", "target": enemy.entity_id, "details": counter_details})
                player_was_hit = True
            elif hit_landed:
                player_was_hit = True
            player = updated_player
            enemy_summary_parts.append(text)
            _append_hit_breakdown(detail_lines, f"Enemy Action | {enemy.name}", details)
            payload["events"].append({"kind": "enemy_action", "enemy": enemy.entity_id, "details": details})
            if player.hp_current <= 0:
                return

    if player_acts_first:
        _resolve_player_action_once(player_choice)
        if player_bonus_turn and player_choice.action in {"strike", "ability"} and _alive_enemies(enemies):
            player_summary_parts.append("Speed opens a second window before the enemy can reset.")
            detail_lines.append("Bonus turn consumed: player follow-up")
            _resolve_player_action_once(player_choice)
        if not _alive_enemies(enemies):
            player, mana_restored = _regen_mana(player, guarded_breathing=player_guarding and not player_was_hit)
            if player_guarding and not player_was_hit and mana_restored > 0:
                player_summary_parts.append("Your guard holds clean, and a quiet breath pulls a little reiatsu back into place.")
            detail_lines.append(f"End-turn mana regen: +{mana_restored}")
            updated_session = replace(
                session,
                player=player,
                enemies=tuple(enemies),
                last_round_summary=_compose_round_summary(player_summary_parts, enemy_summary_parts),
            )
            return CombatRoundOutcome(
                session=updated_session,
                log_event=CombatLogEvent(
                    session.round_number,
                    _compose_round_summary(player_summary_parts, enemy_summary_parts),
                    "\n".join(detail_lines),
                    payload,
                ),
                resolution_type="victory",
                resolution_title=session.resolution_title,
                resolution_description=session.resolution_description,
                xp_reward=session.reward_xp_win,
            )
        _resolve_enemy_actions()
    else:
        _resolve_enemy_actions()
        if player.hp_current > 0:
            _resolve_player_action_once(player_choice)
            if player_bonus_turn and player_choice.action in {"strike", "ability"} and _alive_enemies(enemies):
                player_summary_parts.append("Speed steals a follow-up before the enemy can settle.")
                detail_lines.append("Bonus turn consumed: player follow-up")
                _resolve_player_action_once(player_choice)

    player.cooldowns = _decrement_cooldowns(player.cooldowns)
    enemies = [replace(enemy, cooldowns=_decrement_cooldowns(enemy.cooldowns)) for enemy in enemies]
    player, mana_restored = _regen_mana(player, guarded_breathing=player_guarding and not player_was_hit)
    if player_guarding and not player_was_hit and mana_restored > 0:
        player_summary_parts.append("Your guard buys a small break, and your reiatsu steadies on the inhale.")
    detail_lines.append(f"Cooldowns after turn: {player.cooldowns}")
    for enemy in enemies:
        if enemy.cooldowns:
            detail_lines.append(f"{enemy.name} cooldowns after turn: {enemy.cooldowns}")
    detail_lines.append(f"End-turn mana regen: +{mana_restored}")

    resolution_type = None
    resolution_title = None
    resolution_description = None
    xp_reward = 0
    if player.hp_current <= 0:
        resolution_type = "defeat"
        resolution_title = f"{session.enemy_name} Leaves You Reeling"
        resolution_description = f"The fight turns against you, and **{session.enemy_name}** is still standing when your vision finally goes black."
        xp_reward = session.reward_xp_lose
    elif not _alive_enemies(enemies):
        resolution_type = "victory"
        resolution_title = session.resolution_title
        resolution_description = session.resolution_description
        xp_reward = session.reward_xp_win

    updated_session = replace(
        session,
        player=player,
        enemies=tuple(enemies),
        round_number=session.round_number + (0 if resolution_type is not None else 1),
        last_round_summary=_compose_round_summary(player_summary_parts, enemy_summary_parts),
    )
    return CombatRoundOutcome(
        session=updated_session,
        log_event=CombatLogEvent(
            session.round_number,
            _compose_round_summary(player_summary_parts, enemy_summary_parts),
            "\n".join(detail_lines),
            payload,
        ),
        resolution_type=resolution_type,
        resolution_title=resolution_title,
        resolution_description=resolution_description,
        xp_reward=xp_reward,
    )
