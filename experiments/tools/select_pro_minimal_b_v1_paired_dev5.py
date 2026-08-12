#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
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
    "train_untouched_after_pro_stateful_agent_v2_4_pilot_58.jsonl"
)
SELECTED = ROOT / "experiments/cases/dev_pro_minimal_b_v1_paired5.jsonl"
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_minimal_b_v1_paired_53.jsonl"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "local_mac_pro_minimal_b_v1_paired_dev5.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_public_goal_v2.json"
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_minimal_b_v1_paired_dev5_mac.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_minimal_b_v1_paired_dev5_preregistration.json"
)
PROTOCOL_EN = ROOT / "research/PRO_MINIMAL_B_V1_PAIRED_DEV5_PROTOCOL.md"
PROTOCOL_ZH = ROOT / "research/PRO_MINIMAL_B_V1_PAIRED_DEV5_PROTOCOL_ZH.md"
IMPLEMENTATION_FREEZE = (
    ROOT
    / "experiments/protocols/"
    "envsolve_pro_minimal_b_v1_0_2_implementation_freeze.json"
)

EXPECTED_SOURCE_SHA256 = (
    "a008e4e70f355ecbad9267c373ec710a94e839e6ef9a69645e309f5e6488e1a6"
)
SALT = "envsolve-pro-minimal-b-v1-paired-dev5-2026-08-04"
TAKE = 5
MODEL = "gpt-5.5"
IMPLEMENTATION_FILES = (
    "envsolve_harness/codex/minimal_b_mcp.py",
    "envsolve_harness/runners/codex_cli.py",
    "envsolve_harness/runners/envsolve_pro_minimal_b.py",
    "experiments/extensible_schedule.py",
    "experiments/run_case.py",
    "experiments/run_minimal_b_case.py",
    "experiments/run_minimal_b_schedule.py",
)
TEST_FILES = (
    "tests/test_envsolve_pro_minimal_b_runner.py",
    "tests/test_minimal_b_mcp.py",
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
            "condition": "envsolve-pro-minimal-b-v1.0.2",
            "runner": "envsolve-pro-minimal-b",
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


def main() -> int:
    outputs = (SELECTED, REMAINING, SCHEDULE, PREREGISTRATION)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"Refusing to overwrite frozen output: {existing[0]}")
    if sha256_file(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched source pool hash does not match")
    rows = _read_jsonl(SOURCE)
    if len(rows) != 58:
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
    if len(remaining) != len(rows) - TAKE:
        raise RuntimeError("Selection did not preserve the untouched remainder")

    _write_jsonl(
        SELECTED,
        [
            {**row, "split": "dev-pro-minimal-b-v1-paired5"}
            for row in selected
        ],
    )
    _write_jsonl(
        REMAINING,
        [
            {
                **row,
                "split": "train-untouched-after-pro-minimal-b-v1-paired-53",
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
        for condition in _conditions(repository):
            position = len(episodes) + 1
            label = condition["condition"]
            episodes.append(
                {
                    "position": position,
                    "case_position": case_position,
                    "host": "mac",
                    "case_id": str(row["case_id"]),
                    **condition,
                    "run_id": f"pro-minimal-b-v1-paired5-{position:02d}-{label}",
                    "model": MODEL,
                    "seed": seed,
                }
            )

    write_json(
        SCHEDULE,
        {
            "schema_version": "1.0.0",
            "study_id": "envsolve-pro-minimal-b-v1-paired-dev5",
            "case_file": str(SELECTED.relative_to(ROOT)),
            "case_file_sha256": sha256_file(SELECTED),
            "model": MODEL,
            "episode_timeout_seconds": 22400,
            "episodes": episodes,
        },
    )

    frozen_files = (
        *IMPLEMENTATION_FILES,
        *TEST_FILES,
        str(CONFIG.relative_to(ROOT)),
        str(PROTOCOL.relative_to(ROOT)),
        str(PROTOCOL_EN.relative_to(ROOT)),
        str(PROTOCOL_ZH.relative_to(ROOT)),
        str(IMPLEMENTATION_FREEZE.relative_to(ROOT)),
        str(Path(__file__).resolve().relative_to(ROOT)),
    )
    write_json(
        PREREGISTRATION,
        {
            "schema_version": "1.0.0",
            "study_id": "envsolve-pro-minimal-b-v1-paired-dev5",
            "status": "frozen-before-execution",
            "preregistered_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": _source_revision(),
            "claim_scope": (
                "Repository-disjoint paired five-case development comparison. "
                "It can evaluate the Minimal B mechanism but cannot support held-out "
                "or leaderboard claims."
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
                "failure_prescreen": False,
                "selected_before_execution": True,
                "selected_case_file": str(SELECTED.relative_to(ROOT)),
                "selected_case_file_sha256": sha256_file(SELECTED),
                "remaining_case_file": str(REMAINING.relative_to(ROOT)),
                "remaining_case_file_sha256": sha256_file(REMAINING),
            },
            "conditions": [
                {
                    "condition": "codex-goal-aware-single-session",
                    "role": "strong Agent control",
                    "runner": "codex-cli",
                    "method": "codex-cli-goal-aware",
                    "online_clean_replay": False,
                },
                {
                    "condition": "envsolve-pro-minimal-b-v1.0.2",
                    "role": "online clean-replay treatment",
                    "runner": "envsolve-pro-minimal-b",
                    "method": "envsolve-pro-minimal-b-v1",
                    "online_clean_replay": True,
                },
            ],
            "shared_setting": {
                "model": MODEL,
                "reasoning_effort": "high",
                "candidate_interface": "open cumulative Bash program",
                "construction_environment": "persistent within one Agent session",
                "official_evaluator_feedback_available_online": False,
                "cross_case_memory": False,
                "model_token_hard_limit": False,
                "model_cost_hard_limit": False,
            },
            "metrics": {
                "primary": "paired Official Pass@1",
                "mechanism": "replay-conditioned repair within one Agent session",
                "secondary": [
                    "generation completion",
                    "integrity outcome",
                    "replay calls",
                    "commands",
                    "model tokens",
                    "wall-clock time",
                    "peak memory",
                    "disk growth",
                    "network bytes when available",
                ],
            },
            "analysis_policy": {
                "paired_by_repository": True,
                "case_order": "frozen salted-hash order",
                "condition_order": "frozen per-repository salted rotation",
                "all_ten_episodes_before_algorithm_change": True,
                "individual_case_rules_forbidden": True,
                "case_replacement": False,
                "official_and_integrity_outcomes_reported_separately": True,
                "infrastructure_unknown_excluded_from_effect_denominator": True,
                "identical_infrastructure_retry_requires_frozen_amendment": True,
            },
            "artifacts": {
                "implementation_freeze": {
                    "path": str(IMPLEMENTATION_FREEZE.relative_to(ROOT)),
                    "sha256": sha256_file(IMPLEMENTATION_FREEZE),
                },
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
                    for relative in frozen_files
                },
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
