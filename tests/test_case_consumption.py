from __future__ import annotations

import json
from pathlib import Path

import pytest

from envsolve_harness.case_consumption import (
    audit_case_consumption,
    read_case_ids,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_registry_and_provider_trajectory_are_consumption_evidence(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    write_json(
        registry,
        {
            "trajectories": [
                {
                    "case_id": "case-registry",
                    "run_id": "prior-run",
                    "observed_attempt_count": 1,
                },
                {
                    "case_id": "case-metadata-only",
                    "artifact_root": "/tmp/pre-agent-artifact",
                    "observed_attempt_count": 0,
                },
            ]
        },
    )
    artifact = tmp_path / "runs" / "run-live" / "artifact"
    write_json(artifact / "inputs" / "case.json", {"case_id": "case-live"})
    write_jsonl(
        artifact / "generation" / "trajectory.jsonl",
        [{"event": "provider_response", "request_index": 1}],
    )

    report = audit_case_consumption(
        ["case-registry", "case-live", "case-metadata-only", "case-new"],
        registry_paths=[registry],
        runs_roots=[tmp_path / "runs"],
    )

    by_id = {row["case_id"]: row for row in report["cases"]}
    assert report["consumed_count"] == 2
    assert by_id["case-registry"]["consumed"] is True
    assert by_id["case-live"]["consumed"] is True
    assert by_id["case-metadata-only"]["consumed"] is False
    assert by_id["case-new"]["consumed"] is False


def test_manifest_or_tool_only_trajectory_does_not_count(tmp_path: Path) -> None:
    artifact = tmp_path / "runs" / "run-pre-agent" / "artifact"
    write_json(artifact / "inputs" / "case.json", {"case_id": "case-a"})
    write_json(artifact / "manifest.json", {"case": {"case_id": "case-a"}})
    write_jsonl(
        artifact / "generation" / "trajectory.jsonl",
        [{"event": "tool_result", "request_index": 0}],
    )

    report = audit_case_consumption(["case-a"], runs_roots=[tmp_path / "runs"])

    assert report["consumed_count"] == 0
    assert report["cases"][0]["evidence"] == []


def test_read_case_ids_rejects_duplicates(tmp_path: Path) -> None:
    case_file = tmp_path / "cases.jsonl"
    write_jsonl(case_file, [{"case_id": "case-a"}, {"case_id": "case-a"}])

    with pytest.raises(ValueError, match="Duplicate case identity"):
        read_case_ids(case_file)
