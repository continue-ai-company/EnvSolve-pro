from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from envsolve_harness.core.io import write_json
from envsolve_harness.persistent_state_analysis import (
    analyze_postcondition_persistent_schedule,
    audit_persistent_episode,
)


PERSISTENT_METHOD = (
    "envsolve-pro-goal-contract-evidence-anchor-persistent"
)
FRESH_METHOD = "envsolve-pro-goal-contract-evidence-anchor"


def action(
    candidate_id: str,
    script_sha256: str,
    *,
    source_candidate_id: str | None = None,
) -> dict:
    metadata = {}
    if source_candidate_id is not None:
        metadata["source_candidate_id"] = source_candidate_id
    return {
        "action_id": candidate_id,
        "metadata": metadata,
        "command_artifact": {"sha256": script_sha256},
    }


def verification(
    verification_id: str,
    candidate_id: str,
    environment_id: str,
    sequence: int,
    *,
    role: str,
    environment_fresh: bool,
    state_lineage_id: str | None,
    reported_passed: bool,
    passed: bool | None,
) -> dict:
    return {
        "verification_id": verification_id,
        "passed": passed,
        "details": {
            "candidate_id": candidate_id,
            "feedback_channel": "internal_execution",
            "verification_role": role,
            "environment_fresh": environment_fresh,
            "state_lineage_id": state_lineage_id,
            "reported_passed": reported_passed,
            "environment_receipt": {
                "environment_id": environment_id,
            },
        },
        "state_metadata": {"event_sequence": sequence},
    }


def transition(
    evidence_id: str,
    candidate_id: str,
    environment_id: str,
    disposition: str,
    sequence: int,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "kind": "state-transition-observation",
        "source": "postcondition-state-transition-v1",
        "value": {
            "candidate_id": candidate_id,
            "environment_id": environment_id,
            "disposition": disposition,
            "reason": "fixture",
        },
        "state_metadata": {"event_sequence": sequence},
    }


class PersistentStateAnalysisTests(unittest.TestCase):
    @staticmethod
    def valid_snapshot() -> dict:
        return {
            "actions": {
                "candidate-1": action("candidate-1", "a" * 64),
                "candidate-2": action("candidate-2", "b" * 64),
                "candidate-2-clean-replay": action(
                    "candidate-2-clean-replay",
                    "b" * 64,
                    source_candidate_id="candidate-2",
                ),
            },
            "evidence": {
                "transition-1": transition(
                    "transition-1",
                    "candidate-1",
                    "environment-1",
                    "reusable",
                    5,
                ),
                "transition-2": transition(
                    "transition-2",
                    "candidate-2",
                    "environment-1",
                    "reusable",
                    10,
                ),
            },
            "verifications": [
                verification(
                    "verification-candidate-1",
                    "candidate-1",
                    "environment-1",
                    6,
                    role="construction-state",
                    environment_fresh=True,
                    state_lineage_id="environment-1",
                    reported_passed=False,
                    passed=False,
                ),
                verification(
                    "verification-construction-candidate-2",
                    "candidate-2",
                    "environment-1",
                    11,
                    role="construction-state",
                    environment_fresh=False,
                    state_lineage_id="environment-1",
                    reported_passed=True,
                    passed=None,
                ),
                verification(
                    "verification-candidate-2-clean-replay",
                    "candidate-2-clean-replay",
                    "environment-2",
                    14,
                    role="clean-replay-certification",
                    environment_fresh=True,
                    state_lineage_id=None,
                    reported_passed=True,
                    passed=True,
                ),
            ],
        }

    @staticmethod
    def write_fixture(root: Path, snapshot: dict) -> None:
        write_json(root / "generation" / "episode_snapshot.json", snapshot)
        write_json(
            root / "generation" / "result.json",
            {
                "metadata": {
                    "episode": {
                        "candidate_certification": "certified",
                        "accepted_candidate": {
                            "candidate_id": "candidate-2-clean-replay",
                        },
                        "accepted_environment": {
                            "environment_id": "environment-2",
                        },
                    }
                }
            },
        )

    def test_valid_reuse_and_exact_clean_replay_pass_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_fixture(root, self.valid_snapshot())

            result = audit_persistent_episode(root, PERSISTENT_METHOD)

        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(
            result["metrics"]["reused_construction_verifications"],
            1,
        )
        self.assertEqual(
            result["metrics"]["reused_construction_clean_passes"],
            1,
        )

    def test_damaged_lineage_cannot_be_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self.valid_snapshot()
            snapshot["evidence"]["transition-1"]["value"][
                "disposition"
            ] = "damaged"
            self.write_fixture(root, snapshot)

            result = audit_persistent_episode(root, PERSISTENT_METHOD)

        self.assertFalse(result["valid"])
        self.assertTrue(
            any("damaged lineage" in error for error in result["errors"])
        )
        self.assertTrue(
            any("without prior reusable evidence" in error for error in result["errors"])
        )

    def test_clean_replay_must_use_the_exact_source_program(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self.valid_snapshot()
            snapshot["actions"]["candidate-2-clean-replay"][
                "command_artifact"
            ]["sha256"] = "c" * 64
            self.write_fixture(root, snapshot)

            result = audit_persistent_episode(root, PERSISTENT_METHOD)

        self.assertFalse(result["valid"])
        self.assertTrue(
            any("exact source program" in error for error in result["errors"])
        )

    def test_fresh_control_rejects_transition_state_or_nonfresh_execution(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = {
                "actions": {
                    "candidate-1": action("candidate-1", "a" * 64),
                },
                "evidence": {},
                "verifications": [
                    verification(
                        "verification-candidate-1",
                        "candidate-1",
                        "environment-1",
                        4,
                        role="candidate",
                        environment_fresh=True,
                        state_lineage_id=None,
                        reported_passed=True,
                        passed=True,
                    )
                ],
            }
            self.write_fixture(root, snapshot)

            valid = audit_persistent_episode(root, FRESH_METHOD)
            invalid_snapshot = deepcopy(snapshot)
            invalid_snapshot["evidence"]["transition-1"] = transition(
                "transition-1",
                "candidate-1",
                "environment-1",
                "reusable",
                3,
            )
            self.write_fixture(root, invalid_snapshot)
            invalid = audit_persistent_episode(root, FRESH_METHOD)

        self.assertTrue(valid["valid"])
        self.assertFalse(invalid["valid"])
        self.assertIn(
            "Fresh-state control contains state-transition evidence",
            invalid["errors"],
        )

    def test_frozen_schedule_is_pending_before_artifacts_exist(self) -> None:
        schedule = (
            Path(__file__).resolve().parents[1]
            / "experiments/validations/"
            "pro_postcondition_persistent_qualification_v1_schedule.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = analyze_postcondition_persistent_schedule(
                schedule,
                Path(directory),
            )

        self.assertEqual(result["gate"]["decision"], "pending")
        self.assertFalse(result["gate"]["schedule_complete"])
        self.assertEqual(len(result["runs"]), 15)


if __name__ == "__main__":
    unittest.main()
