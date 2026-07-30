from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from envsolve.state import EnvironmentState
from envsolve_harness.runners.stateful_codex import (
    StatefulCodexCliRunner,
    state_projection,
)


def _large_goal_report() -> dict[str, object]:
    return {
        "schema": "envsolve-goal-report-v1",
        "status": "fail",
        "finding_set_complete": True,
        "raw_payload_marker": "must-not-enter-compact-model-view",
        "findings": [
            {
                "finding_id": f"finding-{index:04d}",
                "domain": "module",
                "subject": f"matplotlib.area_{index % 7}.symbol_{index}",
                "predicate": "present",
                "required": True,
                "observed": False,
                "provenance": {"file": f"tests/test_{index:04d}.py"},
            }
            for index in range(572)
        ],
    }


class StatefulCodexProjectionTests(unittest.TestCase):
    def _state(self) -> EnvironmentState:
        report = _large_goal_report()
        assessment = {
            "admissible": True,
            "unresolved_constraints": 1,
            "satisfied_constraints": 0,
            "unknown_constraints": 0,
            "reason": "complete replay with unresolved internal constraints",
        }
        verifier_details = {
            "adapter_schema": "envsolve-root-obligation-finding-adapter-v1",
            "completed": True,
            "goal_passed": False,
            "finding_set_complete": True,
            "report_details": {
                "goal_report": report,
                "constraint_compaction": {
                    "surface_finding_count": 572,
                    "obligation_group_count": 1,
                },
            },
        }
        state = EnvironmentState(
            case_id="projection-case",
            case={
                "case_id": "projection-case",
                "repository": "example/project",
                "revision": "a" * 40,
            },
        )
        state.actions["candidate-1"] = {
            "action_id": "candidate-1",
            "command": "python -m pip install -e .",
            "status": "succeeded",
            "exit_code": 0,
            "state_metadata": {"event_sequence": 1},
        }
        state.failures["failure-1"] = {
            "failure_id": "failure-1",
            "category": "executable-verifier-counterexample",
            "message": "goal failed",
            "action_id": "candidate-1",
            "details": verifier_details,
            "state_metadata": {"event_sequence": 2},
        }
        state.verifications.append(
            {
                "verification_id": "verification-candidate-1",
                "passed": False,
                "details": {
                    "candidate_id": "candidate-1",
                    "reported_passed": False,
                    "bootstrap_exit_code": 0,
                    "summary": "goal failed",
                    "counterexample_count": 2,
                    "candidate_assessment": assessment,
                    "verifier_details": verifier_details,
                },
            }
        )
        return state

    def test_compact_projection_excludes_raw_report_and_bounds_size(self) -> None:
        state = self._state()

        projection = state_projection(state, "structured", compact=True)
        encoded = json.dumps(projection, sort_keys=True)

        self.assertEqual(projection["schema"], "envsolve-agent-state-v2")
        self.assertNotIn("must-not-enter-compact-model-view", encoded)
        self.assertLess(len(encoded), 50_000)
        self.assertEqual(
            projection["active_goal_state"]["summary"][
                "obligation_group_count"
            ],
            1,
        )
        self.assertEqual(
            projection["best_integrity_valid_candidate"]["script_ref"],
            "prior_candidates",
        )
        self.assertNotIn(
            "script",
            projection["best_integrity_valid_candidate"],
        )

    def test_legacy_projection_remains_available_as_frozen_baseline(self) -> None:
        state = self._state()

        encoded = json.dumps(
            state_projection(state, "structured"),
            sort_keys=True,
        )

        self.assertIn("must-not-enter-compact-model-view", encoded)

    def test_v23_profile_disables_legacy_hard_features(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = StatefulCodexCliRunner(
                codex_executable=root / "codex",
                harness_root=root,
                image="example/image:latest",
                timeout=60,
                command_timeout=30,
                container_create_timeout=30,
                git_fetch_timeout=30,
                max_rounds=3,
                feedback_mode="structured",
                method_profile="stateful-agent-v2.3",
                initial_probe=False,
                enforce_project_namespace_provenance=False,
                restore_shell_invariants=False,
            )

        self.assertFalse(runner.initial_probe)
        self.assertFalse(runner.enforce_project_namespace_provenance)
        self.assertFalse(runner.restore_shell_invariants)

    def test_v23_rejects_accidental_legacy_feature_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "version-aligned"):
                StatefulCodexCliRunner(
                    codex_executable=root / "codex",
                    harness_root=root,
                    image="example/image:latest",
                    timeout=60,
                    command_timeout=30,
                    container_create_timeout=30,
                    git_fetch_timeout=30,
                    max_rounds=3,
                    feedback_mode="structured",
                    method_profile="stateful-agent-v2.3",
                    initial_probe=True,
                    enforce_project_namespace_provenance=False,
                    restore_shell_invariants=False,
                )


if __name__ == "__main__":
    unittest.main()
