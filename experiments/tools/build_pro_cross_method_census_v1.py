#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    ROOT / "experiments/cases/dev_pro_trajectory_census_v1_8.jsonl",
    ROOT / "experiments/cases/dev_pro_trajectory_census_replication_v1_8.jsonl",
)
CASE_FILE = ROOT / "experiments/cases/dev_pro_cross_method_census_v1_16.jsonl"
OUTPUT_ROOT = ROOT / "experiments/validations"
SALT = "envsolve-pro-cross-method-census-v1-2026-07-23"
IMPLEMENTATION_COMMIT = "f114256d7b938d0a8f52c1e22e0cc985cc82e6eb"
MODEL = "deepseek/deepseek-v4-pro"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ordered_cases() -> list[dict[str, Any]]:
    records = [record for source in SOURCES for record in read_jsonl(source)]
    identities = [str(record["case_id"]) for record in records]
    if len(records) != 16 or len(set(identities)) != 16:
        raise ValueError("Cross-method census requires 16 unique consumed cases")
    return sorted(
        records,
        key=lambda item: hashlib.sha256(
            f"{SALT}\0{item['case_id']}".encode()
        ).hexdigest(),
    )


def write_case_file(cases: list[dict[str, Any]]) -> None:
    values = [
        {
            **case,
            "split": "dev-pro-cross-method-census-v1-16-consumed",
        }
        for case in cases
    ]
    CASE_FILE.write_text(
        "".join(
            json.dumps(item, separators=(",", ":"), sort_keys=True) + "\n"
            for item in values
        ),
        encoding="utf-8",
    )


def episode(
    case: dict[str, Any],
    *,
    case_index: int,
    position: int,
    runner: str,
    method: str,
    method_id: str,
    model: str,
) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "case_index": case_index,
        "checkout": IMPLEMENTATION_COMMIT,
        "host": "bound-at-execution",
        "method": method,
        "method_id": method_id,
        "model": model,
        "position": position,
        "run_id": f"pro-cross-method-v1-c{case_index:02d}-{method_id}",
        "runner": runner,
        "seed": 0 if runner == "envsolve" else None,
    }


def schedule(
    cases: list[dict[str, Any]],
    *,
    schedule_id: str,
    runner: str,
    method: str,
    method_id: str,
    model: str,
    include: Any = lambda _index: True,
) -> dict[str, Any]:
    selected = [
        (index, case)
        for index, case in enumerate(cases, start=1)
        if include(index)
    ]
    episodes = [
        episode(
            case,
            case_index=case_index,
            position=position,
            runner=runner,
            method=method,
            method_id=method_id,
            model=model,
        )
        for position, (case_index, case) in enumerate(selected, start=1)
    ]
    return {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-cross-method-census-v1",
        "schedule_id": schedule_id,
        "claim_scope": "Consumed development trajectory diagnostics only",
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "case_file": str(CASE_FILE.relative_to(ROOT)),
        "case_file_sha256": sha256_file(CASE_FILE),
        "episode_timeout_seconds": 21600,
        "episodes": episodes,
    }


def main() -> None:
    cases = ordered_cases()
    write_case_file(cases)
    schedules = {
        "pro_cross_method_census_v1_codex_schedule.json": schedule(
            cases,
            schedule_id="codex-mac-16",
            runner="codex-cli",
            method="codex-cli-native",
            method_id="codex-cli-native",
            model="gpt-5.5",
        ),
        "pro_cross_method_census_v1_envsolve_schedule.json": schedule(
            cases,
            schedule_id="envsolve-spark-16",
            runner="envsolve",
            method="envsolve-pro-causal",
            method_id="envsolve-pro-causal-v3",
            model=MODEL,
        ),
        "pro_cross_method_census_v1_repo2run_lane1_schedule.json": schedule(
            cases,
            schedule_id="repo2run-spark-odd-8",
            runner="repo2run",
            method="repo2run",
            method_id="repo2run-reproduced-open",
            model=MODEL,
            include=lambda index: index % 2 == 1,
        ),
        "pro_cross_method_census_v1_repo2run_lane2_schedule.json": schedule(
            cases,
            schedule_id="repo2run-spark-even-8",
            runner="repo2run",
            method="repo2run",
            method_id="repo2run-reproduced-open",
            model=MODEL,
            include=lambda index: index % 2 == 0,
        ),
    }
    for name, value in schedules.items():
        write_json(OUTPUT_ROOT / name, value)

    write_json(
        OUTPUT_ROOT / "pro_cross_method_census_v1_selection.json",
        {
            "schema_version": "1.0.0",
            "study_id": "envsolve-pro-cross-method-census-v1",
            "selection_kind": "complete reuse of two previously consumed censuses",
            "salted_execution_order": SALT,
            "sources": [
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256_file(path),
                }
                for path in SOURCES
            ],
            "case_file": str(CASE_FILE.relative_to(ROOT)),
            "case_file_sha256": sha256_file(CASE_FILE),
            "case_count": len(cases),
            "case_ids": [case["case_id"] for case in cases],
            "new_untouched_cases_consumed": 0,
            "schedules": {
                name: sha256_file(OUTPUT_ROOT / name) for name in schedules
            },
        },
    )


if __name__ == "__main__":
    main()
