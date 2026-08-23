from __future__ import annotations

from pathlib import Path
import tempfile
from unittest import mock

import pytest

from envsolve_harness.audit import AuditReport
from envsolve_harness.core.io import write_json
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.verifier_handoff_screen import (
    adjudicate_screen,
    build_paired_schedule,
)


def _run(position: int, terminal: str, eligible: bool = True) -> dict[str, object]:
    return {
        "position": position,
        "case_id": f"envbench-python-owner__repo{position}@abc{position}",
        "run_id": f"screen-{position}",
        "method": "envsolve-pro-scheduled-compatibility-observation",
        "seed": 640000 + position,
        "artifact_integrity_valid": True,
        "scientifically_eligible": eligible,
        "descriptive_terminal": terminal,
    }


def test_adjudicates_pass_noncompletion_and_exact_official_retry() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        schedule = root / "schedule.json"
        runs_root = root / "runs"
        write_json(schedule, {"study_id": "screen", "episodes": []})
        source_runs = [
            _run(1, "infrastructure_unknown"),
            _run(2, "generation_failed"),
            _run(3, "official_pass"),
        ]
        retry_id = "screen-1-official-retry1"
        retry_root = runs_root / safe_name(retry_id) / safe_name(
            str(source_runs[0]["case_id"])
        )
        write_json(
            retry_root / "manifest.json",
            {
                "run": {
                    "run_id": retry_id,
                    "method": source_runs[0]["method"],
                    "seed": source_runs[0]["seed"],
                },
                "case": {"case_id": source_runs[0]["case_id"]},
                "result": {"evaluation_completed": True, "official_pass": True},
            },
        )
        write_json(
            retry_root / "inputs" / "evaluation_retry.json",
            {
                "policy": "single-exact-script-infrastructure-retry-v1",
                "source_run_id": source_runs[0]["run_id"],
                "source_case_id": source_runs[0]["case_id"],
                "source_method": source_runs[0]["method"],
                "model_reexecuted": False,
                "infrastructure_signature": "read-timeout",
            },
        )
        with (
            mock.patch(
                "envsolve_harness.verifier_handoff_screen.summarize_schedule",
                return_value={"runs": source_runs},
            ),
            mock.patch(
                "envsolve_harness.verifier_handoff_screen.audit_run",
                return_value=AuditReport(valid=True),
            ),
        ):
            result = adjudicate_screen(
                schedule,
                runs_root,
                official_retries={"screen-1": retry_id},
            )

    assert result["counts"] == {
        "scheduled": 3,
        "scientifically_eligible": 3,
        "official_pass": 2,
        "official_fail": 1,
        "censored": 0,
        "official_only_retries": 1,
    }
    assert result["bad_case_ids"] == [source_runs[1]["case_id"]]


def test_rejects_retry_for_a_scientific_failure() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        schedule = root / "schedule.json"
        write_json(schedule, {"study_id": "screen", "episodes": []})
        with mock.patch(
            "envsolve_harness.verifier_handoff_screen.summarize_schedule",
            return_value={"runs": [_run(1, "generation_failed")]},
        ):
            with pytest.raises(ValueError, match="cannot replace terminal"):
                adjudicate_screen(
                    schedule,
                    root / "runs",
                    official_retries={"screen-1": "retry-1"},
                )


def test_builds_alternating_fresh_pair_schedule() -> None:
    cases = [
        "envbench-python-owner__alpha@abc",
        "envbench-python-owner__beta@def",
    ]
    paired = build_paired_schedule(
        {"study_id": "screen", "bad_case_ids": cases},
        {
            "case_file": "cases.jsonl",
            "case_file_sha256": "existing-value",
            "episode_timeout_seconds": 23000,
            "model": "model",
            "required_environment": {"KEY": "present-not-recorded"},
        },
    )

    episodes = paired["episodes"]
    assert [item["arm"] for item in episodes] == [
        "S-OBS",
        "H-VH",
        "H-VH",
        "S-OBS",
    ]
    assert episodes[0]["seed"] == episodes[1]["seed"]
    assert episodes[2]["seed"] == episodes[3]["seed"]
    assert len({item["run_id"] for item in episodes}) == 4
