from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from envsolve_harness.runners.envsolve_p6 import METHOD_PROFILES


ROOT = Path(__file__).resolve().parents[1]
SALT = "envsolve-p6-operation-qualification-v1-2026-07-17"
SOURCE_SHA256 = "337f72f00b3731fe7388628a01e45f09ac07a4b3f579bc2fbdbdeddfede352ce"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P6OperationQualificationIntegrityTests(unittest.TestCase):
    def test_selection_is_deterministic_disjoint_and_outcome_blind(self) -> None:
        source_path = (
            ROOT / "experiments/cases/train_untouched_after_v3_qualification196.jsonl"
        )
        selected = read_jsonl(
            ROOT / "experiments/cases/dev_operation_qualification5.jsonl"
        )
        remaining = read_jsonl(
            ROOT
            / "experiments/cases/train_untouched_after_operation_qualification191.jsonl"
        )
        source = read_jsonl(source_path)
        self.assertEqual(sha256(source_path), SOURCE_SHA256)
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
        self.assertEqual(len(remaining), 191)
        self.assertFalse(selected_ids & remaining_ids)
        self.assertEqual(
            selected_ids | remaining_ids,
            {row["case_id"] for row in source},
        )
        self.assertTrue(
            all(row["split"] == "dev-operation-qualification-5" for row in selected)
        )

    def test_selection_is_hash_chained_to_preregistration(self) -> None:
        preregistration = (
            ROOT
            / "experiments/validations/p6_operation_qualification_preregistration.json"
        )
        provenance = json.loads(
            (
                ROOT
                / "experiments/validations/p6_operation_qualification_selection.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(provenance["preregistration_sha256"], sha256(preregistration))
        self.assertEqual(provenance["source_sha256"], SOURCE_SHA256)

    def test_schedule_pairs_only_the_operation_treatment(self) -> None:
        selected = read_jsonl(
            ROOT / "experiments/cases/dev_operation_qualification5.jsonl"
        )
        schedule = json.loads(
            (
                ROOT
                / "experiments/validations/p6_operation_qualification_schedule.json"
            ).read_text(encoding="utf-8")
        )
        episodes = schedule["episodes"]
        selected_ids = {row["case_id"] for row in selected}
        expected_methods = {
            "envsolve-operation",
            "envsolve-operation-ablation",
        }

        self.assertEqual([item["position"] for item in episodes], list(range(1, 11)))
        self.assertEqual(len({item["run_id"] for item in episodes}), 10)
        for case_id in selected_ids:
            methods = {
                item["method"] for item in episodes if item["case_id"] == case_id
            }
            self.assertEqual(methods, expected_methods)
        self.assertEqual(
            {METHOD_PROFILES[method][0] for method in expected_methods},
            {"two-layer"},
        )
        self.assertEqual(
            {METHOD_PROFILES[method][1] for method in expected_methods},
            {"constraint-driven", "free-form"},
        )

    def test_budget_is_preregistered_as_five_candidates_and_fifteen_calls(self) -> None:
        preregistration = json.loads(
            (
                ROOT
                / "experiments/validations/p6_operation_qualification_preregistration.json"
            ).read_text(encoding="utf-8")
        )
        config = json.loads(
            (ROOT / "experiments/configs/local_mac_p6_operation.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(preregistration["budget"]["max_candidates"], 5)
        self.assertEqual(preregistration["budget"]["max_model_requests"], 15)
        self.assertEqual(config["generation"]["envsolve_max_candidates"], 5)
        self.assertEqual(config["generation"]["model_max_requests"], 15)


if __name__ == "__main__":
    unittest.main()

