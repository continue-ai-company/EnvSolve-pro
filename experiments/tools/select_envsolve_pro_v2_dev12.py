#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

# ruff: noqa: E402 - workspace path bootstrapping precedes local imports.

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.utils.provenance import sha256_file


STUDY_ID = "envsolve-pro-v2-dev12"
MODEL = "deepseek/deepseek-v4-pro"
PROVIDER = "cloudflare"
SALT = "envsolve-pro-v2-dev12-2026-08-10"
TAKE = 12
CASE_ID_PATTERN = re.compile(
    r"envbench-python-[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+@[0-9a-f]{40}"
)
TERMINAL_EVIDENCE_GLOBS = (
    "*result*.json",
    "*adjudication*.json",
    "*closure*.json",
    "*amendment*.json",
    "*binding*.json",
    "*snapshot*.json",
)

SOURCE = ROOT / "experiments/cases/dev_pro_bad_case_census_v1_209.jsonl"
CANARY = ROOT / "experiments/cases/canary20.jsonl"
PROTECTED_TEST = ROOT / "experiments/cases/official_test100.jsonl"
CONFIG = ROOT / "experiments/configs/local_spark_envsolve_pro_v2_dev12.json"
PROTOCOL = ROOT / "experiments/protocols/envbench_python_official_v1.json"
SMOKE_CLOSURE = ROOT / "experiments/validations/envsolve_pro_v2_smoke_closure.json"
SELECTED = ROOT / "experiments/cases/dev_envsolve_pro_v2_pilot12.jsonl"
RESERVE = ROOT / "experiments/cases/dev_envsolve_pro_v2_reserve44.jsonl"
SCHEDULE = ROOT / "experiments/schedules/envsolve_pro_v2_dev12.json"
AUDIT = ROOT / "experiments/validations/envsolve_pro_v2_dev12_preselection_audit.json"
PREREGISTRATION = ROOT / "experiments/validations/envsolve_pro_v2_dev12_preregistration.json"

EXPECTED_SOURCE_HASHES = {
    SOURCE: "85d0d878a1f5f7ae70f9f93ec31e57cc99989a153c835adee94c56a49e0c6753",
    CANARY: "efaa56b0087776003432fa51ed585aa46729310ab014634352819ae622da709c",
    PROTECTED_TEST: "2c5f9345f12623e1ea197fdd6a1d801eaddb559722c918cbb13220de8f61cfea",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the outcome-independent EnvSolve-Pro V2 Dev-12 pilot."
    )
    parser.add_argument(
        "--manifest-root",
        action="append",
        type=Path,
        default=[],
        help="Run root containing <run>/<case>/manifest.json; may be repeated.",
    )
    return parser.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def _source_revision() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _case_ids_in_value(value: Any) -> set[str]:
    if isinstance(value, str):
        return set(CASE_ID_PATTERN.findall(value))
    if isinstance(value, list):
        return set().union(*(_case_ids_in_value(item) for item in value), set())
    if isinstance(value, dict):
        return set().union(*(_case_ids_in_value(item) for item in value.values()), set())
    return set()


def _manifest_evidence(roots: list[Path]) -> tuple[set[str], list[dict[str, str]]]:
    case_ids: set[str] = set()
    inventory: list[dict[str, str]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/*/manifest.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            case_id = payload.get("case", {}).get("case_id")
            if isinstance(case_id, str) and CASE_ID_PATTERN.fullmatch(case_id):
                case_ids.add(case_id)
            inventory.append(
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                }
            )
    return case_ids, inventory


def _terminal_evidence() -> tuple[set[str], list[dict[str, str]]]:
    paths = sorted(
        {
            path
            for pattern in TERMINAL_EVIDENCE_GLOBS
            for path in (ROOT / "experiments/validations").glob(pattern)
        }
    )
    case_ids: set[str] = set()
    inventory: list[dict[str, str]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        case_ids.update(_case_ids_in_value(payload))
        inventory.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
    return case_ids, inventory


def _inventory_sha256(items: list[dict[str, str]]) -> str:
    encoded = "".join(
        f"{item['path']}\0{item['sha256']}\n"
        for item in sorted(items, key=lambda item: item["path"])
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _arm_order(case_id: str) -> list[dict[str, Any]]:
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
    return arms if int(_digest(SALT, "arm-order", case_id), 16) % 2 == 0 else arms[::-1]


def main() -> int:
    args = _parse_args()
    outputs = (SELECTED, RESERVE, SCHEDULE, AUDIT, PREREGISTRATION)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"Refusing to overwrite frozen output: {existing[0]}")
    for path, expected_hash in EXPECTED_SOURCE_HASHES.items():
        if sha256_file(path) != expected_hash:
            raise RuntimeError(f"Frozen source hash mismatch: {path}")

    source_rows = _read_jsonl(SOURCE)
    source_by_id = {str(row["case_id"]): row for row in source_rows}
    if len(source_rows) != 209 or len(source_by_id) != 209:
        raise RuntimeError("Dev source must contain 209 unique case IDs")
    canary_ids = {str(row["case_id"]) for row in _read_jsonl(CANARY)}
    test_ids = {str(row["case_id"]) for row in _read_jsonl(PROTECTED_TEST)}
    dev_ids = set(source_by_id)
    if dev_ids & canary_ids or dev_ids & test_ids or canary_ids & test_ids:
        raise RuntimeError("Dev, Canary, and protected test identities must be disjoint")

    manifest_roots = list(args.manifest_root) or [
        Path("/Users/admin/Documents/AnyDeploy/runs"),
        ROOT / "runs",
    ]
    manifest_ids, manifest_inventory = _manifest_evidence(manifest_roots)
    terminal_ids, terminal_inventory = _terminal_evidence()
    consumed_dev = sorted(dev_ids & (manifest_ids | terminal_ids))
    eligible = sorted(dev_ids - set(consumed_dev))
    if len(consumed_dev) != 153 or len(eligible) != 56:
        raise RuntimeError(
            "Preselection evidence drifted; expected 153 consumed and 56 eligible Dev cases"
        )

    ranked = sorted(eligible, key=lambda case_id: _digest(SALT, "select", case_id))
    selected_ids = ranked[:TAKE]
    reserve_ids = ranked[TAKE:]
    _write_jsonl(
        SELECTED,
        (
            {**source_by_id[case_id], "split": "dev-envsolve-pro-v2-pilot12"}
            for case_id in selected_ids
        ),
    )
    _write_jsonl(
        RESERVE,
        (
            {**source_by_id[case_id], "split": "dev-envsolve-pro-v2-reserve44"}
            for case_id in reserve_ids
        ),
    )

    case_order = sorted(
        selected_ids,
        key=lambda case_id: _digest(SALT, "case-order", case_id),
    )
    episodes: list[dict[str, Any]] = []
    for case_position, case_id in enumerate(case_order, start=1):
        seed = int(_digest(SALT, "seed", case_id)[:8], 16)
        for pair_position, arm in enumerate(_arm_order(case_id), start=1):
            position = len(episodes) + 1
            episodes.append(
                {
                    "position": position,
                    "case_position": case_position,
                    "pair_position": pair_position,
                    "pair_id": f"dev12-case-{case_position:02d}",
                    "case_id": case_id,
                    "run_id": f"pro-v2-dev12-{position:02d}-{arm['arm']}",
                    "model": MODEL,
                    "provider": PROVIDER,
                    "seed": seed,
                    **arm,
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
            "provider": PROVIDER,
            "required_environment": {
                "OPENROUTER_API_KEY": "present-not-recorded",
                "OPENROUTER_PROVIDER_ORDER": PROVIDER,
            },
            "episode_timeout_seconds": 23000,
            "episodes": episodes,
        },
    )

    write_json(
        AUDIT,
        {
            "schema": "envsolve-pro-v2-dev12-preselection-audit-v1",
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "source_case_file": str(SOURCE.relative_to(ROOT)),
            "source_case_file_sha256": sha256_file(SOURCE),
            "dev_count": len(dev_ids),
            "canary_overlap": 0,
            "protected_test_overlap": 0,
            "manifest_roots": [str(path) for path in manifest_roots],
            "manifest_file_count": len(manifest_inventory),
            "manifest_inventory_sha256": _inventory_sha256(manifest_inventory),
            "terminal_evidence_file_count": len(terminal_inventory),
            "terminal_evidence_inventory_sha256": _inventory_sha256(terminal_inventory),
            "consumed_dev_count": len(consumed_dev),
            "consumed_dev_case_ids": consumed_dev,
            "eligible_dev_count": len(eligible),
            "eligible_dev_case_ids": eligible,
            "information_read_from_evidence": "case identity only",
            "outcome_or_failure_class_used": False,
        },
    )

    implementation_paths = (
        ROOT / "envsolve_harness/runners/openrouter_agent.py",
        ROOT / "envsolve_harness/runners/registry.py",
        ROOT / "envsolve_harness/replay_feedback.py",
        ROOT / "envsolve_harness/integrity/minimal.py",
        ROOT / "envsolve_harness/scripts/minimal_integrity.py",
        ROOT / "experiments/run_case.py",
        ROOT / "experiments/run_schedule.py",
    )
    write_json(
        PREREGISTRATION,
        {
            "schema": "envsolve-pro-v2-dev12-preregistration-v1",
            "study_id": STUDY_ID,
            "status": "frozen-before-first-dev12-episode",
            "preregistered_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": _source_revision(),
            "research_question": "Does same-session clean replay plus soft counterexample feedback improve Official Pass@1 over the same DeepSeek V4 Pro free Agent?",
            "selection": {
                "audit": str(AUDIT.relative_to(ROOT)),
                "audit_sha256": sha256_file(AUDIT),
                "salt": SALT,
                "algorithm": "ascending SHA256(salt + NUL + 'select' + NUL + case_id)",
                "take": TAKE,
                "selected": str(SELECTED.relative_to(ROOT)),
                "selected_sha256": sha256_file(SELECTED),
                "reserve": str(RESERVE.relative_to(ROOT)),
                "reserve_sha256": sha256_file(RESERVE),
                "repository_content_or_outcome_used": False,
            },
            "paired_conditions": [
                {
                    "arm": "A-F",
                    "runner": "deepseek-free-agent",
                    "mechanisms": ["F", "minimal-H"],
                },
                {
                    "arm": "B-FSR",
                    "runner": "envsolve-pro-v2",
                    "mechanisms": ["F", "S", "R", "minimal-H"],
                },
            ],
            "shared_identity": {
                "model": MODEL,
                "provider": PROVIDER,
                "reasoning_effort": "xhigh",
                "architecture": "linux/arm64",
                "image": "ghcr.io/jetbrains-research/envbench-python:latest",
                "official_feedback": "post-episode-only",
            },
            "order": {
                "case_order": "ascending salted SHA256",
                "within_pair_order": "salted SHA256 parity",
                "schedule": str(SCHEDULE.relative_to(ROOT)),
                "schedule_sha256": sha256_file(SCHEDULE),
            },
            "resource_policy": {
                "success_priority": True,
                "token_or_reported_cost_hard_threshold": False,
                "generation_wall_clock_safety_cap_seconds": 18000,
                "agent_request_safety_cap": 120,
                "provider_max_retries_per_request": 5,
                "package_cache_scope": "single episode only",
            },
            "primary_metric": "EnvBench Official Pass@1",
            "diagnostic_metrics": [
                "feedback-conditioned repair",
                "first clean-replay failure",
                "terminal class",
                "wall clock",
                "tokens",
                "tool calls",
                "replay count and time",
                "network bytes when available",
                "disk growth when available",
            ],
            "analysis_rule": "paired pass-rate difference; exact McNemar only when both arms have Boolean Official outcomes; infrastructure censoring reported separately",
            "implementation": {
                str(path.relative_to(ROOT)): sha256_file(path)
                for path in implementation_paths
            },
            "config": {
                "path": str(CONFIG.relative_to(ROOT)),
                "sha256": sha256_file(CONFIG),
            },
            "protocol": {
                "path": str(PROTOCOL.relative_to(ROOT)),
                "sha256": sha256_file(PROTOCOL),
            },
            "smoke_closure": {
                "path": str(SMOKE_CLOSURE.relative_to(ROOT)),
                "sha256": sha256_file(SMOKE_CLOSURE),
            },
            "stopping_rule": "complete all 24 primary episodes; do not change method after opening the batch",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
