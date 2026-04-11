from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from asyncpg import Pool

from src.data.items import ItemDefinition, get_item_definition
from src.models.inventory import PlayerInventoryItem
from src.models.player import PlayerProfile
from src.services.combat_service import fetch_active_combat_record
from src.services.inventory_service import (
    consume_inventory_item_for_connection,
    fetch_inventory_records,
)
from src.services.player_service import get_or_sync_player_record, update_player_record


@dataclass(slots=True)
class UseItemResult:
    status: Literal["used", "missing_profile", "missing_item", "active_combat", "nothing_to_heal", "nothing_to_restore"]
    player: PlayerProfile | None = None
    item: PlayerInventoryItem | None = None
    item_definition: ItemDefinition | None = None
    quantity_remaining: int = 0
    healed_amount: int = 0
    restored_stamina: int = 0


async def use_item(
    pool: Pool | None,
    *,
    user_id: int,
    item_key: str,
) -> UseItemResult:
    if pool is None:
        return UseItemResult(status="missing_profile")

    item_definition = get_item_definition(item_key)

    async with pool.acquire() as connection:
        async with connection.transaction():
            player_sync = await get_or_sync_player_record(connection, user_id, for_update=True)
            if player_sync is None:
                return UseItemResult(status="missing_profile", item_definition=item_definition)

            if item_definition.use_out_of_combat_only:
                active_combat_record = await fetch_active_combat_record(connection, user_id, for_update=True)
                if active_combat_record is not None:
                    return UseItemResult(
                        status="active_combat",
                        player=PlayerProfile.from_record(player_sync.record),
                        item_definition=item_definition,
                    )

            inventory_records = await fetch_inventory_records(connection, user_id, for_update=True)
            inventory_items = [PlayerInventoryItem.from_record(record) for record in inventory_records]
            item = next((entry for entry in inventory_items if entry.item_key == item_key), None)
            if item is None:
                return UseItemResult(
                    status="missing_item",
                    player=PlayerProfile.from_record(player_sync.record),
                    item_definition=item_definition,
                )

            player = PlayerProfile.from_record(player_sync.record)
            if item_definition.heal_hp_pct > 0:
                if player.hp_current >= player.hp_max:
                    return UseItemResult(
                        status="nothing_to_heal",
                        player=player,
                        item=item,
                        item_definition=item_definition,
                        quantity_remaining=item.quantity,
                    )

                heal_amount = max(1, math.ceil(player.hp_max * (item_definition.heal_hp_pct / 100)))
                actual_heal = min(heal_amount, player.hp_max - player.hp_current)
                consumed = await consume_inventory_item_for_connection(
                    connection,
                    user_id=user_id,
                    item_key=item_key,
                    quantity=1,
                )
                if consumed <= 0:
                    return UseItemResult(
                        status="missing_item",
                        player=player,
                        item_definition=item_definition,
                    )

                updates: dict[str, object] = {
                    "hp_current": min(player.hp_max, player.hp_current + actual_heal),
                }
                if player.is_resting and player.rest_hp_snapshot is not None:
                    updates["rest_hp_snapshot"] = min(
                        player.hp_max,
                        player.rest_hp_snapshot + actual_heal,
                    )

                updated_record = await update_player_record(connection, user_id, updates)
                updated_player = PlayerProfile.from_record(updated_record)
                return UseItemResult(
                    status="used",
                    player=updated_player,
                    item=item,
                    item_definition=item_definition,
                    quantity_remaining=max(0, item.quantity - 1),
                    healed_amount=actual_heal,
                )

            if item_definition.restore_stamina_flat > 0:
                if player.stamina_current >= player.stamina_max:
                    return UseItemResult(
                        status="nothing_to_restore",
                        player=player,
                        item=item,
                        item_definition=item_definition,
                        quantity_remaining=item.quantity,
                    )

                actual_restore = min(
                    item_definition.restore_stamina_flat,
                    player.stamina_max - player.stamina_current,
                )
                consumed = await consume_inventory_item_for_connection(
                    connection,
                    user_id=user_id,
                    item_key=item_key,
                    quantity=1,
                )
                if consumed <= 0:
                    return UseItemResult(
                        status="missing_item",
                        player=player,
                        item_definition=item_definition,
                    )

                updates: dict[str, object] = {
                    "stamina_current": min(player.stamina_max, player.stamina_current + actual_restore),
                }
                if player.is_resting and player.rest_stamina_snapshot is not None:
                    updates["rest_stamina_snapshot"] = min(
                        player.stamina_max,
                        player.rest_stamina_snapshot + actual_restore,
                    )

                updated_record = await update_player_record(connection, user_id, updates)
                updated_player = PlayerProfile.from_record(updated_record)
                return UseItemResult(
                    status="used",
                    player=updated_player,
                    item=item,
                    item_definition=item_definition,
                    quantity_remaining=max(0, item.quantity - 1),
                    restored_stamina=actual_restore,
                )

    return UseItemResult(status="missing_item", item_definition=item_definition)
