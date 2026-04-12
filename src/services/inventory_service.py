from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from asyncpg import Connection, Pool, Record

from src.models.inventory import PlayerInventoryItem


PLAYER_INVENTORY_COLUMNS = """
    id,
    user_id,
    item_key,
    item_name,
    item_description,
    item_type,
    rarity,
    quantity,
    stackable,
    source_text,
    metadata,
    created_at,
    updated_at
"""


@dataclass(slots=True)
class InventorySummary:
    stack_count: int
    total_quantity: int


async def fetch_inventory_records(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> list[Record]:
    lock_clause = " FOR UPDATE" if for_update else ""
    return await connection.fetch(
        f"""
        SELECT {PLAYER_INVENTORY_COLUMNS}
        FROM player_inventory_items
        WHERE user_id = $1
        ORDER BY item_name ASC, created_at ASC
        {lock_clause}
        """,
        user_id,
    )


async def list_player_inventory_for_connection(
    connection: Connection,
    user_id: int,
    *,
    for_update: bool = False,
) -> list[PlayerInventoryItem]:
    records = await fetch_inventory_records(connection, user_id, for_update=for_update)
    return [PlayerInventoryItem.from_record(record) for record in records]


async def list_player_inventory(
    pool: Pool | None,
    user_id: int,
) -> list[PlayerInventoryItem]:
    if pool is None:
        return []

    async with pool.acquire() as connection:
        return await list_player_inventory_for_connection(connection, user_id)


async def grant_inventory_item_for_connection(
    connection: Connection,
    *,
    user_id: int,
    item_key: str,
    item_name: str,
    quantity: int = 1,
    item_description: str = "",
    item_type: str = "misc",
    rarity: str = "common",
    stackable: bool = True,
    source_text: str = "",
    metadata: dict[str, Any] | None = None,
) -> PlayerInventoryItem:
    normalized_quantity = max(1, quantity)
    normalized_metadata = metadata or {}
    encoded_metadata = json.dumps(normalized_metadata)

    if stackable:
        existing_record = await connection.fetchrow(
            f"""
            SELECT {PLAYER_INVENTORY_COLUMNS}
            FROM player_inventory_items
            WHERE user_id = $1
              AND item_key = $2
              AND stackable = TRUE
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE
            """,
            user_id,
            item_key,
        )

        if existing_record is not None:
            updated_record = await connection.fetchrow(
                f"""
                UPDATE player_inventory_items
                SET
                    item_name = $3,
                    item_description = $4,
                    item_type = $5,
                    rarity = $6,
                    quantity = quantity + $7,
                    source_text = $8,
                    metadata = $9,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING {PLAYER_INVENTORY_COLUMNS}
                """,
                int(existing_record["id"]),
                user_id,
                item_name,
                item_description,
                item_type,
                rarity,
                normalized_quantity,
                source_text,
                encoded_metadata,
            )
            return PlayerInventoryItem.from_record(updated_record)

    record = await connection.fetchrow(
        f"""
        INSERT INTO player_inventory_items (
            user_id,
            item_key,
            item_name,
            item_description,
            item_type,
            rarity,
            quantity,
            stackable,
            source_text,
            metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING {PLAYER_INVENTORY_COLUMNS}
        """,
        user_id,
        item_key,
        item_name,
        item_description,
        item_type,
        rarity,
        normalized_quantity,
        stackable,
        source_text,
        encoded_metadata,
    )
    return PlayerInventoryItem.from_record(record)


async def grant_inventory_item(
    pool: Pool | None,
    *,
    user_id: int,
    item_key: str,
    item_name: str,
    quantity: int = 1,
    item_description: str = "",
    item_type: str = "misc",
    rarity: str = "common",
    stackable: bool = True,
    source_text: str = "",
    metadata: dict[str, Any] | None = None,
) -> PlayerInventoryItem | None:
    if pool is None:
        return None

    async with pool.acquire() as connection:
        async with connection.transaction():
            return await grant_inventory_item_for_connection(
                connection,
                user_id=user_id,
                item_key=item_key,
                item_name=item_name,
                quantity=quantity,
                item_description=item_description,
                item_type=item_type,
                rarity=rarity,
                stackable=stackable,
                source_text=source_text,
                metadata=metadata,
            )


async def consume_inventory_item_for_connection(
    connection: Connection,
    *,
    user_id: int,
    item_key: str,
    quantity: int = 1,
) -> int:
    normalized_quantity = max(1, quantity)
    record = await connection.fetchrow(
        """
        SELECT id, quantity
        FROM player_inventory_items
        WHERE user_id = $1
          AND item_key = $2
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE
        """,
        user_id,
        item_key,
    )
    if record is None:
        return 0

    current_quantity = int(record["quantity"])
    removed_quantity = min(current_quantity, normalized_quantity)
    remaining_quantity = current_quantity - removed_quantity

    if remaining_quantity <= 0:
        await connection.execute(
            """
            DELETE FROM player_inventory_items
            WHERE id = $1
            """,
            int(record["id"]),
        )
        return removed_quantity

    await connection.execute(
        """
        UPDATE player_inventory_items
        SET quantity = $2, updated_at = NOW()
        WHERE id = $1
        """,
        int(record["id"]),
        remaining_quantity,
    )
    return removed_quantity


async def consume_inventory_item(
    pool: Pool | None,
    *,
    user_id: int,
    item_key: str,
    quantity: int = 1,
) -> int:
    if pool is None:
        return 0

    async with pool.acquire() as connection:
        async with connection.transaction():
            return await consume_inventory_item_for_connection(
                connection,
                user_id=user_id,
                item_key=item_key,
                quantity=quantity,
            )


def build_inventory_summary(items: list[PlayerInventoryItem]) -> InventorySummary:
    return InventorySummary(
        stack_count=len(items),
        total_quantity=sum(item.quantity for item in items),
    )
