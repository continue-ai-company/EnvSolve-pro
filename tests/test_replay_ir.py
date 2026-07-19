from __future__ import annotations

import json
from pathlib import Path
import unittest

from envsolve_harness.scripts.replay_actions import (
    REPLAY_IR_POLICY,
    analyze_successful_command,
)


FIXTURE = Path(__file__).parent / "fixtures/replay_ir_v6_cases.json"


class ReplayIrCorpusTest(unittest.TestCase):
    def test_frozen_synthetic_corpus(self) -> None:
        corpus = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(corpus["policy"], REPLAY_IR_POLICY)

        for case in corpus["cases"]:
            with self.subTest(case=case["name"]):
                analysis = analyze_successful_command(case["command"])
                expected = case["expected"]
                if expected["status"] == "reject":
                    self.assertIsNotNone(analysis.unsupported_reason)
                    self.assertIn(
                        expected["reason_contains"], analysis.unsupported_reason
                    )
                elif expected["status"] == "drop":
                    self.assertIsNone(analysis.unsupported_reason)
                    self.assertTrue(analysis.dropped)
                    self.assertFalse(analysis.actions)
                else:
                    self.assertIsNone(analysis.unsupported_reason)
                    self.assertFalse(analysis.dropped)
                    self.assertEqual(
                        [action.command for action in analysis.actions],
                        expected["commands"],
                    )
                    self.assertEqual(
                        [action.kind for action in analysis.actions],
                        expected["kinds"],
                    )


if __name__ == "__main__":
    unittest.main()
