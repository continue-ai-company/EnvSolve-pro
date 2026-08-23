from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest import mock

from envsolve_harness.audit import AuditReport
from envsolve_harness.core.io import write_json
from envsolve_harness.eligibility import EligibilityReport
from envsolve_harness.results_v2 import (
    _generation_result_resources,
    _paired_aggregate_v2,
    summarize_schedule,
)
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file
from experiments.summarize_schedule_v2 import _attach_coordinator_progress


class ResultSummarizerV2Test(unittest.TestCase):
    def test_string_pair_id_and_end_to_end_non_submission(self) -> None:
        runs = [
            {
                "pair_id": "owner-repo-abc",
                "method": "treatment",
                "scientifically_eligible": True,
                "official_pass": True,
            },
            {
                "pair_id": "owner-repo-abc",
                "method": "control",
                "scientifically_eligible": True,
                "official_pass": None,
            },
        ]

        official_only = _paired_aggregate_v2(
            runs,
            "treatment",
            "control",
            missing_official_as_failure=False,
        )
        end_to_end = _paired_aggregate_v2(
            runs,
            "treatment",
            "control",
            missing_official_as_failure=True,
        )

        self.assertEqual(official_only["censored_pairs"], 1)
        self.assertEqual(end_to_end["eligible_pairs"], 1)
        self.assertEqual(end_to_end["treatment_only_pass"], 1)

    def test_reads_codex_cli_resources_from_generation_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(
                root / "generation" / "result.json",
                {
                    "metadata": {
                        "started_at": "2026-07-30T07:13:34Z",
                        "finished_at": "2026-07-30T07:17:57Z",
                        "token_usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 40,
                            "output_tokens": 20,
                            "reasoning_output_tokens": 5,
                        },
                        "container_command_trace": {
                            "count": 8,
                            "successful_count": 7,
                        },
                    }
                },
            )

            resources = _generation_result_resources(root)

        assert resources is not None
        self.assertEqual(resources["source"], "generation/result.json")
        self.assertEqual(resources["commands"], 8)
        self.assertEqual(resources["successful_commands"], 7)
        self.assertEqual(resources["cache_read_tokens"], 40)
        self.assertEqual(resources["total_tokens"], 120)
        self.assertEqual(resources["elapsed_wall_clock_seconds"], 263.0)

    def test_reads_stateful_resources_without_conflating_command_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(
                root / "generation" / "result.json",
                {
                    "metadata": {
                        "agent_policy": {
                            "container_command_count": 6,
                            "rounds_started": 1,
                            "rounds": [
                                {"successful_container_command_count": 5}
                            ],
                            "token_usage": {
                                "input_tokens": 200,
                                "cached_input_tokens": 150,
                                "output_tokens": 30,
                            },
                        },
                        "execution_budget": {
                            "usage": {
                                "candidates": 1,
                                "commands": 1,
                                "environments": 1,
                                "elapsed_wall_clock_seconds": 42.5,
                            }
                        },
                    }
                },
            )

            resources = _generation_result_resources(root)

        assert resources is not None
        self.assertEqual(resources["commands"], 6)
        self.assertEqual(resources["successful_commands"], 5)
        self.assertEqual(resources["budget_commands"], 1)
        self.assertEqual(resources["candidates"], 1)
        self.assertEqual(resources["rounds_started"], 1)
        self.assertEqual(resources["elapsed_scope"], "generation")

    def test_recovers_failed_episode_resources_from_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(
                root / "generation" / "result.json",
                {
                    "metadata": {
                        "started_at": "2026-07-30T07:13:34Z",
                        "finished_at": "2026-07-30T07:17:57Z",
                    }
                },
            )
            trajectory = root / "generation" / "trajectory.jsonl"
            trajectory.write_text(
                "\n".join(
                    [
                        '{"event":"provider_response","request_index":1,'
                        '"response":{"usage":{"prompt_tokens":100,'
                        '"completion_tokens":20,"prompt_tokens_details":'
                        '{"cached_tokens":40},"completion_tokens_details":'
                        '{"reasoning_tokens":5}}}}',
                        '{"event":"tool_result","request_index":1,'
                        '"result":{"exit_code":0}}',
                        '{"event":"provider_error","request_index":2}',
                        '{"event":"provider_response","request_index":2,'
                        '"response":{"usage":{"prompt_tokens":150,'
                        '"completion_tokens":30}}}',
                        '{"event":"tool_result","request_index":2,'
                        '"result":{"exit_code":1}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            resources = _generation_result_resources(root)

        assert resources is not None
        self.assertEqual(resources["requests_started"], 2)
        self.assertEqual(resources["provider_attempts_started"], 3)
        self.assertEqual(resources["provider_retries"], 1)
        self.assertEqual(resources["provider_retry_recoveries"], 1)
        self.assertEqual(resources["commands"], 2)
        self.assertEqual(resources["successful_commands"], 1)
        self.assertEqual(resources["input_tokens"], 250)
        self.assertEqual(resources["output_tokens"], 50)
        self.assertEqual(resources["cache_read_tokens"], 40)
        self.assertEqual(resources["reasoning_output_tokens"], 5)
        self.assertEqual(resources["total_tokens"], 300)
        self.assertEqual(
            resources["source"],
            "generation/result.json+trajectory.jsonl",
        )

    @mock.patch(
        "envsolve_harness.results.assess_scientific_eligibility",
        return_value=EligibilityReport(eligible=True),
    )
    @mock.patch(
        "envsolve_harness.results.audit_run",
        return_value=AuditReport(valid=True),
    )
    def test_budget_ledger_remains_preferred_resource_source(
        self,
        _audit: mock.Mock,
        _eligibility: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            case_file = root / "cases.jsonl"
            case_file.write_text("{}\n", encoding="utf-8")
            episode = {
                "position": 1,
                "case_id": "owner/repo@abc",
                "run_id": "run-full",
                "method": "full",
                "seed": 0,
            }
            run = runs / safe_name(episode["run_id"]) / safe_name(episode["case_id"])
            write_json(
                run / "manifest.json",
                {
                    "run": {
                        "run_id": episode["run_id"],
                        "method": episode["method"],
                        "seed": 0,
                    },
                    "case": {"case_id": episode["case_id"]},
                    "solver": {"generation_completed": True, "metadata": {}},
                    "result": {
                        "evaluation_completed": True,
                        "official_pass": True,
                    },
                },
            )
            write_json(run / "status.json", {"state": "completed"})
            write_json(
                run / "generation" / "result.json",
                {"metadata": {"token_usage": {"input_tokens": 999}}},
            )
            write_json(
                run / "generation" / "budget_ledger.json",
                {
                    "usage": {"input_tokens": 123, "commands": 4},
                    "provider_attempts": [],
                },
            )
            schedule = root / "schedule.json"
            write_json(
                schedule,
                {
                    "schema_version": "1.0.0",
                    "case_file": str(case_file),
                    "case_file_sha256": sha256_file(case_file),
                    "episodes": [episode],
                },
            )

            summary = summarize_schedule(schedule, runs)

        resources = summary["runs"][0]["resources"]
        self.assertEqual(summary["resource_schema_version"], "2.0.0")
        implementation = summary["analysis_implementation"]
        self.assertEqual(
            implementation["summarizer"]["sha256"],
            sha256_file(Path(__file__).parents[1] / implementation["summarizer"]["path"]),
        )
        self.assertEqual(resources["source"], "generation/budget_ledger.json")
        self.assertEqual(resources["input_tokens"], 123)
        self.assertEqual(resources["commands"], 4)

    def test_attaches_matching_progress_and_ignores_excluded_attempts(self) -> None:
        summary = {
            "runs": [
                {
                    "position": 1,
                    "case_id": "owner/repo@abc",
                    "run_id": "clean-run",
                    "method": "structured",
                    "seed": 4,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            amendment = root / "amendment.json"
            write_json(
                source,
                {
                    "outcomes": [
                        {
                            "position": 1,
                            "case_id": "owner/repo@abc",
                            "run_id": "excluded-dirty-run",
                            "method": "structured",
                            "seed": 4,
                            "duration_seconds": 99.0,
                        }
                    ]
                },
            )
            write_json(
                amendment,
                {
                    "outcomes": [
                        {
                            "position": 1,
                            "case_id": "owner/repo@abc",
                            "run_id": "clean-run",
                            "method": "structured",
                            "seed": 4,
                            "state": "process_finished",
                            "process_exit_code": 0,
                            "started_at": "2026-07-30T00:00:00Z",
                            "finished_at": "2026-07-30T00:00:42Z",
                            "duration_seconds": 42.0,
                        }
                    ]
                },
            )

            _attach_coordinator_progress(summary, [source, amendment])

        progress = summary["coordinator_progress"]
        self.assertEqual(len(progress["runs"]), 1)
        self.assertEqual(progress["runs"][0]["run_id"], "clean-run")
        self.assertEqual(
            progress["aggregate_by_method"]["structured"][
                "endpoint_wall_clock_seconds"
            ],
            42.0,
        )


if __name__ == "__main__":
    unittest.main()
