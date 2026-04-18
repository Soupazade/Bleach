from __future__ import annotations

import random
import unittest

from src.data.locations import RUKONGAI_MARKET, RUKONGAI_OUTSKIRTS, RUKONGAI_STREETS
from src.data.work import get_work_definition, get_work_options_for_location, is_work_location_supported
from src.services.work_service import calculate_work_payout


class WorkServiceTests(unittest.TestCase):
    def test_supported_work_locations_are_market_and_streets_only(self) -> None:
        self.assertTrue(is_work_location_supported(RUKONGAI_STREETS.key))
        self.assertTrue(is_work_location_supported(RUKONGAI_MARKET.key))
        self.assertFalse(is_work_location_supported(RUKONGAI_OUTSKIRTS.key))

    def test_market_and_street_pools_exist(self) -> None:
        self.assertGreater(len(get_work_options_for_location(RUKONGAI_STREETS.key)), 0)
        self.assertGreater(len(get_work_options_for_location(RUKONGAI_MARKET.key)), 0)

    def test_shady_jobs_pay_better_with_bad_reputation(self) -> None:
        job = get_work_definition("market_move_hot_goods")
        clean_rng = random.Random(7)
        dirty_rng = random.Random(7)

        clean_pay, clean_bonus = calculate_work_payout(
            work=job,
            reputation_value=20,
            rng=clean_rng,
        )
        dirty_pay, dirty_bonus = calculate_work_payout(
            work=job,
            reputation_value=-60,
            rng=dirty_rng,
        )

        self.assertGreater(dirty_pay, clean_pay)
        self.assertGreater(dirty_bonus, clean_bonus)

    def test_legit_jobs_pay_better_with_good_reputation(self) -> None:
        job = get_work_definition("market_carry_crates")
        rough_rng = random.Random(11)
        trusted_rng = random.Random(11)

        rough_pay, rough_bonus = calculate_work_payout(
            work=job,
            reputation_value=-20,
            rng=rough_rng,
        )
        trusted_pay, trusted_bonus = calculate_work_payout(
            work=job,
            reputation_value=50,
            rng=trusted_rng,
        )

        self.assertGreater(trusted_pay, rough_pay)
        self.assertGreater(trusted_bonus, rough_bonus)


if __name__ == "__main__":
    unittest.main()
