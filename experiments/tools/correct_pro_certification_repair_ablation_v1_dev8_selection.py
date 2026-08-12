#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
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
AMENDMENT_ID = f"{STUDY_ID}-selection-v1-0-1"
SOURCE = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_minimal_b_v1_paired_53.jsonl"
)
ORIGINAL_SELECTED = (
    ROOT / "experiments/cases/dev_pro_certification_repair_ablation_v1_8.jsonl"
)
ORIGINAL_SCHEDULE = (
    ROOT / "experiments/schedules/pro_certification_repair_ablation_v1_dev8.json"
)
ORIGINAL_PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_dev8_preregistration.json"
)
POSITION4_AMENDMENT = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_dev8_position4_coordinator_amendment.json"
)
SELECTED = (
    ROOT
    / "experiments/cases/"
    "dev_pro_certification_repair_ablation_v1_8_v1_0_1.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_certification_repair_ablation_v1_37_v1_0_1.jsonl"
)
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_certification_repair_ablation_v1_dev8_v1_0_1.json"
)
AUDIT = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_preselection_consumed_repository_audit.json"
)
AMENDMENT = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_dev8_selection_amendment.json"
)

EXPECTED_INPUT_HASHES = {
    SOURCE: "62932c34602538f0653c25cce71adc43aeb2d95113eb2bf6a48901a305e28115",
    ORIGINAL_SELECTED: "bce8707d3abda53641733eb8e92bb1dd5b6b063c2c549d94bb4fae44b7e3a6d1",
    ORIGINAL_SCHEDULE: "463cb342cd1c27850693f6bbe87e8b4f92c47841aafbcf88c074072fe283d37a",
    ORIGINAL_PREREGISTRATION: "9273382b8ac4e363f754a8b3a94838a44446c904c26868af229e389f039887ee",
    POSITION4_AMENDMENT: "17bb88ef97adb5daa21059b70b69f3fd14407c6395ad34fc3670ce223003bebc",
}
SALT = "envsolve-pro-certification-repair-ablation-v1-dev8-2026-08-05"
TAKE = 8
MODEL = "gpt-5.5"
CURRENT_STUDY_RUN_DIRECTORY = STUDY_ID


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Correct the Dev-8 selection using pre-study run manifests."
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("/Users/admin/Documents/AnyDeploy/runs"),
    )
    return parser.parse_args()


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


def _manifest_evidence(
    runs_root: Path,
    pool_repositories: set[str],
) -> tuple[list[Path], dict[str, list[dict[str, str]]]]:
    current_study_root = (runs_root / CURRENT_STUDY_RUN_DIRECTORY).resolve()
    manifests = sorted(runs_root.glob("**/manifest.json"))
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in manifests:
        resolved = path.resolve()
        if current_study_root == resolved or current_study_root in resolved.parents:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        repository = payload.get("case", {}).get("repository")
        if repository not in pool_repositories:
            continue
        evidence[str(repository)].append(
            {
                "manifest_path": str(path.relative_to(runs_root)),
                "manifest_sha256": sha256_file(path),
            }
        )
    return manifests, dict(sorted(evidence.items()))


def _corrected_schedule(
    selected_by_repository: dict[str, dict[str, Any]],
    replacements: list[str],
) -> dict[str, Any]:
    original = json.loads(ORIGINAL_SCHEDULE.read_text(encoding="utf-8"))
    original_episodes = list(original["episodes"])
    original_blocks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for episode in original_episodes:
        original_blocks[int(episode["case_position"])].append(episode)

    replacement_slots = [3, 5, 7, 8]
    if len(replacements) != len(replacement_slots):
        raise RuntimeError("Unexpected replacement count")
    replacement_by_slot = dict(zip(replacement_slots, replacements))
    episodes: list[dict[str, Any]] = []
    for case_position in range(1, 9):
        block = sorted(original_blocks[case_position], key=lambda row: row["position"])
        if case_position not in replacement_by_slot:
            for episode in block:
                corrected = dict(episode)
                corrected["host"] = "mac"
                if int(corrected["position"]) == 4:
                    corrected["run_id"] = (
                        "pro-cert-repair-v1-dev8-04R1-C-retryable-minimal-b"
                    )
                episodes.append(corrected)
            continue

        repository = replacement_by_slot[case_position]
        row = selected_by_repository[repository]
        seed = int(_digest(SALT, "seed", repository)[:8], 16)
        first_position = int(block[0]["position"])
        for offset, condition in enumerate(_conditions(repository)):
            position = first_position + offset
            episodes.append(
                {
                    "position": position,
                    "case_position": case_position,
                    "host": "mac",
                    "case_id": str(row["case_id"]),
                    **condition,
                    "run_id": (
                        f"pro-cert-repair-v1-dev8-{position:02d}R1-"
                        f"{condition['condition']}"
                    ),
                    "model": MODEL,
                    "seed": seed,
                }
            )

    return {
        "schema_version": "1.0.0",
        "study_id": STUDY_ID,
        "selection_version": "1.0.1",
        "case_file": str(SELECTED.relative_to(ROOT)),
        "case_file_sha256": sha256_file(SELECTED),
        "model": MODEL,
        "episode_timeout_seconds": original["episode_timeout_seconds"],
        "episodes": episodes,
    }


def main() -> int:
    args = _parse_args()
    outputs = (SELECTED, REMAINING, SCHEDULE, AUDIT, AMENDMENT)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"Refusing to overwrite frozen output: {existing[0]}")
    for path, expected_hash in EXPECTED_INPUT_HASHES.items():
        if sha256_file(path) != expected_hash:
            raise RuntimeError(f"Frozen input hash does not match: {path}")

    rows = _read_jsonl(SOURCE)
    repositories = [str(row["repository"]) for row in rows]
    if len(rows) != 53 or len(repositories) != len(set(repositories)):
        raise RuntimeError("Unexpected source-pool identity set")
    manifests, evidence = _manifest_evidence(args.runs_root, set(repositories))
    consumed_repositories = set(evidence)

    ranked = sorted(rows, key=lambda row: _digest(SALT, str(row["repository"])))
    eligible = [
        row for row in ranked if str(row["repository"]) not in consumed_repositories
    ]
    selected = eligible[:TAKE]
    selected_repositories = {str(row["repository"]) for row in selected}
    remaining = [
        row
        for row in rows
        if str(row["repository"]) not in consumed_repositories
        and str(row["repository"]) not in selected_repositories
    ]
    if len(consumed_repositories) != 8 or len(selected) != 8 or len(remaining) != 37:
        raise RuntimeError("Historical audit produced an unexpected pool partition")

    original_selected = _read_jsonl(ORIGINAL_SELECTED)
    original_repositories = {str(row["repository"]) for row in original_selected}
    retained = sorted(original_repositories - consumed_repositories)
    stale = sorted(original_repositories & consumed_repositories)
    replacements = [
        str(row["repository"])
        for row in selected
        if str(row["repository"]) not in original_repositories
    ]
    if len(retained) != 4 or len(stale) != 4 or len(replacements) != 4:
        raise RuntimeError("Unexpected correction cardinality")

    _write_jsonl(
        SELECTED,
        [
            {**row, "split": "dev-pro-certification-repair-ablation-v1-8-v1-0-1"}
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
                    "ablation-v1-37-v1-0-1"
                ),
            }
            for row in remaining
        ],
    )
    selected_by_repository = {str(row["repository"]): row for row in selected}
    write_json(SCHEDULE, _corrected_schedule(selected_by_repository, replacements))

    frozen_at = datetime.now(timezone.utc).isoformat()
    write_json(
        AUDIT,
        {
            "schema_version": "1.0.0",
            "audit_id": f"{STUDY_ID}-preselection-consumption-audit",
            "frozen_at": frozen_at,
            "source_revision": _source_revision(),
            "runs_root": str(args.runs_root.resolve()),
            "excluded_current_study_run_root": str(
                (args.runs_root / CURRENT_STUDY_RUN_DIRECTORY).resolve()
            ),
            "manifest_files_discovered_including_excluded_study": len(manifests),
            "source_pool": _reference(SOURCE),
            "source_repository_count": len(rows),
            "identity_key": "case.repository",
            "consumed_repository_count": len(consumed_repositories),
            "consumed_repositories": [
                {
                    "repository": repository,
                    "prior_manifest_count": len(evidence[repository]),
                    "evidence": evidence[repository],
                }
                for repository in sorted(consumed_repositories)
            ],
        },
    )
    write_json(
        AMENDMENT,
        {
            "schema_version": "1.0.0",
            "amendment_id": AMENDMENT_ID,
            "frozen_at": frozen_at,
            "status": (
                "frozen-after-retained-position-1-began-and-before-any-"
                "replacement-repository-episode"
            ),
            "trigger": (
                "The static 53-repository pool still contained repositories with "
                "pre-study run manifests."
            ),
            "selection_information_used": [
                "repository identity",
                "existence of a pre-study manifest",
                "the original frozen salt",
            ],
            "selection_information_not_used": [
                "task outcome",
                "official score",
                "failure class",
                "repository contents",
            ],
            "original_inputs": {
                "selected": _reference(ORIGINAL_SELECTED),
                "schedule": _reference(ORIGINAL_SCHEDULE),
                "preregistration": _reference(ORIGINAL_PREREGISTRATION),
            },
            "audit": _reference(AUDIT),
            "correction": {
                "algorithm": (
                    "Remove every repository with a pre-study manifest, rank the "
                    "remaining repositories by the original ascending salted SHA256, "
                    "and take eight."
                ),
                "salt_unchanged": SALT,
                "retained_repositories": retained,
                "removed_stale_repositories": stale,
                "replacement_repositories_in_rank_order": replacements,
                "replacement_slot_mapping": {
                    "3": replacements[0],
                    "5": replacements[1],
                    "7": replacements[2],
                    "8": replacements[3],
                },
                "slot_mapping_rule": (
                    "Map replacement rank order to stale case-position order; retain "
                    "all valid case positions and regenerate each replacement's "
                    "condition rotation and seed from the frozen salt."
                ),
                "position_4_run_id": (
                    "pro-cert-repair-v1-dev8-04R1-C-retryable-minimal-b"
                ),
                "position_4_reason": _reference(POSITION4_AMENDMENT),
                "execution_host": "mac",
                "selected": _reference(SELECTED),
                "untouched_remaining": _reference(REMAINING),
                "schedule": _reference(SCHEDULE),
            },
            "execution_boundary": {
                "positions_1_to_3": "original frozen schedule and progress",
                "positions_4_to_24": "corrected v1.0.1 schedule and new progress",
                "replacement_case_outcomes_observed_before_freeze": False,
                "retained_position_1_outcome_used_for_correction": False,
            },
            "unchanged": [
                "three treatment arms",
                "model and reasoning effort",
                "official evaluator boundary",
                "algorithm source hashes",
                "timeouts",
                "public goal",
            ],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
