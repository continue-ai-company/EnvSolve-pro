#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
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
from envsolve_harness.runners.certification_repair_boundary_v2 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
    ONE_SHOT_METHOD,
    BoundaryV2QualifiedCodexCliRunner,
    BoundaryV2QualifiedMinimalBRunner,
    BoundaryV2QualifiedOneShotRunner,
)
from envsolve_harness.utils.provenance import sha256_file


STUDY_ID = "envsolve-pro-certification-repair-boundary-v2-dev8"
SALT = "envsolve-pro-certification-repair-ablation-v1-dev8-2026-08-05"
MODEL = "gpt-5.5"
TAKE_REPLACEMENTS = 2
RUNS_ROOT = Path("/Users/admin/Documents/AnyDeploy/runs")

ORIGINAL_SELECTED = (
    ROOT / "experiments/cases/dev_pro_certification_repair_ablation_v1_8_v1_0_1.jsonl"
)
UNTOUCHED_POOL = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_certification_repair_ablation_v1_37_v1_0_1.jsonl"
)
ORIGINAL_SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_certification_repair_ablation_v1_dev8_v1_0_1.json"
)
VALIDITY_STOP = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_dev8_validity_stop_amendment.json"
)
BOUNDARY_FREEZE = (
    ROOT
    / "experiments/protocols/"
    "envsolve_pro_certification_repair_boundary_v2_implementation_freeze.json"
)
CONFIG = (
    ROOT
    / "experiments/configs/"
    "local_mac_pro_certification_repair_boundary_v2_dev8.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_public_goal_v2.json"
CASE_ENTRYPOINT = ROOT / "experiments/run_replay_ablation_boundary_v2_case.py"
SCHEDULE_ENTRYPOINT = ROOT / "experiments/run_replay_ablation_boundary_v2_schedule.py"

SELECTED = (
    ROOT / "experiments/cases/dev_pro_certification_repair_boundary_v2_8.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_certification_repair_boundary_v2_35.jsonl"
)
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_certification_repair_boundary_v2_dev8.json"
)
IDENTITY_AUDIT = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_boundary_v2_replacement_identity_audit.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_boundary_v2_dev8_preregistration.json"
)

EXPECTED_INPUT_HASHES = {
    ORIGINAL_SELECTED: "1c3da3347271aee8d7bd8bd8ad8a6375e9759fc2fc1d219330db6af21d6e4b1c",
    UNTOUCHED_POOL: "512954f013026c1a240192da2cd070a650564b06adab68b089f8040a118c0b00",
    ORIGINAL_SCHEDULE: "c6e36ba47a18337eec611502c3438e59b2d0ee4c79ecb5f377cc6903e6f0f238",
    VALIDITY_STOP: "9db6bba77bb023d70ba5be8baf6e278fe5ae853ec66c28f302fbaf84362c3935",
    BOUNDARY_FREEZE: "38027f95a6ace0f8ed10f6358cbc916629f3def5af2910accc81ce9f100bc895",
}


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


def _reference(path: Path) -> dict[str, str]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
    }


def _source_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _manifest_identity_audit(
    pool_repositories: set[str],
) -> tuple[dict[str, list[dict[str, str]]], int]:
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)
    manifests = sorted(RUNS_ROOT.glob("**/manifest.json"))
    for path in manifests:
        payload = json.loads(path.read_text(encoding="utf-8"))
        repository = payload.get("case", {}).get("repository")
        if repository not in pool_repositories:
            continue
        evidence[str(repository)].append(
            {
                "manifest_path": str(path.relative_to(RUNS_ROOT)),
                "manifest_sha256": sha256_file(path),
            }
        )
    return dict(sorted(evidence.items())), len(manifests)


def _select_replacements(
    rows: list[dict[str, Any]],
    consumed_repositories: set[str],
    take: int = TAKE_REPLACEMENTS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked = sorted(rows, key=lambda row: _digest(SALT, str(row["repository"])))
    eligible = [
        row
        for row in ranked
        if str(row["repository"]) not in consumed_repositories
    ]
    if len(eligible) < take:
        raise RuntimeError("Not enough untouched replacement identities")
    return eligible[:take], eligible[take:]


def _conditions(repository: str) -> list[dict[str, str]]:
    values = [
        {
            "condition": "A-strong-agent-control",
            "runner": BoundaryV2QualifiedCodexCliRunner.runner_name,
            "method": CONTROL_METHOD,
        },
        {
            "condition": "B-one-shot-certification",
            "runner": BoundaryV2QualifiedOneShotRunner.runner_name,
            "method": ONE_SHOT_METHOD,
        },
        {
            "condition": "C-retryable-minimal-b",
            "runner": BoundaryV2QualifiedMinimalBRunner.runner_name,
            "method": MINIMAL_B_METHOD,
        },
    ]
    offset = int(_digest(SALT, "condition-order", repository), 16) % len(values)
    return values[offset:] + values[:offset]


def _carry_forward_rows() -> list[dict[str, Any]]:
    rows = _read_jsonl(ORIGINAL_SELECTED)
    by_case_id = {str(row["case_id"]): row for row in rows}
    schedule = json.loads(ORIGINAL_SCHEDULE.read_text(encoding="utf-8"))
    ordered_case_ids: list[str] = []
    for episode in schedule["episodes"]:
        case_id = str(episode["case_id"])
        if case_id not in ordered_case_ids:
            ordered_case_ids.append(case_id)
    stop = json.loads(VALIDITY_STOP.read_text(encoding="utf-8"))
    expected = set(
        stop["case_accounting"][
            "selected_but_unexecuted_and_uninspected_repositories"
        ]
    )
    carried = [
        by_case_id[case_id]
        for case_id in ordered_case_ids
        if str(by_case_id[case_id]["repository"]) in expected
    ]
    if len(carried) != 6 or {str(row["repository"]) for row in carried} != expected:
        raise RuntimeError("Carry-forward identity set does not match validity stop")
    return carried


def main() -> int:
    outputs = (SELECTED, REMAINING, SCHEDULE, IDENTITY_AUDIT, PREREGISTRATION)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"Refusing to overwrite frozen output: {existing[0]}")
    for path, expected in EXPECTED_INPUT_HASHES.items():
        if sha256_file(path) != expected:
            raise RuntimeError(f"Frozen input hash does not match: {path}")

    pool = _read_jsonl(UNTOUCHED_POOL)
    repositories = [str(row["repository"]) for row in pool]
    if len(pool) != 37 or len(repositories) != len(set(repositories)):
        raise RuntimeError("Unexpected untouched replacement pool")
    evidence, manifest_count = _manifest_identity_audit(set(repositories))
    replacements, remaining = _select_replacements(pool, set(evidence))
    carry_forward = _carry_forward_rows()
    selected = replacements + carry_forward
    selected_repositories = [str(row["repository"]) for row in selected]
    if len(selected_repositories) != len(set(selected_repositories)):
        raise RuntimeError("Boundary-v2 selection contains duplicate identities")

    split = "dev-pro-certification-repair-boundary-v2-8"
    _write_jsonl(SELECTED, [{**row, "split": split} for row in selected])
    remaining_split = "train-untouched-after-pro-certification-repair-boundary-v2"
    _write_jsonl(
        REMAINING,
        [{**row, "split": remaining_split} for row in remaining],
    )

    episodes: list[dict[str, Any]] = []
    for case_position, row in enumerate(selected, start=1):
        repository = str(row["repository"])
        seed = int(_digest(SALT, "seed", repository)[:8], 16)
        for condition in _conditions(repository):
            position = len(episodes) + 1
            episodes.append(
                {
                    "position": position,
                    "case_position": case_position,
                    "host": "mac",
                    "case_id": str(row["case_id"]),
                    **condition,
                    "run_id": (
                        f"pro-cert-repair-boundary-v2-dev8-{position:02d}-"
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

    frozen_at = datetime.now(timezone.utc).isoformat()
    write_json(
        IDENTITY_AUDIT,
        {
            "schema_version": "1.0.0",
            "audit_id": f"{STUDY_ID}-replacement-identity-audit",
            "frozen_at": frozen_at,
            "runs_root": str(RUNS_ROOT),
            "manifest_files_scanned": manifest_count,
            "selection_information_used": [
                "repository identity",
                "existence of any prior manifest",
                "original frozen salt",
            ],
            "selection_information_not_used": [
                "repository contents",
                "task outcome",
                "official score",
                "failure class",
            ],
            "pool_rows": len(pool),
            "prior_manifest_identity_count": len(evidence),
            "prior_manifest_evidence": evidence,
            "replacement_repositories_in_rank_order": [
                str(row["repository"]) for row in replacements
            ],
        },
    )

    freeze_files = (
        CONFIG,
        PROTOCOL,
        BOUNDARY_FREEZE,
        CASE_ENTRYPOINT,
        SCHEDULE_ENTRYPOINT,
        Path(__file__).resolve(),
    )
    write_json(
        PREREGISTRATION,
        {
            "schema_version": "1.0.0",
            "study_id": STUDY_ID,
            "status": "frozen-before-any-boundary-v2-effectiveness-episode",
            "preregistered_at": frozen_at,
            "source_revision": _source_revision(),
            "claim_scope": "Repository-disjoint development mechanism gate under the corrected shared boundary.",
            "selection": {
                "carry_forward_count": 6,
                "carry_forward_policy": "Only identities frozen as unexecuted and uninspected by the validity-stop amendment.",
                "replacement_count": TAKE_REPLACEMENTS,
                "replacement_source": _reference(UNTOUCHED_POOL),
                "replacement_algorithm": "Exclude identities with any manifest, then take the next repositories by the original ascending salted SHA256 rank.",
                "salt": SALT,
                "repository_content_or_outcome_used": False,
                "selected": _reference(SELECTED),
                "remaining": _reference(REMAINING),
                "identity_audit": _reference(IDENTITY_AUDIT)
            },
            "conditions": [
                {
                    "arm": "A",
                    "runner": BoundaryV2QualifiedCodexCliRunner.runner_name,
                    "method": CONTROL_METHOD,
                    "generation_clean_replays": 0
                },
                {
                    "arm": "B",
                    "runner": BoundaryV2QualifiedOneShotRunner.runner_name,
                    "method": ONE_SHOT_METHOD,
                    "maximum_executed_clean_replays": 1
                },
                {
                    "arm": "C",
                    "runner": BoundaryV2QualifiedMinimalBRunner.runner_name,
                    "method": MINIMAL_B_METHOD,
                    "clean_replays_repeatable": True
                }
            ],
            "mechanism_decision": {
                "certification_aware_construction": "Compare A versus B.",
                "feedback_conditioned_repair": "Count only C first replay Fail or Unknown followed by a different passing replay in the same session and terminal Official Pass.",
                "dormant_loop": "If all C first replays pass, do not claim iterative repair and do not add structured state."
            },
            "analysis_policy": {
                "primary_metric": "Official Pass@1",
                "official_and_protocol_admissibility_reported_separately": True,
                "paired_by_repository": True,
                "all_24_episodes_before_algorithm_change": True,
                "individual_case_rules_forbidden": True,
                "infrastructure_unknown_excluded_from_effect_denominator": True,
                "token_and_price_are_measurements_not_success_stopping_budgets": True,
                "host": "mac for all three arms to avoid a host-by-treatment confound"
            },
            "artifacts": {
                "boundary_freeze": _reference(BOUNDARY_FREEZE),
                "config": _reference(CONFIG),
                "protocol": _reference(PROTOCOL),
                "schedule": _reference(SCHEDULE),
                "freeze_files": {
                    str(path.relative_to(ROOT)): sha256_file(path)
                    for path in freeze_files
                }
            }
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
