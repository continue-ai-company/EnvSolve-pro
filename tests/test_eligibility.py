from __future__ import annotations

import tempfile
import time
from pathlib import Path
import unittest
from unittest import mock

from envsolve_harness.audit import AuditReport
from envsolve_harness.core.io import read_jsonl, write_json, write_jsonl
from envsolve_harness.eligibility import assess_scientific_eligibility
from envsolve_harness.execution.heartbeat import (
    RunHeartbeat,
    analyze_heartbeat_records,
)
from envsolve_harness.utils.provenance import sha256_file


class HeartbeatTest(unittest.TestCase):
    def test_monitor_writes_a_complete_sequenced_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "heartbeat.jsonl"
            with RunHeartbeat(path, interval_seconds=0.01, suspend_gap_seconds=0.1):
                time.sleep(0.025)

            records = read_jsonl(path)
            analysis = analyze_heartbeat_records(records, 0.1)
            self.assertTrue(analysis.complete)
            self.assertTrue(analysis.sequence_valid)
            self.assertFalse(analysis.suspend_suspected)
            self.assertGreaterEqual(len(records), 3)

    def test_analysis_detects_a_suspicious_gap(self) -> None:
        records = [
            {"sequence": 0, "event": "started", "gap_seconds": None},
            {"sequence": 1, "event": "heartbeat", "gap_seconds": 31.0},
            {"sequence": 2, "event": "stopped", "gap_seconds": 1.0},
        ]
        analysis = analyze_heartbeat_records(records, 30.0)
        self.assertTrue(analysis.complete)
        self.assertTrue(analysis.suspend_suspected)
        self.assertEqual(analysis.suspicious_gaps, (31.0,))


class ScientificEligibilityTest(unittest.TestCase):
    def _run_root(
        self,
        directory: str,
        *,
        dirty: bool = False,
        elapsed_seconds: float = 10.0,
        heartbeat_gap: float = 1.0,
    ) -> Path:
        root = Path(directory) / "run"
        heartbeat = root / "runtime" / "heartbeat.jsonl"
        heartbeat.parent.mkdir(parents=True)
        write_jsonl(
            heartbeat,
            [
                {"sequence": 0, "event": "started", "gap_seconds": None},
                {"sequence": 1, "event": "heartbeat", "gap_seconds": heartbeat_gap},
                {"sequence": 2, "event": "stopped", "gap_seconds": 1.0},
            ],
        )
        write_json(
            root / "manifest.json",
            {
                "harness": {"revision": "abc123", "dirty": dirty},
                "runtime_monitor": {
                    "required": True,
                    "path": "runtime/heartbeat.jsonl",
                    "suspend_gap_seconds": 30.0,
                    "sha256": sha256_file(heartbeat),
                },
            },
        )
        write_json(
            root / "generation" / "budget_ledger.json",
            {
                "limits": {
                    "max_model_requests": 5,
                    "max_total_tokens": 100,
                    "max_candidates": 5,
                    "max_environments": 5,
                    "max_commands": 5,
                    "max_wall_clock_seconds": 60,
                },
                "usage": {
                    "requests_started": 1,
                    "total_tokens": 10,
                    "candidates": 1,
                    "environments": 1,
                    "commands": 1,
                    "elapsed_wall_clock_seconds": elapsed_seconds,
                },
                "exhausted_limits": [],
                "termination": None,
            },
        )
        return root

    def _assess(self, root: Path):
        with mock.patch(
            "envsolve_harness.eligibility.audit_run",
            return_value=AuditReport(valid=True),
        ):
            return assess_scientific_eligibility(root)

    def test_clean_run_within_budget_is_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = self._assess(self._run_root(directory))
        self.assertTrue(report.eligible)
        self.assertEqual(report.exclusion_reasons, [])

    def test_dirty_source_is_ineligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = self._assess(self._run_root(directory, dirty=True))
        self.assertFalse(report.eligible)
        self.assertTrue(any("unfrozen_source" in item for item in report.exclusion_reasons))

    def test_wall_clock_overrun_is_ineligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = self._assess(self._run_root(directory, elapsed_seconds=90.0))
        self.assertFalse(report.eligible)
        self.assertTrue(any("budget_overrun" in item for item in report.exclusion_reasons))

    def test_heartbeat_gap_is_ineligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = self._assess(self._run_root(directory, heartbeat_gap=45.0))
        self.assertFalse(report.eligible)
        self.assertTrue(
            any("host_suspension_suspected" in item for item in report.exclusion_reasons)
        )


if __name__ == "__main__":
    unittest.main()
