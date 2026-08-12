#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ruff: noqa: E402 - workspace path bootstrapping precedes local imports.

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.utils.provenance import sha256_file

STUDY_ID = "envsolve-pro-certification-repair-ablation-v1-dev8"
SOURCE = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_minimal_b_v1_paired_53.jsonl"
)
SELECTED = ROOT / "experiments/cases/dev_pro_certification_repair_ablation_v1_8.jsonl"
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_certification_repair_ablation_v1_45.jsonl"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "local_mac_pro_certification_repair_ablation_v1_dev8.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_public_goal_v2.json"
DESIGN_FREEZE = (
    ROOT
    / "experiments/protocols/"
    "envsolve_pro_certification_repair_ablation_v1_design_freeze.json"
)
IMPLEMENTATION_FREEZE = (
    ROOT
    / "experiments/protocols/"
    "envsolve_pro_certification_repair_ablation_v1_implementation_freeze.json"
)
INFRASTRUCTURE_FREEZE = (
    ROOT
    / "experiments/protocols/"
    "codex_qualified_infrastructure_v1_freeze.json"
)
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_certification_repair_ablation_v1_dev8.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_dev8_preregistration.json"
)

EXPECTED_SOURCE_SHA256 = (
    "62932c34602538f0653c25cce71adc43aeb2d95113eb2bf6a48901a305e28115"
)
EXPECTED_DESIGN_SHA256 = (
    "84bef012853fbcf5e5737cde4bdcec6f290a87ad8b6d2ca19d212297aed4b765"
)
EXPECTED_IMPLEMENTATION_SHA256 = (
    "741481422cc9ddb755e3bff99e1f82ed43ea521121e207a370e0e832beb99bd0"
)
EXPECTED_INFRASTRUCTURE_SHA256 = (
    "855a4f63cf6cd7bfefe2a571f9b1c1278b96eaecc8a4438d505216e7e9b4cf70"
)
SALT = "envsolve-pro-certification-repair-ablation-v1-dev8-2026-08-05"
TAKE = 8
MODEL = "gpt-5.5"


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
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def _conditions(repository: str) -> list[dict[str, str]]:
    values = [
        {
            "condition": "A-strong-agent-control",
            "runner": "codex-cli-qualified",
            "method": "codex-cli-goal-aware",
        },
        {
            "condition": "B-one-shot-certification",
            "runner": "envsolve-pro-one-shot-certification-qualified",
            "method": "envsolve-pro-one-shot-certification-v1",
        },
        {
            "condition": "C-retryable-minimal-b",
            "runner": "envsolve-pro-minimal-b-qualified",
            "method": "envsolve-pro-minimal-b-v1",
        },
    ]
    offset = int(_digest(SALT, "condition-order", repository), 16) % len(values)
    return values[offset:] + values[:offset]


def _source_revision() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _reference(path: Path) -> dict[str, str]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
    }


def main() -> int:
    outputs = (SELECTED, REMAINING, SCHEDULE, PREREGISTRATION)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"Refusing to overwrite frozen output: {existing[0]}")
    expected = {
        SOURCE: EXPECTED_SOURCE_SHA256,
        DESIGN_FREEZE: EXPECTED_DESIGN_SHA256,
        IMPLEMENTATION_FREEZE: EXPECTED_IMPLEMENTATION_SHA256,
        INFRASTRUCTURE_FREEZE: EXPECTED_INFRASTRUCTURE_SHA256,
    }
    for path, digest in expected.items():
        if sha256_file(path) != digest:
            raise RuntimeError(f"Frozen input hash does not match: {path}")

    rows = _read_jsonl(SOURCE)
    if len(rows) != 53:
        raise RuntimeError("Unexpected untouched source pool size")
    repositories = [str(row["repository"]) for row in rows]
    if len(repositories) != len(set(repositories)):
        raise RuntimeError("Untouched pool contains duplicate repository identities")

    ranked = sorted(rows, key=lambda row: _digest(SALT, str(row["repository"])))
    selected = ranked[:TAKE]
    selected_repositories = {str(row["repository"]) for row in selected}
    remaining = [
        row for row in rows if str(row["repository"]) not in selected_repositories
    ]
    _write_jsonl(
        SELECTED,
        [
            {**row, "split": "dev-pro-certification-repair-ablation-v1-8"}
            for row in selected
        ],
    )
    _write_jsonl(
        REMAINING,
        [
            {
                **row,
                "split": (
                    "train-untouched-after-pro-certification-repair-"
                    "ablation-v1-45"
                ),
            }
            for row in remaining
        ],
    )

    ordered = sorted(
        selected,
        key=lambda row: _digest(SALT, "case-order", str(row["repository"])),
    )
    episodes: list[dict[str, Any]] = []
    for case_position, row in enumerate(ordered, start=1):
        repository = str(row["repository"])
        seed = int(_digest(SALT, "seed", repository)[:8], 16)
        host = "mac" if case_position % 2 else "spark"
        for condition in _conditions(repository):
            position = len(episodes) + 1
            episodes.append(
                {
                    "position": position,
                    "case_position": case_position,
                    "host": host,
                    "case_id": str(row["case_id"]),
                    **condition,
                    "run_id": (
                        f"pro-cert-repair-v1-dev8-{position:02d}-"
                        f"{condition['condition']}"
                    ),
                    "model": MODEL,
                    "seed": seed,
                }
            )

    write_json(
        SCHEDULE,
        {
            "schema_version": "1.0.0",
            "study_id": STUDY_ID,
            "case_file": str(SELECTED.relative_to(ROOT)),
            "case_file_sha256": sha256_file(SELECTED),
            "model": MODEL,
            "episode_timeout_seconds": 22400,
            "episodes": episodes,
        },
    )

    frozen_files = (
        CONFIG,
        PROTOCOL,
        DESIGN_FREEZE,
        IMPLEMENTATION_FREEZE,
        INFRASTRUCTURE_FREEZE,
        ROOT / "experiments/run_replay_ablation_case.py",
        ROOT / "experiments/run_replay_ablation_schedule.py",
        Path(__file__).resolve(),
    )
    write_json(
        PREREGISTRATION,
        {
            "schema_version": "1.0.0",
            "study_id": STUDY_ID,
            "status": "frozen-before-execution",
            "preregistered_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": _source_revision(),
            "claim_scope": "Repository-disjoint eight-case development mechanism gate.",
            "selection": {
                "source_case_file": str(SOURCE.relative_to(ROOT)),
                "source_case_file_sha256": sha256_file(SOURCE),
                "source_rows": len(rows),
                "selection_unit": "repository",
                "salt": SALT,
                "algorithm": "ascending SHA256(salt + NUL + repository)",
                "take": TAKE,
                "repository_content_or_outcome_used_for_selection": False,
                "failure_prescreen": False,
                "selected_before_execution": True,
                "selected_case_file": str(SELECTED.relative_to(ROOT)),
                "selected_case_file_sha256": sha256_file(SELECTED),
                "remaining_case_file": str(REMAINING.relative_to(ROOT)),
                "remaining_case_file_sha256": sha256_file(REMAINING),
            },
            "conditions": [
                {
                    "arm": "A",
                    "runner": "codex-cli-qualified",
                    "method": "codex-cli-goal-aware",
                    "generation_clean_replays": 0,
                },
                {
                    "arm": "B",
                    "runner": "envsolve-pro-one-shot-certification-qualified",
                    "method": "envsolve-pro-one-shot-certification-v1",
                    "maximum_executed_clean_replays": 1,
                },
                {
                    "arm": "C",
                    "runner": "envsolve-pro-minimal-b-qualified",
                    "method": "envsolve-pro-minimal-b-v1",
                    "clean_replays_repeatable": True,
                },
            ],
            "mechanism_decision": {
                "support_rule": (
                    "Arm C first replay Fail/Unknown, later different replay Pass, "
                    "and final Official Pass."
                ),
                "all_first_replays_pass": (
                    "No iterative-repair evidence; do not add structured state."
                ),
            },
            "analysis_policy": {
                "paired_by_repository": True,
                "case_order": "frozen salted-hash order",
                "condition_order": "frozen per-repository salted rotation",
                "all_24_episodes_before_algorithm_change": True,
                "individual_case_rules_forbidden": True,
                "case_replacement": False,
                "official_and_integrity_outcomes_reported_separately": True,
                "infrastructure_unknown_excluded_from_effect_denominator": True,
                "identical_infrastructure_retry_requires_frozen_amendment": True,
            },
            "artifacts": {
                "config": _reference(CONFIG),
                "protocol": _reference(PROTOCOL),
                "design_freeze": _reference(DESIGN_FREEZE),
                "implementation_freeze": _reference(IMPLEMENTATION_FREEZE),
                "infrastructure_freeze": _reference(INFRASTRUCTURE_FREEZE),
                "schedule": _reference(SCHEDULE),
                "freeze_files": {
                    str(path.relative_to(ROOT)): sha256_file(path)
                    for path in frozen_files
                },
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
