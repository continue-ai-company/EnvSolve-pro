import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experiments.tools.select_free_agent_census24 import select


class SelectFreeAgentCensusTest(unittest.TestCase):
    def test_sorted_seeded_sample_is_repeatable_and_outcome_blind(self):
        with TemporaryDirectory() as directory:
            universe = Path(directory) / "universe.jsonl"
            rows = [
                {
                    "case_id": f"case-{index:02d}",
                    "repository": f"owner/repo-{index}",
                    "revision": str(index) * 40,
                    "language": "python",
                    "split": "dev",
                    "source_split": "consumed",
                    "tags": [],
                }
                for index in reversed(range(10))
            ]
            universe.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            first = select(universe, seed=7, size=4)
            second = select(universe, seed=7, size=4)
            self.assertEqual(first, second)
            self.assertEqual([row["position"] for row in first], [1, 2, 3, 4])
            self.assertEqual(len({row["case_id"] for row in first}), 4)
            self.assertTrue(
                all(row["split"] == "dev-pro-free-agent-census24-v1" for row in first)
            )

    def test_duplicate_ids_are_rejected(self):
        with TemporaryDirectory() as directory:
            universe = Path(directory) / "universe.jsonl"
            universe.write_text(
                '{"case_id":"same"}\n{"case_id":"same"}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                select(universe, seed=1, size=1)
