from __future__ import annotations

import json
from pathlib import Path

from experiments.analyze_cross_method_census import (
    analyze,
    candidate_verifications,
    load_attempt_overrides,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_candidate_verifications_supports_both_effect_audit_layouts(
    tmp_path: Path,
) -> None:
    path = tmp_path / "episode.jsonl"
    events = []
    for index, verifier_details in enumerate(
        (
            {"repository_effect_audit": {"valid": True}},
            {"report_details": {"repository_effect_audit": {"valid": False}}},
        ),
        start=1,
    ):
        events.append(
            {
                "event_type": "verification_recorded",
                "payload": {
                    "details": {
                        "candidate_id": f"candidate-{index:04d}",
                        "bootstrap_exit_code": 0,
                        "candidate_assessment": {
                            "admissible": index == 1,
                            "unresolved_constraints": index,
                        },
                        "verifier_details": verifier_details,
                    }
                },
            }
        )
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    candidates = candidate_verifications(path)
    assert [candidate["effect_valid"] for candidate in candidates] == [True, False]
    assert candidates[0]["admissible"] is True
    assert candidates[1]["unresolved_constraints"] == 2


def test_analyze_builds_measurement_matrix_without_causal_labels(
    tmp_path: Path,
) -> None:
    case_id = "envbench-python-owner__repo@abc"
    run_id = "run-one"
    schedule = tmp_path / "schedule.json"
    runs = tmp_path / "runs"
    root = runs / run_id / "envbench-python-owner__repo__abc"
    _write(
        schedule,
        {
            "episodes": [
                {
                    "case_id": case_id,
                    "case_index": 1,
                    "method": "method",
                    "method_id": "method-v1",
                    "model": "model",
                    "run_id": run_id,
                }
            ]
        },
    )
    _write(
        root / "generation/result.json",
        {
            "generation_completed": True,
            "metadata": {
                "started_at": "2026-07-23T00:00:00+00:00",
                "finished_at": "2026-07-23T00:00:12+00:00",
                "token_usage": {"input_tokens": 10, "output_tokens": 2},
            },
        },
    )
    _write(
        root / "evaluation/result.json",
        {
            "evaluation_completed": True,
            "official_pass": False,
            "raw_metrics": {"exit_code": 0, "issues_count": 1},
            "evidence": [
                {
                    "verifier_id": "envbench-pyright-diagnostic",
                    "metrics": {"missing_import_modules": ["missing_package"]},
                }
            ],
        },
    )
    script = root / "scripts/generated.sh"
    script.parent.mkdir(parents=True)
    script.write_text("python -m pip install .\n", encoding="utf-8")

    result = analyze([schedule], [runs])

    assert result["classification_policy"].startswith("No automatic")
    assert result["aggregate"]["method-v1"]["official_passes"] == 0
    record = result["records"][0]
    assert record["terminal"] == "official_fail"
    assert record["official_metrics"]["issues_count"] == 1
    assert record["missing_import_modules"] == ["missing_package"]
    assert record["resources"]["generation_wall_seconds"] == 12
    assert record["final_program"]["nonblank_line_count"] == 1


def test_analyze_can_join_generation_and_evaluation_only_retry(
    tmp_path: Path,
) -> None:
    case_id = "envbench-python-owner__repo@abc"
    scheduled_run_id = "scheduled-run"
    generation_run_id = "generation-attempt"
    evaluation_run_id = "evaluation-only-retry"
    schedule = tmp_path / "schedule.json"
    runs = tmp_path / "runs"
    case_root = "envbench-python-owner__repo__abc"
    generation_root = runs / generation_run_id / case_root
    evaluation_root = runs / evaluation_run_id / case_root
    _write(
        schedule,
        {
            "episodes": [
                {
                    "case_id": case_id,
                    "case_index": 1,
                    "method": "method",
                    "method_id": "method-v1",
                    "model": "model",
                    "run_id": scheduled_run_id,
                }
            ]
        },
    )
    _write(
        generation_root / "generation/result.json",
        {
            "generation_completed": True,
            "metadata": {
                "started_at": "2026-07-23T00:00:00+00:00",
                "finished_at": "2026-07-23T00:00:07+00:00",
            },
        },
    )
    script = generation_root / "scripts/generated.sh"
    script.parent.mkdir(parents=True)
    script.write_text("python -m pip install .\n", encoding="utf-8")
    _write(
        evaluation_root / "evaluation/result.json",
        {
            "evaluation_completed": True,
            "official_pass": True,
            "raw_metrics": {"exit_code": 0, "issues_count": 0},
        },
    )

    result = analyze(
        [schedule],
        [runs],
        attempt_overrides={
            scheduled_run_id: {
                "generation_run_id": generation_run_id,
                "evaluation_run_id": evaluation_run_id,
            }
        },
    )

    record = result["records"][0]
    assert record["terminal"] == "official_pass"
    assert record["generation_run_id"] == generation_run_id
    assert record["evaluation_run_id"] == evaluation_run_id
    assert record["resources"]["generation_wall_seconds"] == 7
    assert record["final_program"]["nonblank_line_count"] == 1
    assert record["evidence_sha256"]["generation/result.json"]
    assert record["evidence_sha256"]["evaluation/result.json"]


def test_load_attempt_overrides_accepts_adjudication_record(tmp_path: Path) -> None:
    path = tmp_path / "adjudication.json"
    _write(
        path,
        {
            "schema": "attempt-adjudication-v1",
            "attempt_overrides": {
                "scheduled-run": {
                    "generation_run_id": "generation-attempt",
                    "evaluation_run_id": "evaluation-only-retry",
                }
            },
        },
    )

    assert load_attempt_overrides(path) == {
        "scheduled-run": {
            "generation_run_id": "generation-attempt",
            "evaluation_run_id": "evaluation-only-retry",
        }
    }
