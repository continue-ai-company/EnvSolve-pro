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
    "train_untouched_after_pro_goal_frontier_v1_pilot_84.jsonl"
)
SELECTED = (
    ROOT
    / "experiments/cases/"
    "dev_pro_bootstrap_frontier_v2_pilot2.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_bootstrap_frontier_v2_pilot_82.jsonl"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_bootstrap_frontier_v2_pilot_preregistration.json"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "local_mac_pro_bootstrap_frontier_v2_deepseek_direct.json"
)
PROTOCOL = (
    ROOT / "experiments/protocols/envbench_python_official_v1.json"
)
GOAL_FRONTIER_FREEZE = (
    ROOT
    / "experiments/validations/"
    "pro_goal_frontier_v1_pilot_preregistration.json"
)

EXPECTED_SOURCE_SHA256 = (
    "0fa7185f3674fbe48f785ae15a6640ba9"
    "c9e589aea0eaeaaa85d9da937a71328"
)
SALT = "envsolve-pro-bootstrap-frontier-v2-pilot-2026-07-29"
TAKE = 2
TREATMENT_FILES = (
    "envsolve/analysis/bootstrap_failures.py",
    "envsolve/constraints/bootstrap_frontier.py",
    "envsolve/runtime/bootstrap_frontier_policy.py",
    "envsolve/tools/run_envsolve_bootstrap_frontier_episode.py",
    "envsolve_harness/runners/frontier_experiment.py",
    "envsolve_harness/runners/envsolve_pro_bootstrap_frontier.py",
    "experiments/run_bootstrap_frontier_case.py",
)
INHERITED_GOAL_FRONTIER_FILES = (
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


def _verify_inherited_goal_frontier() -> dict[str, str]:
    freeze = json.loads(GOAL_FRONTIER_FREEZE.read_text(encoding="utf-8"))
    expected = freeze["algorithm_freeze"]["treatment_files"]
    actual = {
        relative: sha256_file(ROOT / relative)
        for relative in INHERITED_GOAL_FRONTIER_FILES
    }
    if actual != expected:
        raise RuntimeError("Inherited goal-frontier-v1 files changed after freeze")
    return actual


def main() -> int:
    if sha256_file(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched source pool hash does not match")
    inherited_hashes = _verify_inherited_goal_frontier()
    rows = _read_jsonl(SOURCE)
    if len(rows) != 84:
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
    if len(remaining) != 82:
        raise RuntimeError("Selection did not preserve the untouched remainder")

    _write_jsonl(
        SELECTED,
        [
            {
                **row,
                "split": "dev-pro-bootstrap-frontier-v2-pilot2",
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
                    "train-untouched-after-pro-bootstrap-frontier-v2-pilot-82"
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
                "condition": "goal-frontier-v1-control",
                "runner": "envsolve-pro-goal-frontier",
                "method": "envsolve-pro-goal-frontier",
            },
            {
                "condition": "bootstrap-frontier-v2",
                "runner": "envsolve-pro-bootstrap-frontier",
                "method": "envsolve-pro-bootstrap-frontier-v2",
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
                        f"pro-bootstrap-frontier-v2-pilot-{position:02d}-"
                        f"{label}"
                    ),
                    "model": "deepseek-v4-pro",
                    "seed": 1,
                }
            )
            position += 1

    payload = {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-bootstrap-frontier-v2-pilot",
        "status": "preregistered",
        "preregistered_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": (
            "Repository-disjoint development pilot only; not final test or "
            "leaderboard evidence."
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
                for relative in TREATMENT_FILES
            },
            "inherited_goal_frontier_v1_files": inherited_hashes,
            "goal_frontier_v1_freeze": str(
                GOAL_FRONTIER_FREEZE.relative_to(ROOT)
            ),
            "goal_frontier_v1_freeze_sha256": sha256_file(
                GOAL_FRONTIER_FREEZE
            ),
        },
        "conditions": [
            {
                "condition": "goal-frontier-v1-control",
                "runner": "envsolve-pro-goal-frontier",
                "method": "envsolve-pro-goal-frontier",
                "constraint_profile": "goal-obligation-frontier-v1",
                "base_environment_observation": "not-model-visible",
                "operation_profile": "open-program",
            },
            {
                "condition": "bootstrap-frontier-v2",
                "runner": "envsolve-pro-bootstrap-frontier",
                "method": "envsolve-pro-bootstrap-frontier-v2",
                "constraint_profile": "bootstrap-contradiction-frontier-v2",
                "base_environment_observation": "model-visible",
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
            "model_request_timeout_seconds": 900,
            "token_policy": (
                "Tokens and price are reported outcomes; configured limits "
                "are emergency guards, not research stopping thresholds."
            ),
        },
        "hypothesis": {
            "problem": (
                "Before the executable goal runs, repeated deployment "
                "failures remain raw local logs, so a solver can oscillate "
                "among repairs without representing the failed runtime branch."
            ),
            "mechanism": (
                "Expose the base environment and aggregate direct bootstrap "
                "outcomes into soft runtime-by-strategy branch constraints, "
                "while retaining raw evidence and an open Bash action space."
            ),
            "primary": (
                "Bootstrap-frontier-v2 improves or preserves Official Pass "
                "relative to goal-frontier-v1."
            ),
            "threshold_rationale": (
                "Search dominance requires the minimum evidence that "
                "distinguishes branch persistence from one local failure: "
                "three failed attempts, at least two strategy signatures, "
                "and at least two classified deployment failures. It is a "
                "soft search status and is revoked by observed success."
            ),
        },
        "analysis": {
            "primary_metric": "Official Pass@1",
            "paired_unit": "repository",
            "mechanism_metrics": [
                "bootstrap failures before first goal observation",
                "first search-dominance trigger",
                "runtime branch changes",
                "repeated failure signatures",
                "frontier projection completeness",
            ],
            "descriptive_metrics": [
                "input, cached, output, and reasoning tokens",
                "logical model requests and provider attempts",
                "candidate environments, commands, and wall-clock time",
            ],
            "planned_ablation_after_pilot": [
                "base-environment visibility only",
                "failure aggregation without search-dominance status",
                "goal-frontier removal",
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
