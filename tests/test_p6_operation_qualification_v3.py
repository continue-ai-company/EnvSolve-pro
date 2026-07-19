from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from envsolve_harness.runners.envsolve_p6 import METHOD_PROFILES


ROOT = Path(__file__).resolve().parents[1]
SALT = "envsolve-p6-operation-qualification-v3-2026-07-17"
SOURCE_SHA256 = "fc4fd281c00c881578b06dde83985bbd64d750249e65d12ec5ea9946b3891f62"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P6OperationQualificationV3IntegrityTests(unittest.TestCase):
    def test_q3_selection_is_deterministic_and_disjoint(self) -> None:
        source_path = (
            ROOT
            / "experiments/cases/train_untouched_after_operation_qualification_v2_186.jsonl"
        )
        source = read_jsonl(source_path)
        selected = read_jsonl(
            ROOT / "experiments/cases/dev_operation_qualification_v3_5.jsonl"
        )
        remaining = read_jsonl(
            ROOT
            / "experiments/cases/train_untouched_after_operation_qualification_v3_181.jsonl"
        )
        expected = sorted(
            source,
            key=lambda row: hashlib.sha256(
                (SALT + "\0" + str(row["case_id"])).encode()
            ).hexdigest(),
        )[:5]
        selected_ids = {row["case_id"] for row in selected}
        remaining_ids = {row["case_id"] for row in remaining}

        self.assertEqual(sha256(source_path), SOURCE_SHA256)
        self.assertEqual(selected_ids, {row["case_id"] for row in expected})
        self.assertEqual((len(selected), len(remaining)), (5, 181))
        self.assertFalse(selected_ids & remaining_ids)
        self.assertEqual(selected_ids | remaining_ids, {row["case_id"] for row in source})

    def test_q3_selection_is_hash_chained_to_preregistration(self) -> None:
        preregistration = (
            ROOT
            / "experiments/validations/p6_operation_qualification_v3_preregistration.json"
        )
        provenance = json.loads(
            (
                ROOT
                / "experiments/validations/p6_operation_qualification_v3_selection.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(provenance["preregistration_sha256"], sha256(preregistration))
        self.assertEqual(provenance["source_sha256"], SOURCE_SHA256)

    def test_q3_schedule_pairs_only_the_operation_treatment(self) -> None:
        schedule = json.loads(
            (
                ROOT
                / "experiments/validations/p6_operation_qualification_v3_schedule.json"
            ).read_text(encoding="utf-8")
        )
        episodes = schedule["episodes"]
        expected_methods = {
            "envsolve-operation",
            "envsolve-operation-ablation",
        }

        self.assertEqual([item["position"] for item in episodes], list(range(1, 11)))
        self.assertEqual(len({item["run_id"] for item in episodes}), 10)
        self.assertEqual({item["method"] for item in episodes}, expected_methods)
        for pair_index in range(1, 6):
            self.assertEqual(
                {
                    item["method"]
                    for item in episodes
                    if item["pair_index"] == pair_index
                },
                expected_methods,
            )
        self.assertEqual(
            {METHOD_PROFILES[method][0] for method in expected_methods},
            {"two-layer"},
        )
        self.assertEqual(
            {METHOD_PROFILES[method][1] for method in expected_methods},
            {"constraint-driven", "free-form"},
        )


if __name__ == "__main__":
    unittest.main()
