from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PARENT = (
    ROOT
    / "experiments/validations/pro_postcondition_persistent_qualification_v1_schedule.json"
)
RETRY = (
    ROOT
    / "experiments/validations/"
    "pro_postcondition_persistent_qualification_v1_position5_retry1_schedule.json"
)
RESOLUTION = (
    ROOT
    / "experiments/validations/"
    "pro_postcondition_persistent_qualification_v1_infrastructure_resolution_r1.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PostconditionPersistentInfrastructureResolutionTests(unittest.TestCase):
    def test_retry_changes_only_run_id_and_local_schedule_position(self) -> None:
        parent = json.loads(PARENT.read_text(encoding="utf-8"))
        retry = json.loads(RETRY.read_text(encoding="utf-8"))
        original = parent["episodes"][4]
        replacement = retry["episodes"][0]

        self.assertEqual(retry["parent_schedule_sha256"], sha256(PARENT))
        self.assertEqual(retry["case_file_sha256"], parent["case_file_sha256"])
        self.assertEqual(retry["model"], parent["model"])
        self.assertEqual(retry["episode_timeout_seconds"], parent["episode_timeout_seconds"])
        self.assertEqual(replacement["original_position"], original["position"])
        for field in ("case_block", "condition", "case_id", "method", "seed"):
            self.assertEqual(replacement[field], original[field], field)
        self.assertNotEqual(replacement["run_id"], original["run_id"])
        self.assertEqual(replacement["position"], 1)

    def test_resolution_binds_censored_evidence_and_retry_schedule(self) -> None:
        resolution = json.loads(RESOLUTION.read_text(encoding="utf-8"))

        self.assertEqual(resolution["parent_schedule"]["sha256"], sha256(PARENT))
        self.assertEqual(resolution["replacement"]["schedule_sha256"], sha256(RETRY))
        self.assertFalse(resolution["research_integrity"]["algorithm_changed"])
        self.assertFalse(resolution["research_integrity"]["official_outcome_used"])
        self.assertEqual(
            resolution["replacement"]["only_changed_field"],
            "run_id",
        )
        self.assertEqual(
            resolution["replacement"]["maximum_replacements_authorized"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
