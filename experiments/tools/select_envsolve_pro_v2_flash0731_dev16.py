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


STUDY_ID = "envsolve-pro-v2-flash0731-dev16"
MODEL = "deepseek/deepseek-v4-flash-0731"
PROVIDER = "cloudflare"
SALT = "envsolve-pro-v2-flash0731-dev16-2026-08-14"
TAKE = 16

SOURCE = ROOT / "experiments/cases/dev_envsolve_pro_v2_reserve44.jsonl"
CANARY = ROOT / "experiments/cases/canary20.jsonl"
PROTECTED_TEST = ROOT / "experiments/cases/official_test100.jsonl"
QUALIFICATION = (
    ROOT
    / "experiments/validations/envsolve_pro_v2_flash0731_qualification_result.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_official_v1.json"
RUNNER = ROOT / "envsolve_harness/runners/openrouter_agent.py"
SELECTED = ROOT / "experiments/cases/dev_envsolve_pro_v2_flash0731_dev16.jsonl"
REMAINING = ROOT / "experiments/cases/dev_envsolve_pro_v2_flash0731_remaining28.jsonl"
CONFIG = ROOT / "experiments/configs/local_spark_envsolve_pro_v2_flash0731_dev16.json"
SCHEDULE = ROOT / "experiments/schedules/envsolve_pro_v2_flash0731_dev16.json"
AUDIT = ROOT / "experiments/validations/envsolve_pro_v2_flash0731_dev16_selection.json"
PREREGISTRATION = (
    ROOT / "experiments/validations/envsolve_pro_v2_flash0731_dev16_preregistration.json"
)

EXPECTED_HASHES = {
    SOURCE: "716ce34d6711be30fa3a44cf4e9b8dd7169dd042faa2d8a92ee83c7f302a97a7",
    CANARY: "efaa56b0087776003432fa51ed585aa46729310ab014634352819ae622da709c",
    PROTECTED_TEST: "2c5f9345f12623e1ea197fdd6a1d801eaddb559722c918cbb13220de8f61cfea",
    QUALIFICATION: "c1cf54b7e4c0321de13d21027427304d70c9509fdbd68c2e0d77d4568d64772f",
    PROTOCOL: "f495b4949c8b1fd7b45b63dd1fb8ab47869867b977fc74b0d30e733b42cc92af",
    RUNNER: "c50804145a373add5095127610b286cc423b6ba0fa4db0270abd514953441b13",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def select_case_ids(case_ids: list[str]) -> tuple[list[str], list[str]]:
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Case identities must be unique")
    ranked = sorted(case_ids, key=lambda case_id: _digest(SALT, "select", case_id))
    return ranked[:TAKE], ranked[TAKE:]


def arm_order(case_id: str) -> list[dict[str, Any]]:
    arms = [
        {
            "arm": "A-F",
            "runner": "deepseek-free-agent",
            "method": "free-feedback-search",
            "mechanisms": ["F", "minimal-H"],
        },
        {
            "arm": "B-FSR",
            "runner": "envsolve-pro-v2",
            "method": "envsolve-pro-fsr-minimal-h",
            "mechanisms": ["F", "S", "R", "minimal-H"],
        },
    ]
    if int(_digest(SALT, "arm-order", case_id), 16) % 2:
        arms.reverse()
    return arms


def build_episodes(selected_ids: list[str]) -> list[dict[str, Any]]:
    case_order = sorted(
        selected_ids,
        key=lambda case_id: _digest(SALT, "case-order", case_id),
    )
    episodes: list[dict[str, Any]] = []
    for case_position, case_id in enumerate(case_order, start=1):
        seed = int(_digest(SALT, "seed", case_id)[:8], 16)
        for pair_position, arm in enumerate(arm_order(case_id), start=1):
            position = len(episodes) + 1
            episodes.append(
                {
                    "position": position,
                    "case_position": case_position,
                    "pair_position": pair_position,
                    "pair_id": f"flash0731-dev16-case-{case_position:02d}",
                    "case_id": case_id,
                    "run_id": f"pro-v2-flash0731-dev16-{position:02d}-{arm['arm']}",
                    "model": MODEL,
                    "provider": PROVIDER,
                    "seed": seed,
                    **arm,
                }
            )
    return episodes


def _source_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _config() -> dict[str, Any]:
    return {
        "paths": {"runs": "runs/envsolve-pro-v2-flash0731-dev16"},
        "benchmarks": {
            "envbench": {
                "adapter": "envbench",
                "root": "EnvBench",
                "settings": {
                    "image": "ghcr.io/jetbrains-research/envbench-python:latest",
                    "deterministic_script": "evaluation/scripts/python_baseline.sh",
                },
            }
        },
        "generation": {
            "timeout": 18000,
            "model_request_timeout": 600,
            "model_max_retries": 5,
            "model_max_output_tokens": 32768,
            "model_reasoning_effort": "xhigh",
            "model_max_requests": 120,
            "model_max_total_tokens": 100000000,
            "model_max_estimated_cost_usd": 1000.0,
            "max_iterations": 120,
            "envsolve_max_candidates": 3,
            "envsolve_max_environments": 3,
            "envsolve_max_commands": 3,
            "bash_timeout": 1800,
        },
        "evaluation": {
            "create_container_timeout": 600,
            "container_timeout": 2400,
            "process_timeout": 3600,
            "git_fetch_timeout": 900,
            "max_workers": 1,
        },
    }


def main() -> int:
    outputs = (SELECTED, REMAINING, CONFIG, SCHEDULE, AUDIT, PREREGISTRATION)
    for output in outputs:
        if output.exists():
            raise RuntimeError(f"Refusing to overwrite frozen output: {output}")
    for path, expected in EXPECTED_HASHES.items():
        if sha256_file(path) != expected:
            raise RuntimeError(f"Frozen input hash mismatch: {path}")

    rows = _read_jsonl(SOURCE)
    by_id = {str(row["case_id"]): row for row in rows}
    if len(rows) != 44 or len(by_id) != 44:
        raise RuntimeError("Flash Dev16 source must contain 44 unique cases")
    source_ids = set(by_id)
    canary_ids = {str(row["case_id"]) for row in _read_jsonl(CANARY)}
    protected_ids = {str(row["case_id"]) for row in _read_jsonl(PROTECTED_TEST)}
    if source_ids & canary_ids or source_ids & protected_ids:
        raise RuntimeError("Development source overlaps Canary or protected test")

    selected_ids, remaining_ids = select_case_ids(list(source_ids))
    _write_jsonl(
        SELECTED,
        [
            {**by_id[case_id], "split": "dev-envsolve-pro-v2-flash0731-dev16"}
            for case_id in selected_ids
        ],
    )
    _write_jsonl(
        REMAINING,
        [
            {
                **by_id[case_id],
                "split": "dev-envsolve-pro-v2-flash0731-remaining28",
            }
            for case_id in remaining_ids
        ],
    )
    write_json(CONFIG, _config())
    write_json(
        SCHEDULE,
        {
            "schema_version": "1.0.0",
            "study_id": STUDY_ID,
            "case_file": str(SELECTED.relative_to(ROOT)),
            "case_file_sha256": sha256_file(SELECTED),
            "model": MODEL,
            "provider": PROVIDER,
            "population_role": "taxonomy-consumed-flash-treatment-unrun-development",
            "required_environment": {
                "OPENROUTER_API_KEY": "present-not-recorded",
                "OPENROUTER_PROVIDER_ORDER": PROVIDER,
            },
            "episode_timeout_seconds": 23000,
            "episodes": build_episodes(selected_ids),
        },
    )
    now = datetime.now(timezone.utc).isoformat()
    write_json(
        AUDIT,
        {
            "schema": "envsolve-pro-v2-flash0731-dev16-selection-v1",
            "frozen_at": now,
            "source": str(SOURCE.relative_to(ROOT)),
            "source_sha256": sha256_file(SOURCE),
            "source_count": 44,
            "source_evidence_status": "all identities were previously available to taxonomy census",
            "repository_unseen": False,
            "flash0731_treatment_previously_run": False,
            "information_used_for_selection": "case identity only",
            "outcome_or_failure_class_used": False,
            "salt": SALT,
            "algorithm": "ascending SHA256(salt + NUL + 'select' + NUL + case_id)",
            "selected_count": 16,
            "remaining_count": 28,
            "selected_case_ids": selected_ids,
            "canary_overlap": 0,
            "protected_test_overlap": 0,
        },
    )
    write_json(
        PREREGISTRATION,
        {
            "schema": "envsolve-pro-v2-flash0731-dev16-preregistration-v1",
            "study_id": STUDY_ID,
            "status": "frozen-before-first-episode",
            "preregistered_at": now,
            "source_revision": _source_revision(),
            "research_question": "Does F+S+R improve Official Pass@1 over F on the same pinned Flash 0731 model?",
            "population_role": "taxonomy-consumed-flash-treatment-unrun-development",
            "claim_boundary": "development same-model effect only; repository-level generalization requires untouched Canary and protected test",
            "selection": {
                "audit": str(AUDIT.relative_to(ROOT)),
                "audit_sha256": sha256_file(AUDIT),
                "selected": str(SELECTED.relative_to(ROOT)),
                "selected_sha256": sha256_file(SELECTED),
                "remaining": str(REMAINING.relative_to(ROOT)),
                "remaining_sha256": sha256_file(REMAINING),
            },
            "schedule": {
                "path": str(SCHEDULE.relative_to(ROOT)),
                "sha256": sha256_file(SCHEDULE),
                "episode_count": 32,
                "paired_randomized_order": True,
            },
            "execution": {
                "model": MODEL,
                "provider": PROVIDER,
                "model_fallback": False,
                "config": str(CONFIG.relative_to(ROOT)),
                "config_sha256": sha256_file(CONFIG),
                "protocol": str(PROTOCOL.relative_to(ROOT)),
                "protocol_sha256": sha256_file(PROTOCOL),
                "runner_sha256": sha256_file(RUNNER),
                "qualification_sha256": sha256_file(QUALIFICATION),
            },
            "primary_outcome": "Official Pass@1",
            "diagnostic_outcomes": [
                "terminal class",
                "first replay failure",
                "feedback-conditioned repair",
                "wall time",
                "token usage",
                "tool calls",
                "reported provider cost",
            ],
            "budget_policy": "token and cost are reported diagnostics, not success-stopping thresholds",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
