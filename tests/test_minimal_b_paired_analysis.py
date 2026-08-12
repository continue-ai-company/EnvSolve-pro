from __future__ import annotations

from pathlib import Path
import tempfile
from unittest import mock

from envsolve_harness.audit import AuditReport
from envsolve_harness.core.io import write_json
from envsolve_harness.minimal_b_analysis import analyze_minimal_b_paired_dev5
from envsolve_harness.storage.artifacts import safe_name


def _write_episode(
    runs_root: Path,
    *,
    run_id: str,
    case_id: str,
    method: str,
    seed: int,
    official_pass: bool | None,
    input_tokens: int,
    commands: int,
) -> None:
    root = runs_root / safe_name(run_id) / safe_name(case_id)
    write_json(
        root / "manifest.json",
        {
            "run": {"run_id": run_id, "method": method, "seed": seed},
            "case": {"case_id": case_id},
        },
    )
    write_json(root / "status.json", {"state": "completed"})
    write_json(
        root / "generation" / "result.json",
        {
            "generation_completed": official_pass is not None,
            "metadata": {
                "started_at": "2026-08-01T00:00:00Z",
                "finished_at": "2026-08-01T00:01:00Z",
                "candidate_validation": {"accepted": official_pass is not None},
                "container_command_trace": {
                    "count": commands,
                    "successful_count": commands,
                },
                "repository_integrity": {"valid": True},
                "token_usage": {
                    "input_tokens": input_tokens,
                    "cached_input_tokens": input_tokens // 2,
                    "output_tokens": 10,
                    "reasoning_output_tokens": 5,
                },
            },
        },
    )
    if official_pass is not None:
        write_json(
            root / "evaluation" / "result.json",
            {
                "official_pass": official_pass,
                "metadata": {
                    "started_at": "2026-08-01T00:01:00Z",
                    "finished_at": "2026-08-01T00:01:30Z",
                },
                "raw_metrics": {"error_count": 0},
                "evidence": [],
            },
        )


@mock.patch(
    "envsolve_harness.minimal_b_analysis.audit_run",
    return_value=AuditReport(valid=True),
)
def test_recomputes_frozen_paired_outcome_and_censors_only_timing(
    _audit: mock.Mock,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        runs_root = root / "runs"
        progress_path = root / "progress.json"
        episodes = []
        outcomes = []
        for pair_index in range(1, 6):
            case_id = f"owner/repo-{pair_index}@abc{pair_index}"
            for condition, method in (
                ("treatment", "treatment-method"),
                ("control", "control-method"),
            ):
                run_id = f"pair-{pair_index}-{condition}"
                passed = not (pair_index == 2 and condition == "control")
                official_pass = passed if passed else None
                _write_episode(
                    runs_root,
                    run_id=run_id,
                    case_id=case_id,
                    method=method,
                    seed=pair_index,
                    official_pass=official_pass,
                    input_tokens=100 + pair_index,
                    commands=pair_index,
                )
                episode = {
                    "pair_index": pair_index,
                    "position": len(episodes) + 1,
                    "repository": f"owner/repo-{pair_index}",
                    "case_id": case_id,
                    "run_id": run_id,
                    "condition": condition,
                    "method": method,
                    "seed": pair_index,
                    "progress_path": str(progress_path),
                }
                if pair_index == 2 and condition == "control":
                    episode["coordinator_wall_clock_comparable"] = False
                episodes.append(episode)
                outcomes.append(
                    {
                        "run_id": run_id,
                        "case_id": case_id,
                        "method": method,
                        "seed": pair_index,
                        "duration_seconds": 100.0 + pair_index,
                    }
                )
        write_json(progress_path, {"outcomes": outcomes})
        adjudication_path = root / "adjudication.json"
        write_json(
            adjudication_path,
            {
                "schema_version": "1.0.0",
                "study_id": "synthetic-paired-dev5",
                "claim_scope": "synthetic test",
                "conditions": {"treatment": "treatment", "control": "control"},
                "effective_episodes": episodes,
                "excluded_attempts": [],
            },
        )

        result = analyze_minimal_b_paired_dev5(adjudication_path, runs_root)

    primary = result["primary"]
    assert primary["by_condition"]["treatment"]["official_pass_at_1"] == 5
    assert primary["by_condition"]["control"]["official_pass_at_1"] == 4
    assert primary["paired_counts"]["treatment_only_pass"] == 1
    assert primary["exact_two_sided_mcnemar_p"] == 1.0
    assert result["resources"]["metrics"]["input_tokens"]["treatment"]["count"] == 5
    assert (
        result["resources"]["metrics"]["coordinator_wall_clock_seconds"]
        ["treatment"]["count"]
        == 4
    )
