from __future__ import annotations

import unittest

from src.data.game_constants import SOUL_ROLE_ID
from src.data.locations import RUKONGAI_MARKET, RUKONGAI_TRAINING_YARD
from src.services.location_service import resolve_location_role, role_matches_location
from src.services.role_service import remove_player_roles, sync_member_location_role


class FakeRole:
    def __init__(self, role_id: int, name: str, position: int = 0) -> None:
        self.id = role_id
        self.name = name
        self.position = position


class FakeGuild:
    def __init__(self, roles: list[FakeRole]) -> None:
        self.roles = roles

    def get_role(self, role_id: int) -> FakeRole | None:
        for role in self.roles:
            if role.id == role_id:
                return role
        return None


class FakeMember:
    def __init__(self, guild: FakeGuild, roles: list[FakeRole]) -> None:
        self.guild = guild
        self.roles = roles[:]

    async def add_roles(self, *roles: FakeRole, reason: str) -> None:
        del reason
        for role in roles:
            if all(existing.id != role.id for existing in self.roles):
                self.roles.append(role)

    async def remove_roles(self, *roles: FakeRole, reason: str) -> None:
        del reason
        removed_ids = {role.id for role in roles}
        self.roles = [role for role in self.roles if role.id not in removed_ids]


class LocationRoleTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_location_role_matches_normalized_name(self) -> None:
        market_role = FakeRole(2001, "Rukongai-Market", position=4)
        guild = FakeGuild([market_role])

        resolved_role = resolve_location_role(guild, RUKONGAI_MARKET)

        self.assertIs(resolved_role, market_role)

    async def test_sync_member_location_role_removes_old_location_and_adds_target(self) -> None:
        outskirts_role = FakeRole(2002, "Rukongai_Outskirts", position=3)
        market_role = FakeRole(2003, "Rukongai-Market", position=4)
        misc_role = FakeRole(9999, "Soul Reaper", position=1)
        guild = FakeGuild([outskirts_role, market_role, misc_role])
        member = FakeMember(guild, [outskirts_role, misc_role])

        summary, warning = await sync_member_location_role(
            member,
            RUKONGAI_MARKET,
            reason="Travel complete",
        )

        self.assertIsNone(warning)
        self.assertIsNotNone(summary)
        self.assertCountEqual(
            [role.name for role in member.roles],
            ["Rukongai-Market", "Soul Reaper"],
        )

    async def test_sync_member_location_role_preserves_existing_target_match(self) -> None:
        market_role = FakeRole(2004, "Rukongai Market", position=4)
        training_role = FakeRole(2005, "rukongai-training-yard", position=5)
        guild = FakeGuild([market_role, training_role])
        member = FakeMember(guild, [training_role])

        summary, warning = await sync_member_location_role(
            member,
            RUKONGAI_TRAINING_YARD,
            reason="Travel complete",
        )

        self.assertIsNone(warning)
        self.assertIsNone(summary)
        self.assertEqual([role.name for role in member.roles], ["rukongai-training-yard"])
        self.assertTrue(role_matches_location(training_role, RUKONGAI_TRAINING_YARD))

    async def test_remove_player_roles_removes_soul_and_location_roles(self) -> None:
        soul_role = FakeRole(SOUL_ROLE_ID, "Soul", position=10)
        training_role = FakeRole(2006, "Rukongai Training Yard", position=5)
        misc_role = FakeRole(9998, "Captain", position=20)
        guild = FakeGuild([soul_role, training_role, misc_role])
        member = FakeMember(guild, [soul_role, training_role, misc_role])

        summary, warning = await remove_player_roles(member, reason="Reset player")

        self.assertIsNone(warning)
        self.assertIsNotNone(summary)
        self.assertEqual([role.name for role in member.roles], ["Captain"])


if __name__ == "__main__":
    unittest.main()
