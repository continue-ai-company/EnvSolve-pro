from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = ROOT / "envsolve/protocols/p6_constraint_operation_freeze_v17.json"
FREEZE_REVISION = "cf52839c947bc4eb23e6b21cc278620f47a5b47b"


def frozen_blob(path: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{FREEZE_REVISION}:{path}"],
        cwd=ROOT,
    )


class P6OperationFreezeTests(unittest.TestCase):
    def test_v17_source_and_parent_hashes_match_frozen_revision(self) -> None:
        relative_freeze = str(FREEZE_PATH.relative_to(ROOT))
        self.assertEqual(FREEZE_PATH.read_bytes(), frozen_blob(relative_freeze))
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))

        for relative, expected in freeze["files"].items():
            self.assertEqual(hashlib.sha256(frozen_blob(relative)).hexdigest(), expected, relative)
        for field in ("parent_freeze", "harness_freeze"):
            record = freeze[field]
            self.assertEqual(
                hashlib.sha256(frozen_blob(record["path"])).hexdigest(),
                record["sha256"],
            )

    def test_v17_treatment_boundary_is_explicit(self) -> None:
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        boundary = freeze["semantic_boundary"]

        self.assertEqual(
            boundary["shared_repository_observer"],
            "envsolve-repository-declarations-v2",
        )
        self.assertEqual(boundary["shared_verifier"], "python-deployment-v7")
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
                "negative_operation_state_visibility",
                "grounded_negative_operation_context_visibility",
                "context_scoped_negative_operation_guard",
            ],
        )
        contract = freeze["negative_operation_contract"]
        self.assertTrue(contract["model_projection"]["failed_prefix_visible"])
        self.assertTrue(contract["shared_prefix_provenance"])
        self.assertEqual(
            contract["ungrounded_evidence"],
            "not visible to the model and not hardened by the guard",
        )
        self.assertFalse(boundary["cross_case_memory"])
        self.assertFalse(boundary["case_specific_rules"])


if __name__ == "__main__":
    unittest.main()
