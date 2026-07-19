#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.core.io import read_jsonl, write_json, write_jsonl

CASE_ROOT = WORKSPACE_ROOT / "experiments/cases"
UPSTREAM_ALL = CASE_ROOT / "upstream/python_baseline_failure_all.jsonl"
UPSTREAM_TEST = CASE_ROOT / "upstream/python_baseline_failure_test.jsonl"

UPSTREAM_REVISION = "d1e96e6b10335cad40ac7b4f709f46a2c579765a"
UPSTREAM_ALL_SHA256 = "f145b829393a1da17aced5cf96d28173c2b4a9ebc7dcb9a849fa7a6f8031b01e"
UPSTREAM_TEST_SHA256 = "96bb402eee8d5717c3b32ee7879fb3bedd16a7f0a17abcffb14ae628fcace962"
CANARY_SALT = "envsolve-canary-v1-2026-07-13"
DEV_EXTENSION_SALT = "envsolve-dev-extension-v1-2026-07-13"
DEV_EXTENSION_SIZE = 3

DEV_CASES: dict[str, dict[str, str]] = {
    "jaraco/inflect": {
        "category": "standard-metadata",
        "rationale": "Pure-Python package with conventional packaging metadata",
    },
    "python-poetry/poetry": {
        "category": "version-and-package-manager",
        "rationale": "Lockfile and package-manager-driven environment",
    },
    "convexengineering/gpkit": {
        "category": "system-or-native-dependency",
        "rationale": "Scientific package with external solver and system dependency surface",
    },
    "pytest-dev/pytest-xdist": {
        "category": "test-and-development-dependencies",
        "rationale": "Test plugin whose usable environment depends on development tooling",
    },
    "markqvist/reticulum": {
        "category": "platform-optional-dependency",
        "rationale": "Platform-specific and optional imports expose verifier-fidelity risks",
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(record: dict[str, Any]) -> tuple[str, str]:
    return str(record["repository"]), str(record["revision"])


def case_record(record: dict[str, Any], split: str, tags: list[str] | None = None) -> dict[str, Any]:
    repository, revision = identity(record)
    return {
        "case_id": f"envbench-python-{repository.replace('/', '__')}@{revision}",
        "repository": repository,
        "revision": revision,
        "language": "python",
        "split": split,
        "tags": tags or [],
    }


def main() -> int:
    actual_hashes = {
        "all": sha256_file(UPSTREAM_ALL),
        "official_test": sha256_file(UPSTREAM_TEST),
    }
    expected_hashes = {"all": UPSTREAM_ALL_SHA256, "official_test": UPSTREAM_TEST_SHA256}
    if actual_hashes != expected_hashes:
        raise RuntimeError(f"Upstream EnvBench snapshot hash mismatch: {actual_hashes}")

    all_rows = read_jsonl(UPSTREAM_ALL)
    test_rows = read_jsonl(UPSTREAM_TEST)
    all_by_id = {identity(row): row for row in all_rows}
    test_ids = {identity(row) for row in test_rows}
    if len(all_rows) != 329 or len(all_by_id) != 329 or len(test_ids) != 100:
        raise RuntimeError("Unexpected EnvBench Python split cardinality")
    if not test_ids <= all_by_id.keys():
        raise RuntimeError("Official test contains cases absent from the 329-case source")

    train_rows = [row for row in all_rows if identity(row) not in test_ids]
    train_by_repo = {str(row["repository"]): row for row in train_rows}
    missing_dev = DEV_CASES.keys() - train_by_repo.keys()
    if missing_dev:
        raise RuntimeError(f"Dev cases are not in the reconstructed official train split: {sorted(missing_dev)}")

    dev_rows = [train_by_repo[repository] for repository in DEV_CASES]
    dev_ids = {identity(row) for row in dev_rows}
    canary_pool = [row for row in train_rows if identity(row) not in dev_ids]
    canary_rows = sorted(
        canary_pool,
        key=lambda row: hashlib.sha256(
            f"{CANARY_SALT}|{row['repository']}@{row['revision']}".encode("utf-8")
        ).hexdigest(),
    )[:20]
    canary_ids = {identity(row) for row in canary_rows}
    train_rest = [row for row in train_rows if identity(row) not in dev_ids | canary_ids]
    dev_extension_rows = sorted(
        train_rest,
        key=lambda row: hashlib.sha256(
            f"{DEV_EXTENSION_SALT}|{row['repository']}@{row['revision']}".encode(
                "utf-8"
            )
        ).hexdigest(),
    )[:DEV_EXTENSION_SIZE]
    dev_extension_ids = {identity(row) for row in dev_extension_rows}
    train_untouched = [
        row for row in train_rest if identity(row) not in dev_extension_ids
    ]

    generated = {
        "envbench_python_329.jsonl": [case_record(row, "leaderboard-329") for row in all_rows],
        "dev5.jsonl": [
            case_record(row, "dev-5", [DEV_CASES[str(row["repository"])]["category"]])
            for row in dev_rows
        ],
        "canary20.jsonl": [case_record(row, "canary-20") for row in canary_rows],
        "train_rest204.jsonl": [case_record(row, "train-rest-204") for row in train_rest],
        "dev_extension3.jsonl": [
            case_record(row, "dev-extension-3") for row in dev_extension_rows
        ],
        "train_untouched201.jsonl": [
            case_record(row, "train-untouched-201") for row in train_untouched
        ],
        "official_test100.jsonl": [case_record(row, "official-test-100") for row in test_rows],
    }
    expected_counts = {
        "envbench_python_329.jsonl": 329,
        "dev5.jsonl": 5,
        "canary20.jsonl": 20,
        "train_rest204.jsonl": 204,
        "dev_extension3.jsonl": 3,
        "train_untouched201.jsonl": 201,
        "official_test100.jsonl": 100,
    }
    for filename, records in generated.items():
        if len(records) != expected_counts[filename]:
            raise RuntimeError(f"Unexpected generated count for {filename}: {len(records)}")
        write_jsonl(CASE_ROOT / filename, records)

    write_json(
        CASE_ROOT / "split_manifest.json",
        {
            "schema_version": "1.1.0",
            "source": {
                "repository": "JetBrains-Research/EnvBench",
                "repository_type": "dataset",
                "revision": UPSTREAM_REVISION,
                "files": {
                    "splits/python_baseline_failure.jsonl": UPSTREAM_ALL_SHA256,
                    "splits/python_baseline_failure_test.jsonl": UPSTREAM_TEST_SHA256,
                },
                "note": "Official train is reconstructed as all-329 minus official-test-100 because the upstream train JSONL has a concatenated record at line 72.",
            },
            "selection": {
                "dev5": DEV_CASES,
                "canary20": {
                    "algorithm": "First 20 SHA256-ranked cases from official train excluding Dev-5",
                    "salt": CANARY_SALT,
                    "outcome_blind": True,
                },
                "dev_extension3": {
                    "algorithm": (
                        "First 3 SHA256-ranked cases from Train-Rest-204 using "
                        "the frozen development-extension salt"
                    ),
                    "salt": DEV_EXTENSION_SALT,
                    "outcome_blind": True,
                    "selected_before_execution": True,
                    "excluded_from_future_training_pool": True,
                },
            },
            "counts": {
                "all": 329,
                "official_train_reconstructed": 229,
                "dev5": 5,
                "canary20": 20,
                "train_rest": 204,
                "dev_extension": 3,
                "train_untouched_after_dev_extension": 201,
                "official_test": 100,
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
