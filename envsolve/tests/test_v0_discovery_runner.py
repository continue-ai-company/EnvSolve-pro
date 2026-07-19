from __future__ import annotations

import unittest

from experiments.run_v0_discovery import build_schedule


class V0DiscoveryRunnerTests(unittest.TestCase):
    def test_schedule_alternates_condition_order_per_case(self) -> None:
        records = [
            {"case_id": "one", "repository": "owner/one", "revision": "a"},
            {"case_id": "two", "repository": "owner/two", "revision": "b"},
        ]
        schedule = build_schedule(records)
        self.assertEqual(
            [(item["case_id"], item["condition"]) for item in schedule],
            [
                ("one", "envsolve_v0"),
                ("one", "freeagent"),
                ("two", "freeagent"),
                ("two", "envsolve_v0"),
            ],
        )
        self.assertEqual(len({(item["case_id"], item["condition"]) for item in schedule}), 4)


if __name__ == "__main__":
    unittest.main()
