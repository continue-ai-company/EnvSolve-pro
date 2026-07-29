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
    "train_untouched_after_pro_execution_feedback_v3_spark4_70.jsonl"
)
SELECTED = (
    ROOT / "experiments/cases/dev_pro_stateful_agent_v2_2_pilot5.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_stateful_agent_v2_2_pilot_65.jsonl"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "local_mac_pro_stateful_agent_v2_2_pilot5.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_official_v1.json"
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_stateful_agent_v2_2_pilot5_mac.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_stateful_agent_v2_2_pilot5_preregistration.json"
)

EXPECTED_SOURCE_SHA256 = (
    "300128ba31acd31b9f3de63b050a17b51653b0ee8ec1d0174c0c549afc66efbe"
)
SALT = "envsolve-pro-stateful-agent-v2.2-dev5-2026-07-30"
TAKE = 5
MODEL = "gpt-5.5"
IMPLEMENTATION_FILES = (
    "envsolve/runtime/stateful_integrity_v2.py",
    "envsolve/runtime/stateful_integrity_v22.py",
    "envsolve/runtime/stateful_goal_verifier_v2.py",
    "envsolve/runtime/stateful_goal_verifier_v22.py",
    "envsolve/constraints/goal_frontier.py",
    "envsolve/solver/counterexample.py",
    "envsolve_harness/runners/codex_cli.py",
    "envsolve_harness/runners/stateful_codex.py",
    "envsolve_harness/scripts/open_program.py",
    "experiments/extensible_schedule.py",
    "experiments/run_stateful_codex_case.py",
    "experiments/run_stateful_codex_schedule.py",
)
TEST_FILES = (
    "tests/test_integrity_audit.py",
    "tests/test_stateful_codex_runner.py",
    "tests/test_stateful_integrity_v22.py",
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


def _conditions(case_id: str) -> list[dict[str, str]]:
    values = [
        {
            "condition": "codex-goal-aware-single-session",
            "runner": "codex-cli",
            "method": "codex-cli-goal-aware",
        },
        {
            "condition": "codex-raw-repair-v2.2",
            "runner": "codex-stateful-raw-v2.2",
            "method": "codex-cli-goal-aware-raw-repair-v2.2",
        },
        {
            "condition": "envsolve-pro-structured-v2.2",
            "runner": "envsolve-pro-stateful-agent-v2.2",
            "method": "envsolve-pro-stateful-agent-v2.2",
        },
    ]
    offset = int(_digest(SALT, "condition-order", case_id), 16) % len(values)
    return values[offset:] + values[:offset]


def main() -> int:
    if sha256_file(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched source pool hash does not match")
    rows = _read_jsonl(SOURCE)
    if len(rows) != 70:
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
    if len(remaining) != 65:
        raise RuntimeError("Selection did not preserve the untouched remainder")

    _write_jsonl(
        SELECTED,
        [
            {
                **row,
                "split": "dev-pro-stateful-agent-v2.2-pilot5",
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
                    "train-untouched-after-pro-stateful-agent-v2.2-pilot-65"
                ),
            }
            for row in remaining
        ],
    )

    ordered_cases = sorted(
        selected,
        key=lambda row: _digest(SALT, "case-order", str(row["case_id"])),
    )
    episodes: list[dict[str, Any]] = []
    for case_position, row in enumerate(ordered_cases, start=1):
        case_id = str(row["case_id"])
        for condition in _conditions(case_id):
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
                        f"pro-stateful-v2-2-pilot5-{position:02d}-{label}"
                    ),
                    "model": MODEL,
                    "seed": 3,
                }
            )

    write_json(
        SCHEDULE,
        {
            "schema_version": "1.0.0",
            "study_id": "envsolve-pro-stateful-agent-v2.2-pilot5",
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
            "study_id": "envsolve-pro-stateful-agent-v2.2-pilot5",
            "status": "frozen",
            "preregistered_at": datetime.now(timezone.utc).isoformat(),
            "claim_scope": (
                "Repository-disjoint five-case development pilot. It can guide "
                "generic mechanism selection but cannot support final test or "
                "leaderboard-scale claims."
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
            "conditions": [
                {
                    "condition": "codex-goal-aware-single-session",
                    "role": "strong single-session baseline",
                    "public_goal_visible": True,
                    "repair_rounds": False,
                    "structured_state": False,
                },
                {
                    "condition": "codex-raw-repair-v2.2",
                    "role": "same-model stateful raw-history control",
                    "public_goal_visible": True,
                    "repair_rounds": True,
                    "structured_state": False,
                },
                {
                    "condition": "envsolve-pro-structured-v2.2",
                    "role": "EnvSolve-Pro treatment",
                    "public_goal_visible": True,
                    "repair_rounds": True,
                    "structured_state": True,
                },
            ],
            "shared_setting": {
                "model": MODEL,
                "reasoning_effort": "high",
                "official_evaluator_feedback_available_online": False,
                "candidate_interface": "open cumulative Bash program",
                "candidate_verification_environment": (
                    "fresh exact-revision checkout"
                ),
                "model_token_hard_limit": False,
                "model_cost_hard_limit": False,
                "stateful_max_model_candidates": 3,
            },
            "metrics": {
                "primary": "Official Pass@1 by condition",
                "secondary": [
                    "integrity-qualified pass",
                    "repair success conditioned on first-candidate failure",
                    "model candidates",
                    "container commands",
                    "input and output tokens",
                    "wall-clock time",
                    "infrastructure censoring",
                ],
                "official_and_integrity_labels_reported_separately": True,
            },
            "analysis_policy": {
                "paired_by_case": True,
                "case_order": "frozen salted-hash order",
                "condition_order": "frozen per-case salted rotation",
                "individual_case_rules_forbidden": True,
                "mechanism_change_gate": (
                    "A new inner rule requires either the same failure category "
                    "on at least two repository-disjoint pilot cases or a generic "
                    "counterexample canary plus a non-regression control. Any "
                    "change requires a new version and new untouched cases."
                ),
                "infrastructure_policy": (
                    "Provider, network, acquisition, and evaluator failures are "
                    "censored and may be retried only under an identical-setting "
                    "amendment."
                ),
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
            "preflight": {
                "mac_focused": "20 passed",
                "spark_focused": "18 passed before runner exposure",
                "spark_full": (
                    "662 passed, 3 skipped, 75 subtests passed; one diagnosed "
                    "host logout fixture failure"
                ),
                "module_identity_canary": {
                    "path": (
                        "experiments/validations/"
                        "pro_stateful_agent_v2_2_module_identity_canary.json"
                    ),
                    "status": "passed",
                },
            },
        },
    )
    print(f"selected={SELECTED.relative_to(ROOT)}")
    print(f"remaining={REMAINING.relative_to(ROOT)}")
    print(f"schedule={SCHEDULE.relative_to(ROOT)}")
    print(f"preregistration={PREREGISTRATION.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
