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
    "train_untouched_after_pro_operation_relevance_contract_v1_86.jsonl"
)
SELECTED = ROOT / "experiments/cases/dev_pro_goal_frontier_v1_pilot2.jsonl"
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_goal_frontier_v1_pilot_84.jsonl"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_goal_frontier_v1_pilot_preregistration.json"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "local_mac_pro_operation_relevance_v1_deepseek_direct.json"
)
PROTOCOL = (
    ROOT / "experiments/protocols/envbench_python_official_v1.json"
)

EXPECTED_SOURCE_SHA256 = (
    "c1d02f8bd156d2b54245519660cd42414"
    "dfc9db6189043c65a204f91d12b3b1f"
)
SALT = "envsolve-pro-goal-frontier-v1-pilot-2026-07-28"
TAKE = 2
ALGORITHM_FILES = (
    "envsolve/constraints/goal_frontier.py",
    "envsolve/runtime/goal_frontier_policy.py",
    "envsolve/tools/run_envsolve_goal_frontier_episode.py",
    "envsolve_harness/runners/envsolve_pro_goal_frontier.py",
    "experiments/run_goal_frontier_case.py",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def main() -> int:
    if sha256_file(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched source pool hash does not match")
    rows = _read_jsonl(SOURCE)
    if len(rows) != 86:
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
    if len(remaining) != 84:
        raise RuntimeError("Selection did not preserve the untouched remainder")

    _write_jsonl(
        SELECTED,
        [
            {
                **row,
                "split": "dev-pro-goal-frontier-v1-pilot2",
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
                    "train-untouched-after-pro-goal-frontier-v1-pilot-84"
                ),
            }
            for row in remaining
        ],
    )

    episodes = []
    position = 1
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
                "condition": "frozen-fresh-control",
                "runner": "envsolve",
                "method": "envsolve-pro-goal-contract-evidence-anchor",
            },
            {
                "condition": "goal-frontier-v1",
                "runner": "envsolve-pro-goal-frontier",
                "method": "envsolve-pro-goal-frontier",
            },
        ]
        if int(_digest(SALT, "condition-order", case_id), 16) % 2:
            conditions.reverse()
        for condition in conditions:
            label = str(condition["condition"])
            episodes.append(
                {
                    "position": position,
                    "case_id": case_id,
                    **condition,
                    "run_id": (
                        f"pro-goal-frontier-v1-pilot-{position:02d}-"
                        f"{label}"
                    ),
                    "model": "deepseek-v4-pro",
                    "seed": 1,
                }
            )
            position += 1

    payload = {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-goal-frontier-v1-pilot",
        "status": "preregistered",
        "preregistered_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": (
            "Repository-disjoint development pilot only; consumed-trajectory "
            "mechanism check, not final test or leaderboard evidence."
        ),
        "selection": {
            "source_case_file": str(SOURCE.relative_to(ROOT)),
            "source_case_file_sha256": sha256_file(SOURCE),
            "source_rows": len(rows),
            "selection_unit": "case_id",
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
        "algorithm_freeze": {
            "treatment_files": {
                relative: sha256_file(ROOT / relative)
                for relative in ALGORITHM_FILES
            },
            "frozen_control_protocol": (
                "experiments/protocols/"
                "pro_operation_relevance_contract_v1_freeze.json"
            ),
            "frozen_control_protocol_sha256": sha256_file(
                ROOT
                / "experiments/protocols/"
                "pro_operation_relevance_contract_v1_freeze.json"
            ),
        },
        "conditions": [
            {
                "condition": "frozen-fresh-control",
                "runner": "envsolve",
                "method": "envsolve-pro-goal-contract-evidence-anchor",
                "constraint_profile": "flat",
                "operation_profile": "free-form",
            },
            {
                "condition": "goal-frontier-v1",
                "runner": "envsolve-pro-goal-frontier",
                "method": "envsolve-pro-goal-frontier",
                "constraint_profile": "goal-obligation-frontier-v1",
                "operation_profile": "open-program",
            },
        ],
        "shared_contract": {
            "model": "deepseek-v4-pro",
            "provider": "DeepSeek direct",
            "seed": 1,
            "config": str(CONFIG.relative_to(ROOT)),
            "config_sha256": sha256_file(CONFIG),
            "protocol": str(PROTOCOL.relative_to(ROOT)),
            "protocol_sha256": sha256_file(PROTOCOL),
            "public_executable_goal": True,
            "repository_evidence": "constraint-routed",
            "candidate_anchor": "retained-admissible",
            "candidate_interface": "open-program",
            "candidate_retention": "best-admissible",
            "environment_strategy": "fresh-candidate",
            "max_candidates": 12,
            "max_environments": 24,
            "max_commands": 24,
            "generation_timeout_seconds": 18_000,
            "candidate_command_timeout_seconds": 1_200,
            "token_policy": (
                "Tokens and price are reported outcomes; configured limits "
                "are emergency guards, not research stopping thresholds."
            ),
        },
        "hypothesis": {
            "problem": (
                "Raw executable-goal findings amplify repeated source "
                "surfaces and induce package-by-symptom planning."
            ),
            "mechanism": (
                "Compress all active findings into lossless namespace-level "
                "goal obligations with source-role evidence, while preserving "
                "the strong model's open Bash action space."
            ),
            "primary": (
                "Goal-frontier-v1 improves or preserves Official Pass "
                "relative to the frozen fresh evidence-anchor control."
            ),
        },
        "analysis": {
            "primary_metric": "Official Pass@1",
            "paired_unit": "repository",
            "mechanism_metrics": [
                "active finding count and obligation-group count",
                "model projection completeness",
                "package enumeration breadth",
                "candidate execution count",
                "post-first-failure finding delta",
            ],
            "descriptive_metrics": [
                "input, cached, output, and reasoning tokens",
                "logical model requests and provider attempts",
                "candidate environments, commands, and wall-clock time",
            ],
            "no_algorithm_prompt_or_threshold_change_after_selection": True,
            "infrastructure_retry_policy": (
                "Retry only a provider- or network-censored episode with "
                "identical code, settings, seed, and case; never replace a "
                "case based on outcome."
            ),
        },
        "episodes": episodes,
    }
    write_json(PREREGISTRATION, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
