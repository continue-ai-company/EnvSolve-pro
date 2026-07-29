#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


# ruff: noqa: E402 - workspace path bootstrapping precedes local imports.

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.utils.provenance import sha256_file


SOURCE = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_execution_feedback_v3_screen8_74.jsonl"
)
SELECTED = (
    ROOT
    / "experiments/cases/"
    "dev_pro_execution_feedback_v3_spark4.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_execution_feedback_v3_spark4_70.jsonl"
)
PARENT = (
    ROOT
    / "experiments/validations/"
    "pro_execution_feedback_v3_screen8_preregistration.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_execution_feedback_v3_spark4_preregistration.json"
)
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_execution_feedback_v3_spark4.json"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "spark_pro_execution_feedback_v3_deepseek_direct.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_official_v1.json"

EXPECTED_SOURCE_SHA256 = (
    "dfe5f50717ae1e47f6a96b89b7db2baf"
    "9a68c0d0cfbdc568cbc842d7cebdf038"
)
SALT = "envsolve-pro-execution-feedback-v3-spark4-2026-07-29"
TAKE = 4


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def main() -> int:
    if sha256_file(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched source pool hash does not match")
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    treatment_hashes = parent["algorithm_freeze"]["treatment_files"]
    actual_hashes = {
        relative: sha256_file(ROOT / relative)
        for relative in treatment_hashes
    }
    if actual_hashes != treatment_hashes:
        raise RuntimeError("Execution-feedback-v3 changed after parent freeze")

    rows = _read_jsonl(SOURCE)
    if len(rows) != 74:
        raise RuntimeError("Unexpected untouched source pool size")
    ranked = sorted(
        rows,
        key=lambda row: _digest(SALT, str(row["case_id"])),
    )
    selected = ranked[:TAKE]
    selected_ids = {str(row["case_id"]) for row in selected}
    remaining = [
        row for row in rows if str(row["case_id"]) not in selected_ids
    ]
    if len(remaining) != 70:
        raise RuntimeError("Selection did not preserve the untouched remainder")
    _write_jsonl(
        SELECTED,
        [
            {
                **row,
                "split": "dev-pro-execution-feedback-v3-spark4",
            }
            for row in selected
        ],
    )
    _write_jsonl(
        REMAINING,
        [
            {
                **row,
                "split": (
                    "train-untouched-after-pro-execution-feedback-v3-spark4-70"
                ),
            }
            for row in remaining
        ],
    )

    episodes: list[dict[str, Any]] = []
    for row in sorted(
        selected,
        key=lambda item: _digest(
            SALT,
            "case-order",
            str(item["case_id"]),
        ),
    ):
        case_id = str(row["case_id"])
        conditions = [
            {
                "condition": "goal-frontier-v1-control",
                "runner": "envsolve-pro-goal-frontier",
                "method": "envsolve-pro-goal-frontier",
            },
            {
                "condition": "execution-feedback-v3",
                "runner": "envsolve-pro-execution-feedback",
                "method": "envsolve-pro-execution-feedback-v3",
            },
        ]
        if int(_digest(SALT, "condition-order", case_id), 16) % 2:
            conditions.reverse()
        for condition in conditions:
            position = len(episodes) + 1
            label = str(condition["condition"])
            episodes.append(
                {
                    "position": position,
                    "host": "spark",
                    "case_id": case_id,
                    **condition,
                    "run_id": (
                        f"pro-execution-feedback-v3-spark4-{position:02d}-"
                        f"{label}"
                    ),
                    "model": "deepseek-v4-pro",
                    "seed": 1,
                }
            )

    schedule = {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-execution-feedback-v3-spark4",
        "case_file": str(SELECTED.relative_to(ROOT)),
        "case_file_sha256": sha256_file(SELECTED),
        "model": "deepseek-v4-pro",
        "episode_timeout_seconds": 22_800,
        "episodes": episodes,
    }
    write_json(SCHEDULE, schedule)
    payload = {
        "schema_version": "1.0.0",
        "study_id": schedule["study_id"],
        "status": "preregistered",
        "preregistered_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": (
            "Repository-disjoint supplementary development screen under "
            "concurrent Spark load; Official Pass is primary and resource "
            "metrics are descriptive only."
        ),
        "parent_freeze": {
            "path": str(PARENT.relative_to(ROOT)),
            "sha256": sha256_file(PARENT),
            "treatment_files": actual_hashes,
        },
        "selection": {
            "source_case_file": str(SOURCE.relative_to(ROOT)),
            "source_case_file_sha256": sha256_file(SOURCE),
            "source_rows": len(rows),
            "salt": SALT,
            "algorithm": "ascending SHA256(salt + NUL + case_id)",
            "take": TAKE,
            "repository_content_or_outcome_used_for_selection": False,
            "selected_before_execution": True,
            "selected_case_file": str(SELECTED.relative_to(ROOT)),
            "selected_case_file_sha256": sha256_file(SELECTED),
            "remaining_case_file": str(REMAINING.relative_to(ROOT)),
            "remaining_case_file_sha256": sha256_file(REMAINING),
        },
        "execution": {
            "host": "spark",
            "concurrent_with": (
                "envsolve-pro-execution-feedback-v3-screen8-spark"
            ),
            "config": str(CONFIG.relative_to(ROOT)),
            "config_sha256": sha256_file(CONFIG),
            "protocol": str(PROTOCOL.relative_to(ROOT)),
            "protocol_sha256": sha256_file(PROTOCOL),
            "schedule": str(SCHEDULE.relative_to(ROOT)),
            "schedule_sha256": sha256_file(SCHEDULE),
            "success_metric_unaffected_by_host_concurrency": True,
            "resource_metrics_comparable_as_primary": False,
        },
        "conditions": parent["conditions"],
        "analysis": {
            "primary_metric": "Official Pass@1",
            "paired_unit": "repository",
            "provider_censoring_excluded": True,
            "official_evaluator_feedback_used_online": False,
            "posthoc_case_replacement": False,
        },
        "episodes": episodes,
    }
    write_json(PREREGISTRATION, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
