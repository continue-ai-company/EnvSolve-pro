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
    "train_untouched_after_pro_stateful_agent_v2_3_pilot_62.jsonl"
)
SELECTED = ROOT / "experiments/cases/dev_pro_stateful_agent_v2_4_pilot4.jsonl"
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_stateful_agent_v2_4_pilot_58.jsonl"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "local_mac_pro_stateful_agent_v2_4_pilot4.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_official_v1.json"
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_stateful_agent_v2_4_pilot4_mac.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_stateful_agent_v2_4_pilot4_preregistration.json"
)

EXPECTED_SOURCE_SHA256 = (
    "92785247d6b920cc862d8d680ff8f32c103b780f19c09312924f34e0d22b0323"
)
SALT = "envsolve-pro-stateful-agent-v2.4-dev4-2026-07-30"
TAKE = 4
MODEL = "gpt-5.5"
IMPLEMENTATION_FILES = (
    "envsolve/constraints/goal_frontier.py",
    "envsolve/runtime/goal_verifier.py",
    "envsolve/runtime/stateful_goal_verifier_v23.py",
    "envsolve/runtime/stateful_goal_verifier_v24.py",
    "envsolve/solver/counterexample.py",
    "envsolve/verification/counterexamples.py",
    "envsolve/verification/root_obligations.py",
    "envsolve_harness/runners/codex_cli.py",
    "envsolve_harness/runners/stateful_codex.py",
    "envsolve_harness/scripts/open_program.py",
    "experiments/extensible_schedule.py",
    "experiments/run_stateful_codex_case.py",
    "experiments/run_stateful_codex_schedule.py",
)
TEST_FILES = (
    "envsolve/tests/test_stateful_codex_projection.py",
    "envsolve/tests/test_structured_counterexamples.py",
    "tests/test_goal_obligation_frontier.py",
    "tests/test_open_candidate_interface.py",
    "tests/test_stateful_codex_runner.py",
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


def _conditions(repository: str) -> list[dict[str, str]]:
    values = [
        {
            "condition": "codex-goal-aware-single-session",
            "runner": "codex-cli",
            "method": "codex-cli-goal-aware",
        },
        {
            "condition": "codex-raw-repair-v2.4",
            "runner": "codex-stateful-raw-v2.4",
            "method": "codex-cli-goal-aware-raw-repair-v2.4",
        },
        {
            "condition": "envsolve-pro-structured-v2.4",
            "runner": "envsolve-pro-stateful-agent-v2.4",
            "method": "envsolve-pro-stateful-agent-v2.4",
        },
    ]
    offset = int(
        _digest(SALT, "condition-order", repository),
        16,
    ) % len(values)
    return values[offset:] + values[:offset]


def main() -> int:
    if sha256_file(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched source pool hash does not match")
    rows = _read_jsonl(SOURCE)
    if len(rows) != 62:
        raise RuntimeError("Unexpected untouched source pool size")

    by_repository: dict[str, dict[str, Any]] = {}
    for row in rows:
        repository = str(row["repository"])
        if repository in by_repository:
            raise RuntimeError(
                f"Untouched pool contains duplicate repository identity: {repository}"
            )
        by_repository[repository] = row
    ranked = sorted(
        rows,
        key=lambda row: _digest(SALT, str(row["repository"])),
    )
    selected = ranked[:TAKE]
    selected_repositories = {
        str(row["repository"])
        for row in selected
    }
    remaining = [
        row
        for row in rows
        if str(row["repository"]) not in selected_repositories
    ]
    if len(remaining) != 58:
        raise RuntimeError("Selection did not preserve the untouched remainder")

    _write_jsonl(
        SELECTED,
        [
            {**row, "split": "dev-pro-stateful-agent-v2.4-pilot4"}
            for row in selected
        ],
    )
    _write_jsonl(
        REMAINING,
        [
            {
                **row,
                "split": (
                    "train-untouched-after-pro-stateful-agent-v2.4-pilot-58"
                ),
            }
            for row in remaining
        ],
    )

    ordered_cases = sorted(
        selected,
        key=lambda row: _digest(
            SALT,
            "case-order",
            str(row["repository"]),
        ),
    )
    episodes: list[dict[str, Any]] = []
    for case_position, row in enumerate(ordered_cases, start=1):
        case_id = str(row["case_id"])
        repository = str(row["repository"])
        for condition in _conditions(repository):
            position = len(episodes) + 1
            label = condition["condition"]
            episodes.append(
                {
                    "position": position,
                    "case_position": case_position,
                    "host": "mac",
                    "case_id": case_id,
                    **condition,
                    "run_id": (
                        f"pro-stateful-v2-4-pilot4-{position:02d}-{label}"
                    ),
                    "model": MODEL,
                    "seed": 4,
                }
            )

    write_json(
        SCHEDULE,
        {
            "schema_version": "1.0.0",
            "study_id": "envsolve-pro-stateful-agent-v2.4-pilot4",
            "case_file": str(SELECTED.relative_to(ROOT)),
            "case_file_sha256": sha256_file(SELECTED),
            "model": MODEL,
            "episode_timeout_seconds": 22400,
            "episodes": episodes,
        },
    )

    freeze_files = (
        *IMPLEMENTATION_FILES,
        *TEST_FILES,
        str(CONFIG.relative_to(ROOT)),
        str(PROTOCOL.relative_to(ROOT)),
        str(Path(__file__).resolve().relative_to(ROOT)),
    )
    write_json(
        PREREGISTRATION,
        {
            "schema_version": "1.0.0",
            "study_id": "envsolve-pro-stateful-agent-v2.4-pilot4",
            "status": "frozen",
            "preregistered_at": datetime.now(timezone.utc).isoformat(),
            "claim_scope": (
                "Repository-disjoint four-case development pilot. It may "
                "select the next generic mechanism but cannot support final "
                "test or leaderboard claims."
            ),
            "selection": {
                "source_case_file": str(SOURCE.relative_to(ROOT)),
                "source_case_file_sha256": sha256_file(SOURCE),
                "source_rows": len(rows),
                "selection_unit": "repository",
                "salt": SALT,
                "algorithm": "ascending SHA256(salt + NUL + repository)",
                "take": TAKE,
                "repository_content_or_outcome_used_for_selection": False,
                "selected_before_execution": True,
                "selected_case_file": str(SELECTED.relative_to(ROOT)),
                "selected_case_file_sha256": sha256_file(SELECTED),
                "remaining_case_file": str(REMAINING.relative_to(ROOT)),
                "remaining_case_file_sha256": sha256_file(REMAINING),
            },
            "conditions": [
                {
                    "condition": "codex-goal-aware-single-session",
                    "role": "strong single-session baseline",
                    "public_goal_visible": True,
                    "repair_rounds": False,
                    "structured_state": False,
                },
                {
                    "condition": "codex-raw-repair-v2.4",
                    "role": "failure-triggered same-model raw control",
                    "public_goal_visible": True,
                    "repair_rounds": True,
                    "structured_state": False,
                },
                {
                    "condition": "envsolve-pro-structured-v2.4",
                    "role": "factorized goal-operation state treatment",
                    "public_goal_visible": True,
                    "repair_rounds": True,
                    "structured_state": True,
                },
            ],
            "shared_setting": {
                "model": MODEL,
                "reasoning_effort": "high",
                "candidate_interface": "open cumulative Bash program",
                "candidate_verification_environment": (
                    "fresh exact-revision checkout"
                ),
                "official_evaluator_feedback_available_online": False,
                "stateful_max_model_candidates": 3,
                "model_token_hard_limit": False,
                "model_cost_hard_limit": False,
            },
            "mechanism": {
                "initial_goal_probe": False,
                "structured_feedback_trigger": "first candidate failure",
                "structured_projection": (
                    "root-obligation-plus-operation-contract-v1"
                ),
                "goal_and_operation_state_factorized": True,
                "operation_postconditions": [
                    "candidate policy",
                    "repository effects",
                    "caller working directory",
                ],
                "raw_findings": "immutable audit archive only",
                "hard_constraint_authority": (
                    "public executable goal and shared protocol"
                ),
                "operation_space": "open",
            },
            "metrics": {
                "primary": "Official Pass@1 by condition",
                "secondary": [
                    "repair success conditioned on first-candidate failure",
                    "goal-satisfied operation-repair success",
                    "first-candidate success",
                    "model candidates",
                    "container commands",
                    "input and output tokens",
                    "model-visible projection bytes",
                    "surface finding and root obligation counts",
                    "state event count",
                    "wall-clock time",
                    "infrastructure censoring",
                ],
            },
            "analysis_policy": {
                "paired_by_repository": True,
                "case_order": "frozen salted-hash order",
                "condition_order": "frozen per-repository salted rotation",
                "individual_case_rules_forbidden": True,
                "v2_3_pilot_reuse_for_effect_claim": False,
                "official_and_integrity_outcomes_reported_separately": True,
                "next_change_gate": (
                    "At least two repository-disjoint cases with the same "
                    "earliest failure interface, or one generic counterexample "
                    "plus a non-regression control."
                ),
            },
            "preflight": {
                "mac": "663 passed, 3 skipped",
                "spark_arm_linux": (
                    "54 V2.4-focused passed; full 660 passed, 3 skipped, "
                    "with two host python-alias and one no-git fixture failure"
                ),
                "historical_freeze_hashes": "preserved",
            },
            "artifacts": {
                "config": {
                    "path": str(CONFIG.relative_to(ROOT)),
                    "sha256": sha256_file(CONFIG),
                },
                "protocol": {
                    "path": str(PROTOCOL.relative_to(ROOT)),
                    "sha256": sha256_file(PROTOCOL),
                },
                "schedule": {
                    "path": str(SCHEDULE.relative_to(ROOT)),
                    "sha256": sha256_file(SCHEDULE),
                },
                "freeze_files": {
                    relative: sha256_file(ROOT / relative)
                    for relative in freeze_files
                },
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
