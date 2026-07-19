from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from envsolve_harness.core.io import write_json, write_jsonl
from envsolve_harness.failure_analysis import analyze_candidate_failures
from envsolve_harness.storage.artifacts import safe_name


class FailureAnalysisTest(unittest.TestCase):
    def test_partitions_candidate_transition_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = root / "schedule.json"
            runs = root / "runs"
            episode = {
                "position": 1,
                "pair_index": 1,
                "case_id": "owner/repo@abc",
                "run_id": "run-full",
                "method": "full",
                "seed": 0,
            }
            write_json(schedule, {"episodes": [episode]})
            episode_path = (
                runs
                / safe_name(episode["run_id"])
                / safe_name(episode["case_id"])
                / "generation"
                / "episode.jsonl"
            )
            events = []
            sequence = 0
            categories = (
                ("candidate-0001", 252, None),
                ("candidate-0002", 251, None),
                (
                    "candidate-0003",
                    1,
                    {
                        "summary": "Complete candidate failed fixed internal Python checks",
                        "verifier_details": {
                            "failed_candidate_action": {"action_index": 0}
                        },
                    },
                ),
                (
                    "candidate-0004",
                    1,
                    {
                        "summary": "Complete candidate failed fixed internal Python checks",
                        "verifier_details": {},
                    },
                ),
                (
                    "candidate-0005",
                    0,
                    {
                        "summary": "structured verifier: goal=False, active=1",
                        "verifier_details": {},
                    },
                ),
            )
            for candidate_id, exit_code, verification in categories:
                events.append(
                    {
                        "sequence": sequence,
                        "event_type": "action_proposed",
                        "payload": {"action_id": candidate_id},
                    }
                )
                sequence += 1
                events.append(
                    {
                        "sequence": sequence,
                        "event_type": "action_finished",
                        "payload": {"action_id": candidate_id, "exit_code": exit_code},
                    }
                )
                sequence += 1
                if verification is not None:
                    events.append(
                        {
                            "sequence": sequence,
                            "event_type": "verification_recorded",
                            "payload": {
                                "passed": False,
                                "details": {
                                    "candidate_id": candidate_id,
                                    **verification,
                                },
                            },
                        }
                    )
                    sequence += 1
            write_jsonl(episode_path, events)

            analysis = analyze_candidate_failures(schedule, runs)

        self.assertEqual(analysis["aggregate"]["candidates"], 5)
        self.assertEqual(analysis["aggregate"]["executed_candidates"], 3)
        self.assertEqual(analysis["aggregate"]["later_proposal_candidates"], 4)
        self.assertEqual(
            analysis["aggregate"]["categories"],
            {
                "candidate_command_failure": 1,
                "candidate_validation_reject": 1,
                "fixed_internal_check_failure": 1,
                "operation_guard_reject": 1,
                "structured_obligations_active": 1,
            },
        )
        self.assertEqual(analysis["methods"]["full"], analysis["aggregate"])


if __name__ == "__main__":
    unittest.main()
