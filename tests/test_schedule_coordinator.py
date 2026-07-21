from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from envsolve_harness.execution.schedule import (
    ScheduleProgress,
    run_scheduled_process,
)
from experiments.run_schedule import _episode_identity


class ScheduleProgressTest(unittest.TestCase):
    def test_mixed_schedule_episode_overrides_runner_model_and_allows_null_seed(self) -> None:
        identity = _episode_identity(
            {
                "position": 3,
                "case_id": "owner/repo@abc",
                "run_id": "mixed-run",
                "runner": "repo2run",
                "method": "repo2run",
                "model": "provider/model",
                "seed": None,
            },
            {},
            "envsolve",
        )

        self.assertEqual(identity["runner"], "repo2run")
        self.assertEqual(identity["model"], "provider/model")
        self.assertIsNone(identity["seed"])

    def test_legacy_schedule_uses_top_level_model_and_default_runner(self) -> None:
        identity = _episode_identity(
            {
                "position": 1,
                "case_id": "owner/repo@abc",
                "run_id": "legacy-run",
                "method": "envsolve-pro",
                "seed": 7,
            },
            {"model": "provider/model"},
            "envsolve",
        )

        self.assertEqual(identity["runner"], "envsolve")
        self.assertEqual(identity["model"], "provider/model")
        self.assertEqual(identity["seed"], 7)

    def test_resume_preserves_completed_positions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = root / "schedule.json"
            schedule.write_text("{}\n", encoding="utf-8")
            progress_path = root / "progress.json"
            execution = {"runner": "test", "episode_timeout_seconds": 10}
            progress = ScheduleProgress(progress_path, schedule, "schedule-hash", execution)
            first = {
                "position": 1,
                "case_id": "case-1",
                "run_id": "run-1",
                "method": "full",
            }
            progress.begin(first)
            progress.complete(
                1,
                {"state": "process_finished", "process_exit_code": 0},
            )

            resumed = ScheduleProgress(progress_path, schedule, "schedule-hash", execution)
            resumed.begin(
                {
                    "position": 2,
                    "case_id": "case-2",
                    "run_id": "run-2",
                    "method": "ablation",
                }
            )
            resumed.complete(
                2,
                {"state": "process_finished", "process_exit_code": 1},
            )

            self.assertEqual([item["position"] for item in resumed.outcomes], [1, 2])
            self.assertEqual(resumed.outcomes[0]["process_exit_code"], 0)

    def test_resume_rejects_changed_execution_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = root / "schedule.json"
            schedule.write_text("{}\n", encoding="utf-8")
            progress = ScheduleProgress(
                root / "progress.json",
                schedule,
                "schedule-hash",
                {"timeout": 10},
            )
            progress.begin(
                {
                    "position": 1,
                    "case_id": "case",
                    "run_id": "run",
                    "method": "full",
                }
            )
            with self.assertRaisesRegex(ValueError, "execution settings"):
                ScheduleProgress(
                    root / "progress.json",
                    schedule,
                    "schedule-hash",
                    {"timeout": 20},
                )

    def test_running_position_becomes_orphaned_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = root / "schedule.json"
            schedule.write_text("{}\n", encoding="utf-8")
            progress_path = root / "progress.json"
            progress = ScheduleProgress(progress_path, schedule, "schedule-hash")
            progress.begin(
                {
                    "position": 1,
                    "case_id": "case",
                    "run_id": "run",
                    "method": "full",
                }
            )

            resumed = ScheduleProgress(progress_path, schedule, "schedule-hash")
            self.assertEqual(resumed.recover_orphans(), (1,))
            self.assertEqual(resumed.outcomes[0]["state"], "orphaned")
            self.assertTrue(resumed.contains(1))


class ScheduledProcessTest(unittest.TestCase):
    def test_hard_timeout_terminates_the_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_scheduled_process(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=Path(directory),
                timeout_seconds=0.05,
                termination_grace_seconds=0.1,
            )

        self.assertEqual(result["state"], "timed_out")
        self.assertIsNotNone(result["process_exit_code"])
        self.assertLess(result["duration_seconds"], 2.0)

    def test_process_output_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_scheduled_process(
                [sys.executable, "-c", "print('x' * 5000)"],
                cwd=Path(directory),
                timeout_seconds=2.0,
            )

        self.assertEqual(result["state"], "process_finished")
        self.assertEqual(result["process_exit_code"], 0)
        self.assertEqual(len(result["stdout_tail"]), 4000)


if __name__ == "__main__":
    unittest.main()
