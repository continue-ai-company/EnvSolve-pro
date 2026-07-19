from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_jsonl
from envsolve_harness.utils.provenance import sha256_file
from experiments.tools.freeze_paired_qualification import (
    build_qualification_outputs,
    write_qualification_outputs,
)


class FreezePairedQualificationTest(unittest.TestCase):
    def _fixture(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory)
        source = root / "pool.jsonl"
        write_jsonl(
            source,
            [
                {
                    "case_id": f"owner/repo-{index}@abc",
                    "repository": f"owner/repo-{index}",
                    "revision": "abc",
                    "split": "untouched",
                }
                for index in range(6)
            ],
        )
        preregistration = root / "prereg.json"
        write_json(
            preregistration,
            {
                "status": "registered_before_selection",
                "selection": {
                    "source": "pool.jsonl",
                    "source_sha256": sha256_file(source),
                    "source_count": 6,
                    "count": 2,
                    "salt": "fixture-salt",
                    "algorithm": "ascending SHA256(salt + NUL + case_id)",
                    "metadata_only": True,
                    "selected_path": "selected.jsonl",
                    "remaining_path": "remaining.jsonl",
                    "provenance_path": "selection.json",
                    "selected_split": "dev-selected",
                    "remaining_split": "still-untouched",
                },
                "schedule": {
                    "output_path": "schedule.json",
                    "run_prefix": "qualification",
                    "methods": ["control", "treatment"],
                    "model": "provider/model",
                    "seed": 0,
                    "episode_timeout_seconds": 30,
                },
            },
        )
        return root, preregistration

    def test_materializes_deterministic_disjoint_selection_and_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, preregistration = self._fixture(directory)
            outputs = build_qualification_outputs(root, preregistration)
            write_qualification_outputs(outputs)
            selected = read_jsonl(root / "selected.jsonl")
            remaining = read_jsonl(root / "remaining.jsonl")
            schedule = read_json(root / "schedule.json")
            expected = sorted(
                [*selected, *remaining],
                key=lambda row: hashlib.sha256(
                    ("fixture-salt\0" + row["case_id"]).encode()
                ).hexdigest(),
            )[:2]

            self.assertEqual({row["case_id"] for row in selected}, {row["case_id"] for row in expected})
            self.assertFalse(
                {row["case_id"] for row in selected}
                & {row["case_id"] for row in remaining}
            )
            self.assertEqual(len(schedule["episodes"]), 4)
            self.assertEqual(
                [episode["position"] for episode in schedule["episodes"]],
                [1, 2, 3, 4],
            )
            for pair_index in (1, 2):
                self.assertEqual(
                    {
                        episode["method"]
                        for episode in schedule["episodes"]
                        if episode["pair_index"] == pair_index
                    },
                    {"control", "treatment"},
                )
            self.assertEqual(
                schedule["selection_provenance_sha256"],
                sha256_file(root / "selection.json"),
            )

    def test_refuses_source_drift_and_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, preregistration = self._fixture(directory)
            outputs = build_qualification_outputs(root, preregistration)
            write_qualification_outputs(outputs)
            with self.assertRaises(FileExistsError):
                write_qualification_outputs(outputs)
            (root / "pool.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source pool hash"):
                build_qualification_outputs(root, preregistration)


if __name__ == "__main__":
    unittest.main()
