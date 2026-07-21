from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = ROOT / "envsolve/protocols/p5_hierarchical_verifier_freeze_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P5FreezeTests(unittest.TestCase):
    def test_freeze_records_expected_pass_curve(self) -> None:
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))

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

    def test_committed_evidence_matches_the_freeze(self) -> None:
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))

        for record in freeze["artifacts"].values():
            self.assertEqual(sha256(ROOT / record["path"]), record["sha256"])


if __name__ == "__main__":
    unittest.main()
