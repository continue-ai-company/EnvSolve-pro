from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from envsolve_harness.runners.envsolve_p6 import (
    METHOD_CONSTRAINT_PROFILES,
    METHOD_ENVIRONMENT_STRATEGIES,
)


ROOT = Path(__file__).resolve().parents[1]
SALT = "8104851:postcondition-persistent-qv1"
SOURCE = (
    ROOT
    / "experiments/cases/train_untouched_after_pro_trajectory_census_replication_v1_96.jsonl"
)
CASES = (
    ROOT
    / "experiments/cases/dev_pro_postcondition_persistent_qualification_v1_5.jsonl"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/pro_postcondition_persistent_qualification_v1_preregistration.json"
)
SCHEDULE = (
    ROOT
    / "experiments/validations/pro_postcondition_persistent_qualification_v1_schedule.json"
)
FREEZE = (
    ROOT
    / "experiments/protocols/pro_postcondition_persistent_v1_freeze.json"
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PostconditionPersistentQualificationTests(unittest.TestCase):
    def test_selection_is_metadata_only_deterministic_and_repository_disjoint(
        self,
    ) -> None:
        source = read_jsonl(SOURCE)
        selected = read_jsonl(CASES)
        preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        excluded = set(
            preregistration["selection"]["excluded_consumed_repositories"]
        )
        eligible = {
            str(item["repository"]): item
            for item in source
            if item["repository"] not in excluded
        }
        expected = sorted(
            eligible.values(),
            key=lambda item: hashlib.sha256(
                (
                    f"{SALT}:{item['repository']}@{item['revision']}"
                ).encode()
            ).hexdigest(),
        )[:5]

        self.assertEqual(
            [item["case_id"] for item in selected],
            [item["case_id"] for item in expected],
        )
        self.assertEqual(len({item["repository"] for item in selected}), 5)
        self.assertFalse(
            {item["repository"] for item in selected} & excluded
        )
        self.assertEqual(
            preregistration["selection"]["case_file_sha256"],
            sha256(CASES),
        )

    def test_schedule_contains_three_frozen_conditions_per_case(self) -> None:
        schedule = json.loads(SCHEDULE.read_text(encoding="utf-8"))
        episodes = schedule["episodes"]
        methods = {
            "envsolve-pro-goal-contract-evidence-anchor",
            "envsolve-pro-goal-contract-evidence-anchor-persistent",
            "envsolve-pro-goal-aware-raw-evidence-anchor-persistent",
        }

        self.assertEqual(
            [item["position"] for item in episodes],
            list(range(1, 16)),
        )
        self.assertEqual(len({item["run_id"] for item in episodes}), 15)
        for case_block in range(1, 6):
            self.assertEqual(
                {
                    item["method"]
                    for item in episodes
                    if item["case_block"] == case_block
                },
                methods,
            )
        self.assertEqual(
            METHOD_ENVIRONMENT_STRATEGIES[
                "envsolve-pro-goal-contract-evidence-anchor"
            ],
            "fresh-candidate",
        )
        self.assertEqual(
            {
                METHOD_ENVIRONMENT_STRATEGIES[method]
                for method in methods
                if method.endswith("-persistent")
            },
            {"postcondition-persistent"},
        )
        self.assertEqual(
            METHOD_CONSTRAINT_PROFILES[
                "envsolve-pro-goal-contract-evidence-anchor-persistent"
            ],
            "flat",
        )
        self.assertEqual(
            METHOD_CONSTRAINT_PROFILES[
                "envsolve-pro-goal-aware-raw-evidence-anchor-persistent"
            ],
            "raw-history",
        )

    def test_schedule_is_hash_bound_to_inputs(self) -> None:
        schedule = json.loads(SCHEDULE.read_text(encoding="utf-8"))

        self.assertEqual(schedule["preregistration_sha256"], sha256(PREREGISTRATION))
        self.assertEqual(schedule["case_file_sha256"], sha256(CASES))

    def test_freeze_hashes_match_the_bound_artifacts(self) -> None:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))

        for relative, expected in freeze["files"].items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)
        harness = freeze["harness_freeze"]
        self.assertEqual(
            sha256(ROOT / harness["path"]),
            harness["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
