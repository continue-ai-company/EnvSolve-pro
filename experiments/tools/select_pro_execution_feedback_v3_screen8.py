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
    "train_untouched_after_pro_bootstrap_frontier_v2_pilot_82.jsonl"
)
SELECTED = (
    ROOT
    / "experiments/cases/"
    "dev_pro_execution_feedback_v3_screen8.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_execution_feedback_v3_screen8_74.jsonl"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_execution_feedback_v3_screen8_preregistration.json"
)
SCHEDULES = {
    "mac": (
        ROOT
        / "experiments/schedules/"
        "pro_execution_feedback_v3_screen8_mac.json"
    ),
    "spark": (
        ROOT
        / "experiments/schedules/"
        "pro_execution_feedback_v3_screen8_spark.json"
    ),
}
PROTOCOL = ROOT / "experiments/protocols/envbench_python_official_v1.json"
GOAL_FRONTIER_FREEZE = (
    ROOT
    / "experiments/validations/"
    "pro_goal_frontier_v1_pilot_preregistration.json"
)
CONFIGS = {
    "mac": (
        ROOT
        / "experiments/configs/"
        "local_mac_pro_execution_feedback_v3_deepseek_direct.json"
    ),
    "spark": (
        ROOT
        / "experiments/configs/"
        "spark_pro_execution_feedback_v3_deepseek_direct.json"
    ),
}

EXPECTED_SOURCE_SHA256 = (
    "7895a2fd84abcf9609fc9f4e8b167530"
    "3dc43e4ebbde25a2d60d760f2c1d48d7"
)
SALT = "envsolve-pro-execution-feedback-v3-screen8-2026-07-29"
TAKE = 8
TREATMENT_FILES = (
    "envsolve/runtime/execution_feedback.py",
    "envsolve/tools/run_envsolve_execution_feedback_episode.py",
    "envsolve_harness/runners/frontier_experiment.py",
    "envsolve_harness/runners/envsolve_pro_execution_feedback.py",
    "envsolve_harness/scripts/observable_open_program.py",
    "experiments/run_execution_feedback_case.py",
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
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


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
    if len(rows) != 82:
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
    if len(remaining) != 74:
        raise RuntimeError("Selection did not preserve the untouched remainder")

    _write_jsonl(
        SELECTED,
        [
            {
                **row,
                "split": "dev-pro-execution-feedback-v3-screen8",
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
                    "train-untouched-after-pro-execution-feedback-v3-screen8-74"
                ),
            }
            for row in remaining
        ],
    )

    episodes: list[dict[str, Any]] = []
    ordered_cases = sorted(
        selected,
        key=lambda row: _digest(
            SALT,
            "case-order",
            str(row["case_id"]),
        ),
    )
    for case_position, row in enumerate(ordered_cases, start=1):
        case_id = str(row["case_id"])
        host = "mac" if case_position % 2 else "spark"
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
            label = str(condition["condition"])
            position = len(episodes) + 1
            episodes.append(
                {
                    "position": position,
                    "host_position": sum(
                        item["host"] == host for item in episodes
                    )
                    + 1,
                    "host": host,
                    "case_id": case_id,
                    **condition,
                    "run_id": (
                        f"pro-execution-feedback-v3-screen8-{position:02d}-"
                        f"{label}"
                    ),
                    "model": "deepseek-v4-pro",
                    "seed": 1,
                }
            )

    for host, schedule_path in SCHEDULES.items():
        host_episodes = [
            {
                **episode,
                "global_position": episode["position"],
                "position": episode["host_position"],
            }
            for episode in episodes
            if episode["host"] == host
        ]
        write_json(
            schedule_path,
            {
                "schema_version": "1.0.0",
                "study_id": (
                    f"envsolve-pro-execution-feedback-v3-screen8-{host}"
                ),
                "case_file": str(SELECTED.relative_to(ROOT)),
                "case_file_sha256": sha256_file(SELECTED),
                "model": "deepseek-v4-pro",
                "episode_timeout_seconds": 22_800,
                "episodes": host_episodes,
            },
        )

    payload = {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-execution-feedback-v3-screen8",
        "status": "preregistered",
        "preregistered_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": (
            "Repository-disjoint eight-case development screen; not final test "
            "or leaderboard evidence."
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
                "goal_frontier": "goal-obligation-frontier-v1",
                "candidate_interface": "open-program-v1",
                "goal_process_failure": "terminal-unknown",
            },
            {
                "condition": "execution-feedback-v3",
                "runner": "envsolve-pro-execution-feedback",
                "method": "envsolve-pro-execution-feedback-v3",
                "goal_frontier": "goal-obligation-frontier-v1",
                "candidate_interface": "open-program-v2-observable",
                "goal_process_failure": (
                    "recoverable-non-infrastructure-counterexample"
                ),
                "bootstrap_taxonomy": "disabled",
            },
        ],
        "shared_contract": {
            "model": "deepseek-v4-pro",
            "provider": "DeepSeek direct",
            "seed": 1,
            "configs": {
                host: {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256_file(path),
                }
                for host, path in CONFIGS.items()
            },
            "host_schedules": {
                host: {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256_file(path),
                }
                for host, path in SCHEDULES.items()
            },
            "host_assignment": (
                "Both conditions for a repository run on the same host; four "
                "pairs per host by preregistered alternating case order."
            ),
            "protocol": str(PROTOCOL.relative_to(ROOT)),
            "protocol_sha256": sha256_file(PROTOCOL),
            "public_executable_goal": True,
            "repository_evidence": "constraint-routed",
            "candidate_anchor": "retained-admissible",
            "candidate_retention": "best-admissible",
            "environment_strategy": "fresh-candidate",
            "max_candidates": 12,
            "max_environments": 24,
            "max_commands": 24,
            "generation_timeout_seconds": 18_000,
            "candidate_command_timeout_seconds": 1_200,
            "model_request_timeout_seconds": 900,
            "token_policy": (
                "Tokens and price are reported outcomes; configured limits are "
                "emergency guards, not research stopping thresholds."
            ),
        },
        "hypothesis": {
            "problem": (
                "A solver cannot repair evidence that candidate programs discard, "
                "and a candidate-induced crash of the public goal currently ends "
                "the episode instead of becoming fresh-container feedback."
            ),
            "mechanism": (
                "Preserve mutation diagnostics and reclassify only completed, "
                "non-infrastructure goal-process crashes as recoverable execution "
                "state conflicts, while retaining the v1 goal frontier and open Bash."
            ),
            "primary": (
                "Execution-feedback-v3 improves or preserves Official Pass@1 "
                "relative to frozen goal-frontier-v1."
            ),
        },
        "screening_rule": {
            "promote_to_twenty_cases": (
                "Net paired Official Pass difference is positive with no integrity "
                "regression, or tied with a directly triggered mechanism and no loss."
            ),
            "discard": (
                "Treatment has no wins and at least two losses, or causes any "
                "repository-integrity or evaluator-leakage regression."
            ),
            "otherwise": "Inspect only preregistered mechanism traces, then decide.",
        },
        "analysis": {
            "primary_metric": "Official Pass@1",
            "paired_unit": "repository",
            "mechanism_metrics": [
                "diagnostic redirections removed",
                "recoverable goal execution failures",
                "infrastructure-censored unknowns",
                "candidate count before official pass",
            ],
            "descriptive_metrics": [
                "input, cached, output, and reasoning tokens",
                "model requests, environments, commands, and wall-clock time",
            ],
            "no_algorithm_prompt_or_threshold_change_after_selection": True,
            "infrastructure_retry_policy": (
                "Retry only a provider- or network-censored episode with identical "
                "code, settings, seed, host, and case."
            ),
        },
        "episodes": episodes,
    }
    write_json(PREREGISTRATION, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
