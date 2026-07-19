from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from envsolve_harness.core.io import write_json, write_jsonl
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.trajectory_binding import freeze_last_verified_candidates
from envsolve_harness.utils.provenance import sha256_file


class TrajectoryBindingTest(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        schedule_path = root / "schedule.json"
        runs_root = root / "runs"
        scripts_dir = root / "frozen"
        episode = {
            "position": 1,
            "pair_index": 1,
            "case_id": "benchmark-owner__repo@abc",
            "run_id": "source-run",
            "method": "full",
            "seed": 0,
        }
        write_json(schedule_path, {"episodes": [episode]})
        source_root = (
            runs_root
            / safe_name(episode["run_id"])
            / safe_name(episode["case_id"])
        )
        raw_root = source_root / "generation" / "raw-artifacts"
        first = raw_root / "aa" / "first.sh"
        rejected = raw_root / "bb" / "rejected.sh"
        first.parent.mkdir(parents=True)
        rejected.parent.mkdir(parents=True)
        first.write_text("set -e\nfirst\n", encoding="utf-8")
        rejected.write_text("set -e\nrejected\n", encoding="utf-8")
        events = [
            {
                "sequence": 1,
                "event_type": "action_proposed",
                "payload": {
                    "action_id": "candidate-0001",
                    "command_artifact": {
                        "path": "aa/first.sh",
                        "sha256": sha256_file(first),
                    },
                },
            },
            {
                "sequence": 2,
                "event_type": "action_finished",
                "payload": {"action_id": "candidate-0001", "exit_code": 1},
            },
            {
                "sequence": 3,
                "event_type": "verification_recorded",
                "payload": {
                    "passed": False,
                    "details": {
                        "candidate_id": "candidate-0001",
                        "candidate_sha256": sha256_file(first),
                        "summary": "fixed failure",
                    },
                },
            },
            {
                "sequence": 4,
                "event_type": "action_proposed",
                "payload": {
                    "action_id": "candidate-0002",
                    "command_artifact": {
                        "path": "bb/rejected.sh",
                        "sha256": sha256_file(rejected),
                    },
                },
            },
            {
                "sequence": 5,
                "event_type": "action_finished",
                "payload": {"action_id": "candidate-0002", "exit_code": 251},
            },
        ]
        write_jsonl(source_root / "generation" / "episode.jsonl", events)
        return schedule_path, runs_root, scripts_dir

    def test_freezes_last_verified_not_last_proposed_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule, runs, scripts = self._fixture(root)

            manifest = freeze_last_verified_candidates(
                schedule,
                runs,
                scripts,
                root,
                calibration_run_prefix="calibration",
            )

            binding = manifest["bindings"][0]
            selected = binding["selected_candidate"]
            frozen = root / selected["frozen_script_path"]
            self.assertEqual(selected["candidate_id"], "candidate-0001")
            self.assertEqual(frozen.read_text(encoding="utf-8"), "set -e\nfirst\n")
            self.assertEqual(selected["script_sha256"], sha256_file(frozen))
            self.assertEqual(binding["calibration_run_id"], "calibration-01")
            self.assertFalse(manifest["selection_policy"]["uses_official_outcome"])

    def test_rejects_candidate_hash_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule, runs, scripts = self._fixture(root)
            episode_path = next(runs.glob("*/*/generation/episode.jsonl"))
            events = episode_path.read_text(encoding="utf-8").replace(
                '"candidate_sha256": "', '"candidate_sha256": "wrong-', 1
            )
            episode_path.write_text(events, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Candidate hashes disagree"):
                freeze_last_verified_candidates(
                    schedule,
                    runs,
                    scripts,
                    root,
                    calibration_run_prefix="calibration",
                )


if __name__ == "__main__":
    unittest.main()
