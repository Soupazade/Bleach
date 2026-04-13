from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from src.services.inventory_service import grant_inventory_item_for_connection


def _build_inventory_record(
    *,
    record_id: int,
    user_id: int,
    item_key: str,
    item_name: str,
    quantity: int,
    metadata: str | dict[str, object] | None = None,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "id": record_id,
        "user_id": user_id,
        "item_key": item_key,
        "item_name": item_name,
        "item_description": "desc",
        "item_type": "material",
        "rarity": "common",
        "quantity": quantity,
        "stackable": True,
        "source_text": "Rukongai Streets",
        "metadata": metadata if metadata is not None else {},
        "created_at": now,
        "updated_at": now,
    }


class FakeConnection:
    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self._responses: list[dict[str, object] | None] = []

    def queue_fetchrow_response(self, response: dict[str, object] | None) -> None:
        self._responses.append(response)

    async def fetchrow(self, query: str, *args: object) -> dict[str, object] | None:
        self.fetchrow_calls.append((query, args))
        if not self._responses:
            return None
        return self._responses.pop(0)


class InventoryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_grant_stackable_item_updates_existing_stack_with_user_guard(self) -> None:
        connection = FakeConnection()
        connection.queue_fetchrow_response(
            _build_inventory_record(
                record_id=12,
                user_id=42,
                item_key="cloth_scraps",
                item_name="Cloth Scraps",
                quantity=1,
            )
        )
        connection.queue_fetchrow_response(
            _build_inventory_record(
                record_id=12,
                user_id=42,
                item_key="cloth_scraps",
                item_name="Cloth Scraps",
                quantity=3,
                metadata={"source": "explore"},
            )
        )

        item = await grant_inventory_item_for_connection(
            connection,
            user_id=42,
            item_key="cloth_scraps",
            item_name="Cloth Scraps",
            quantity=2,
            item_description="Worn fabric.",
            item_type="material",
            rarity="common",
            stackable=True,
            source_text="Rukongai Streets",
            metadata={"source": "explore"},
        )

        self.assertEqual(item.quantity, 3)
        self.assertEqual(len(connection.fetchrow_calls), 2)

        update_query, update_args = connection.fetchrow_calls[1]
        self.assertIn("WHERE id = $1", update_query)
        self.assertIn("AND user_id = $2", update_query)
        self.assertEqual(update_args[0], 12)
        self.assertEqual(update_args[1], 42)
        self.assertEqual(update_args[6], 2)
        self.assertEqual(json.loads(str(update_args[8])), {"source": "explore"})

    async def test_grant_nonexistent_stackable_item_inserts_new_row(self) -> None:
        connection = FakeConnection()
        connection.queue_fetchrow_response(None)
        connection.queue_fetchrow_response(
            _build_inventory_record(
                record_id=99,
                user_id=42,
                item_key="food_scraps",
                item_name="Food Scraps",
                quantity=2,
            )
        )

        item = await grant_inventory_item_for_connection(
            connection,
            user_id=42,
            item_key="food_scraps",
            item_name="Food Scraps",
            quantity=2,
        )

        self.assertEqual(item.id, 99)
        self.assertEqual(item.quantity, 2)
        insert_query, insert_args = connection.fetchrow_calls[1]
        self.assertIn("INSERT INTO player_inventory_items", insert_query)
        self.assertEqual(insert_args[0], 42)
        self.assertEqual(insert_args[1], "food_scraps")


if __name__ == "__main__":
    unittest.main()
