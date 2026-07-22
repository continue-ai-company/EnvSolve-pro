from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from envsolve_harness.audit import AuditReport
from envsolve_harness.core.io import write_json
from envsolve_harness.eligibility import EligibilityReport
from envsolve_harness.results import summarize_schedule
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


class ResultSummarizerTest(unittest.TestCase):
    def _fixture(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory)
        runs = root / "runs"
        case_file = root / "cases.jsonl"
        case_file.write_text("{}\n", encoding="utf-8")
        episodes = []
        for position, method, passed in (
            (1, "full", True),
            (2, "ablation", False),
        ):
            episode = {
                "position": position,
                "pair_index": 1,
                "case_id": "owner/repo@abc",
                "run_id": f"run-{method}",
                "method": method,
                "seed": 0,
            }
            episodes.append(episode)
            run = runs / safe_name(episode["run_id"]) / safe_name(episode["case_id"])
            write_json(
                run / "manifest.json",
                {
                    "run": {
                        "run_id": episode["run_id"],
                        "method": method,
                        "seed": 0,
                    },
                    "case": {"case_id": episode["case_id"]},
                    "solver": {"generation_completed": True, "metadata": {}},
                    "result": {
                        "evaluation_completed": True,
                        "official_pass": passed,
                    },
                },
            )
            write_json(run / "status.json", {"state": "completed"})
            write_json(
                run / "evaluation" / "result.json",
                {"evaluation_completed": True, "official_pass": passed},
            )
        schedule = root / "schedule.json"
        write_json(
            schedule,
            {
                "schema_version": "1.0.0",
                "case_file": str(case_file),
                "case_file_sha256": sha256_file(case_file),
                "episodes": episodes,
            },
        )
        return schedule, runs

    @mock.patch(
        "envsolve_harness.results.assess_scientific_eligibility",
        return_value=EligibilityReport(eligible=True),
    )
    @mock.patch(
        "envsolve_harness.results.audit_run",
        return_value=AuditReport(valid=True),
    )
    def test_builds_paired_result_and_hash_chain(
        self,
        _audit: mock.Mock,
        _eligibility: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schedule, runs = self._fixture(directory)
            summary = summarize_schedule(
                schedule,
                runs,
                treatment_method="full",
                control_method="ablation",
            )

        self.assertEqual(summary["descriptive"]["artifact_integrity_valid"], 2)
        self.assertEqual(summary["scientific"]["eligible_runs"], 2)
        self.assertEqual(summary["paired_scientific"]["treatment_only_pass"], 1)
        self.assertEqual(summary["paired_scientific"]["eligible_pairs"], 1)
        self.assertRegex(summary["runs"][0]["artifact_bundle_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("manifest.json", summary["runs"][0]["artifact_hashes"])
        self.assertIn("evaluation/result.json", summary["runs"][0]["artifact_hashes"])

    @mock.patch(
        "envsolve_harness.results.assess_scientific_eligibility",
        return_value=EligibilityReport(
            eligible=False,
            classification="scientifically_ineligible",
            exclusion_reasons=["host_suspension_suspected: fixture"],
        ),
    )
    @mock.patch(
        "envsolve_harness.results.audit_run",
        return_value=AuditReport(valid=True),
    )
    def test_descriptive_results_are_retained_but_scientific_pair_is_censored(
        self,
        _audit: mock.Mock,
        _eligibility: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schedule, runs = self._fixture(directory)
            summary = summarize_schedule(
                schedule,
                runs,
                treatment_method="full",
                control_method="ablation",
            )

        self.assertEqual(summary["descriptive"]["official_pass"], 1)
        self.assertEqual(summary["scientific"]["eligible_runs"], 0)
        self.assertEqual(summary["paired_scientific"]["censored_pairs"], 1)

    @mock.patch(
        "envsolve_harness.results.assess_scientific_eligibility",
        return_value=EligibilityReport(eligible=True),
    )
    @mock.patch(
        "envsolve_harness.results.audit_run",
        return_value=AuditReport(valid=True),
    )
    def test_normalizes_shared_seed_and_pair_alias(
        self,
        _audit: mock.Mock,
        _eligibility: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schedule, runs = self._fixture(directory)
            value = json.loads(schedule.read_text(encoding="utf-8"))
            value["shared"] = {"seed": 0}
            for episode in value["episodes"]:
                episode["pair"] = episode.pop("pair_index")
                episode.pop("seed")
            write_json(schedule, value)

            summary = summarize_schedule(
                schedule,
                runs,
                treatment_method="full",
                control_method="ablation",
            )

        self.assertEqual(summary["scientific"]["eligible_runs"], 2)
        self.assertEqual(summary["paired_scientific"]["eligible_pairs"], 1)

    @mock.patch(
        "envsolve_harness.results.assess_scientific_eligibility",
        return_value=EligibilityReport(eligible=True),
    )
    @mock.patch(
        "envsolve_harness.results.audit_run",
        return_value=AuditReport(valid=True),
    )
    def test_preserves_incomplete_evaluator_termination_kind(
        self,
        _audit: mock.Mock,
        _eligibility: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schedule, runs = self._fixture(directory)
            run = runs / safe_name("run-full") / safe_name("owner/repo@abc")
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            manifest["result"] = {
                "evaluation_completed": False,
                "official_pass": False,
                "metadata": {
                    "termination": {
                        "kind": "measurement_integrity_unknown",
                        "scope": "evaluator_diagnostics",
                    }
                },
            }
            write_json(run / "manifest.json", manifest)
            write_json(run / "evaluation" / "result.json", manifest["result"])

            summary = summarize_schedule(
                schedule,
                runs,
                treatment_method="full",
                control_method="ablation",
            )

        full = next(run for run in summary["runs"] if run["method"] == "full")
        self.assertEqual(full["descriptive_terminal"], "measurement_integrity_unknown")
        self.assertIsNone(full["official_pass"])
        self.assertEqual(summary["paired_scientific"]["censored_pairs"], 1)


if __name__ == "__main__":
    unittest.main()
