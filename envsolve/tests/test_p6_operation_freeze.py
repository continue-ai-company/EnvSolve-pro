from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = ROOT / "envsolve/protocols/p6_constraint_operation_freeze_v9.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P6OperationFreezeTests(unittest.TestCase):
    def test_v9_source_and_parent_hashes_are_current(self) -> None:
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))

        for relative, expected in freeze["files"].items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)
        for field in ("parent_freeze", "harness_freeze"):
            record = freeze[field]
            self.assertEqual(sha256(ROOT / record["path"]), record["sha256"])

    def test_v9_treatment_boundary_is_explicit(self) -> None:
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        boundary = freeze["semantic_boundary"]

        self.assertEqual(
            boundary["shared_repository_observer"],
            "envsolve-repository-declarations-v2",
        )
        self.assertEqual(boundary["shared_verifier"], "python-deployment-v5")
        self.assertEqual(
            boundary["shared_base_runtime_observer"],
            "envsolve-base-runtime-observation-v1",
        )
        self.assertEqual(
            boundary["treatment_components"],
            [
                "pre_action_constraint_admission",
                "constraint_operation_plan_visibility",
                "constraint_operation_guard",
            ],
        )
        self.assertFalse(boundary["cross_case_memory"])
        self.assertFalse(boundary["case_specific_rules"])


if __name__ == "__main__":
    unittest.main()
