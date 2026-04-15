from __future__ import annotations

import unittest

from src.data.dungeons import get_first_dungeon_definition
from src.models.dungeon import DungeonLootEntry, DungeonProgressState
from src.services.dungeon_service import build_progress_update, get_room_options


class DungeonServiceTests(unittest.TestCase):
    def test_build_progress_update_merges_totals_and_loot(self) -> None:
        progress = DungeonProgressState(
            total_xp=4,
            total_kan=10,
            total_reputation=1,
            history=("You entered the tunnel.",),
            items=(DungeonLootEntry(item_key="cloth_scraps", item_name="Cloth Scraps", quantity=1),),
        )

        updated = build_progress_update(
            progress,
            xp_gain=6,
            kan_gain=12,
            reputation_gain=2,
            granted_items=(
                DungeonLootEntry(item_key="cloth_scraps", item_name="Cloth Scraps", quantity=2),
                DungeonLootEntry(item_key="ration_pack", item_name="Ration Pack", quantity=1),
            ),
            history_entry="You pushed deeper into the tunnel.",
        )

        self.assertEqual(updated.total_xp, 10)
        self.assertEqual(updated.total_kan, 22)
        self.assertEqual(updated.total_reputation, 3)
        self.assertEqual(updated.history[-1], "You pushed deeper into the tunnel.")
        loot_by_key = {item.item_key: item.quantity for item in updated.items}
        self.assertEqual(loot_by_key["cloth_scraps"], 3)
        self.assertEqual(loot_by_key["ration_pack"], 1)

    def test_get_room_options_returns_single_forward_option_for_combat_room(self) -> None:
        dungeon = get_first_dungeon_definition()
        combat_room = dungeon.rooms[1]

        options = get_room_options(combat_room)

        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].label, "Push forward")


if __name__ == "__main__":
    unittest.main()
