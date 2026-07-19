from __future__ import annotations

import unittest

from envsolve.tools.p5_freeze import build


class P5FreezeTests(unittest.TestCase):
    def test_freeze_reconstructs_expected_pass_curve(self) -> None:
        freeze = build()

        self.assertTrue(freeze["scope"]["p5_complete"])
        self.assertEqual(freeze["validation"]["official_pass"], 2)
        self.assertEqual(freeze["validation"]["robust_pass"], 2)
        self.assertEqual(
            freeze["validation"]["level_counts"]["V6"],
            {"pass": 4, "fail": 0, "unknown": 1},
        )
        self.assertEqual(
            freeze["validation"]["clean_replay_provenance"],
            {"legacy-egg-link": 1, "pep610-direct-url": 3},
        )
        self.assertFalse(freeze["integrity"]["development_unknown_promoted_to_pass"])


if __name__ == "__main__":
    unittest.main()
