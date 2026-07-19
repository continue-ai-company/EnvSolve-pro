from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SALT = "envsolve-p6-v3-qualification-v1-2026-07-16"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class P6V3SelectionIntegrityTests(unittest.TestCase):
    def test_selection_is_deterministic_disjoint_and_outcome_blind(self) -> None:
        source = read_jsonl(ROOT / "experiments/cases/train_untouched201.jsonl")
        selected = read_jsonl(
            ROOT / "experiments/cases/dev_v3_qualification5.jsonl"
        )
        remaining = read_jsonl(
            ROOT
            / "experiments/cases/train_untouched_after_v3_qualification196.jsonl"
        )
        expected = sorted(
            source,
            key=lambda row: hashlib.sha256(
                (SALT + "\0" + str(row["case_id"])).encode()
            ).hexdigest(),
        )[:5]
        selected_ids = {row["case_id"] for row in selected}
        remaining_ids = {row["case_id"] for row in remaining}

        self.assertEqual(selected_ids, {row["case_id"] for row in expected})
        self.assertEqual(len(selected), 5)
        self.assertEqual(len(remaining), 196)
        self.assertFalse(selected_ids & remaining_ids)
        self.assertEqual(
            selected_ids | remaining_ids,
            {row["case_id"] for row in source},
        )
        self.assertTrue(
            all(row["split"] == "dev-v3-qualification-5" for row in selected)
        )

    def test_selection_provenance_is_hash_chained_to_preregistration(self) -> None:
        preregistration = (
            ROOT
            / "experiments/validations/p6_v3_unseen_dev5_preregistration.json"
        )
        provenance = json.loads(
            (
                ROOT
                / "experiments/validations/p6_v3_unseen_dev5_selection.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            provenance["preregistration_sha256"],
            hashlib.sha256(preregistration.read_bytes()).hexdigest(),
        )

    def test_schedule_pairs_each_case_once_per_method(self) -> None:
        selected = read_jsonl(
            ROOT / "experiments/cases/dev_v3_qualification5.jsonl"
        )
        schedule = json.loads(
            (
                ROOT
                / "experiments/validations/p6_v3_unseen_dev5_schedule.json"
            ).read_text(encoding="utf-8")
        )
        episodes = schedule["episodes"]
        selected_ids = {row["case_id"] for row in selected}

        self.assertEqual(len(episodes), 10)
        self.assertEqual(
            [item["position"] for item in episodes], list(range(1, 11))
        )
        self.assertEqual(len({item["run_id"] for item in episodes}), 10)
        for case_id in selected_ids:
            methods = {
                item["method"] for item in episodes if item["case_id"] == case_id
            }
            self.assertEqual(
                methods, {"envsolve-runtime-only", "envsolve-full"}
            )
