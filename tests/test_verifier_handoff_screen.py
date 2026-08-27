from __future__ import annotations

from pathlib import Path
import tempfile
from unittest import mock

import pytest

from envsolve_harness.audit import AuditReport
from envsolve_harness.core.io import write_json
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.verifier_handoff_screen import (
    adjudicate_paired_schedule,
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


def test_adjudicates_official_and_protocol_compliant_pair_tables() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        schedule = root / "schedule.json"
        runs_root = root / "runs"
        episodes = []
        source_runs = []
        for pair_index in range(1, 4):
            for arm, method in (
                ("S-OBS", "envsolve-pro-scheduled-compatibility-observation"),
                ("H-VH", "envsolve-pro-verifier-triggered-handoff"),
            ):
                position = len(episodes) + 1
                run_id = f"pair-{pair_index}-{arm}"
                case_id = f"envbench-python-owner__repo{pair_index}@abc"
                episodes.append(
                    {
                        "position": position,
                        "pair_index": pair_index,
                        "pair_id": f"pair-{pair_index}",
                        "pair_position": 1 if arm == "S-OBS" else 2,
                        "arm": arm,
                        "case_id": case_id,
                        "run_id": run_id,
                        "method": method,
                        "seed": 650000 + pair_index,
                    }
                )
                terminal = "official_pass"
                if pair_index == 3 and arm == "S-OBS":
                    terminal = "infrastructure_unknown"
                if pair_index == 3 and arm == "H-VH":
                    terminal = "official_fail"
                source_runs.append(
                    {
                        **_run(position, terminal),
                        "pair_index": pair_index,
                        "case_id": case_id,
                        "run_id": run_id,
                        "method": method,
                        "seed": 650000 + pair_index,
                    }
                )
        write_json(schedule, {"study_id": "paired", "episodes": episodes})
        retry_id = "pair-3-S-OBS-official-retry1"
        retry_root = runs_root / safe_name(retry_id) / safe_name(
            str(episodes[4]["case_id"])
        )
        write_json(
            retry_root / "manifest.json",
            {
                "run": {
                    "run_id": retry_id,
                    "method": episodes[4]["method"],
                    "seed": episodes[4]["seed"],
                },
                "case": {"case_id": episodes[4]["case_id"]},
                "result": {"evaluation_completed": True, "official_pass": True},
            },
        )
        write_json(
            retry_root / "inputs" / "evaluation_retry.json",
            {
                "policy": "single-exact-script-infrastructure-retry-v1",
                "source_run_id": episodes[4]["run_id"],
                "source_case_id": episodes[4]["case_id"],
                "source_method": episodes[4]["method"],
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
            result = adjudicate_paired_schedule(
                schedule,
                runs_root,
                official_retries={episodes[4]["run_id"]: retry_id},
                protocol_invalid={
                    episodes[2]["run_id"]: "manual-site-packages-stub-provider",
                    episodes[3]["run_id"]: "manual-site-packages-stub-provider",
                },
            )

    assert result["official_paired"] == {
        "pairs": 3,
        "eligible_pairs": 3,
        "censored_pairs": 0,
        "control_passes": 3,
        "treatment_passes": 2,
        "both_pass": 2,
        "control_only_pass": 1,
        "treatment_only_pass": 0,
        "neither_pass": 0,
        "control_pass_rate": 1.0,
        "treatment_pass_rate": 2 / 3,
        "treatment_minus_control_pass_rate": -1 / 3,
        "discordant_pairs": 1,
        "mcnemar_exact_two_sided_p_value": 1.0,
    }
    assert result["protocol_compliant_paired"] == {
        "pairs": 3,
        "eligible_pairs": 3,
        "censored_pairs": 0,
        "control_passes": 2,
        "treatment_passes": 1,
        "both_pass": 1,
        "control_only_pass": 1,
        "treatment_only_pass": 0,
        "neither_pass": 1,
        "control_pass_rate": 2 / 3,
        "treatment_pass_rate": 1 / 3,
        "treatment_minus_control_pass_rate": -1 / 3,
        "discordant_pairs": 1,
        "mcnemar_exact_two_sided_p_value": 1.0,
    }


def test_accepts_explicit_arm_labels_and_reports_common_success_resources() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        schedule = root / "schedule.json"
        case_id = "envbench-python-owner__repo@abc"
        episodes = [
            {
                "position": 1,
                "pair_index": 1,
                "pair_id": "pair-1",
                "pair_position": 1,
                "arm": "A-F+O",
                "case_id": case_id,
                "run_id": "control",
            },
            {
                "position": 2,
                "pair_index": 1,
                "pair_id": "pair-1",
                "pair_position": 2,
                "arm": "B-F+O+H+R",
                "case_id": case_id,
                "run_id": "treatment",
            },
        ]
        source_runs = [
            {
                **_run(index, "official_pass"),
                "case_id": case_id,
                "run_id": episode["run_id"],
            }
            for index, episode in enumerate(episodes, start=1)
        ]
        write_json(schedule, {"study_id": "custom-arms", "episodes": episodes})

        def metrics(_root: Path, run_id: str, _case_id: str) -> dict[str, object]:
            value = 10 if run_id == "control" else 20
            return {
                "generation_seconds": value,
                "official_seconds": value / 2,
                "model_requests": value,
                "token_usage": {"total_tokens": value * 100},
            }

        with (
            mock.patch(
                "envsolve_harness.verifier_handoff_screen.summarize_schedule",
                return_value={"runs": source_runs},
            ),
            mock.patch(
                "envsolve_harness.verifier_handoff_screen._run_metrics",
                side_effect=metrics,
            ),
        ):
            result = adjudicate_paired_schedule(
                schedule,
                root / "runs",
                control_arm="A-F+O",
                treatment_arm="B-F+O+H+R",
            )

    assert result["arms"] == {
        "control": "A-F+O",
        "treatment": "B-F+O+H+R",
    }
    assert result["official_paired"]["both_pass"] == 1
    assert result["official_paired"]["mcnemar_exact_two_sided_p_value"] == 1.0
    resources = result["resources"]["common_success"]
    assert resources["pairs"] == 1
    assert resources["control"]["model_requests"]["mean"] == 10
    assert resources["treatment"]["total_tokens"]["mean"] == 2000


def test_resource_summary_ignores_boolean_metric_values() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        schedule = root / "schedule.json"
        case_id = "envbench-python-owner__repo@abc"
        episodes = [
            {
                "position": position,
                "pair_index": 1,
                "pair_id": "pair-1",
                "pair_position": position,
                "arm": arm,
                "case_id": case_id,
                "run_id": run_id,
            }
            for position, (arm, run_id) in enumerate(
                (("A", "control"), ("B", "treatment")), start=1
            )
        ]
        source_runs = [
            {
                **_run(index, "official_pass"),
                "case_id": case_id,
                "run_id": episode["run_id"],
            }
            for index, episode in enumerate(episodes, start=1)
        ]
        write_json(schedule, {"study_id": "boolean-metrics", "episodes": episodes})

        with (
            mock.patch(
                "envsolve_harness.verifier_handoff_screen.summarize_schedule",
                return_value={"runs": source_runs},
            ),
            mock.patch(
                "envsolve_harness.verifier_handoff_screen._run_metrics",
                return_value={"model_requests": True},
            ),
        ):
            result = adjudicate_paired_schedule(
                schedule,
                root / "runs",
                control_arm="A",
                treatment_arm="B",
            )

    assert result["resources"]["common_success"]["control"]["model_requests"] is None


def test_rejects_unknown_protocol_invalid_run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        schedule = root / "schedule.json"
        write_json(schedule, {"study_id": "paired", "episodes": []})
        with mock.patch(
            "envsolve_harness.verifier_handoff_screen.summarize_schedule",
            return_value={"runs": []},
        ):
            with pytest.raises(ValueError, match="unknown runs"):
                adjudicate_paired_schedule(
                    schedule,
                    root / "runs",
                    protocol_invalid={"not-scheduled": "reason"},
                )
