#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_jsonl


SOURCE = WORKSPACE_ROOT / "experiments/cases/train_untouched201.jsonl"
OUTPUT = WORKSPACE_ROOT / "experiments/cases/envsolve_v0_discovery5.jsonl"
PREREGISTRATION = (
    WORKSPACE_ROOT
    / "experiments/validations/envsolve_v0_discovery5_round1_preregistration.json"
)
P0_PREREGISTRATION = (
    WORKSPACE_ROOT
    / "experiments/validations/p0_post_freeze_dev3_preregistration.json"
)
CONFIG = WORKSPACE_ROOT / "experiments/configs/local_mac.json"
PROTOCOL = WORKSPACE_ROOT / "experiments/protocols/envbench_python_official_v1.json"
SALT = "envsolve-v0-discovery-v1-2026-07-15"
SIZE = 5
REGISTERED_AT = "2026-07-14T16:23:28Z"

EXPECTED_HASHES = {
    "experiments/cases/train_untouched201.jsonl": (
        "076ef72dbab0bb5cdefa72b10b2a84d4391914716fb640c5ab5f579b46677bfe"
    ),
    "experiments/validations/p0_post_freeze_dev3_preregistration.json": (
        "612dad9cdab7af3cedde84a31b8dfc01e1b74b4d45ed11432edb1b4a60db7728"
    ),
    "experiments/configs/local_mac.json": (
        "2a10d8206875741a1adbf1a0ee38174bd916b865f2a30d8de518c7c7b680f1ea"
    ),
    "experiments/protocols/envbench_python_official_v1.json": (
        "f495b4949c8b1fd7b45b63dd1fb8ab47869867b977fc74b0d30e733b42cc92af"
    ),
}

METHOD_SOURCES = (
    "envsolve/v0/agent.py",
    "envsolve/v0/verification.py",
    "envsolve/v0/finalization.py",
    "envsolve/tools/run_v0_inference.py",
    "envsolve_harness/runners/envsolve_v0.py",
    "envsolve_harness/runners/envbench_agent.py",
    "experiments/run_v0_discovery.py",
)
ANALYSIS_SOURCES = (
    "envsolve/analysis/discovery.py",
    "envsolve/analysis/trajectory.py",
    "envsolve/tools/analyze_v0_discovery.py",
)
PROTECTED_CASE_FILES = (
    "experiments/cases/dev5.jsonl",
    "experiments/cases/dev_extension3.jsonl",
    "experiments/cases/canary20.jsonl",
    "experiments/cases/official_test100.jsonl",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rank(record: dict[str, Any]) -> str:
    identity = f"{record['repository']}@{record['revision']}"
    return hashlib.sha256(f"{SALT}|{identity}".encode()).hexdigest()


def validate_frozen_inputs() -> None:
    actual = {
        relative: sha256_file(WORKSPACE_ROOT / relative)
        for relative in EXPECTED_HASHES
    }
    if actual != EXPECTED_HASHES:
        raise RuntimeError(f"Frozen discovery inputs changed: {actual}")


def selected_records() -> tuple[list[dict[str, Any]], list[str]]:
    source = read_jsonl(SOURCE)
    if len(source) != 201:
        raise RuntimeError(f"Expected 201 source cases, found {len(source)}")
    p0 = read_json(P0_PREREGISTRATION)
    excluded = {str(item["case_id"]) for item in p0["selected"]}
    protected: set[str] = set()
    for relative in PROTECTED_CASE_FILES:
        protected.update(
            str(item["case_id"])
            for item in read_jsonl(WORKSPACE_ROOT / relative)
        )
    pool = [item for item in source if str(item["case_id"]) not in excluded]
    selected = sorted(pool, key=rank)[:SIZE]
    selected_ids = {str(item["case_id"]) for item in selected}
    if len(selected) != SIZE or selected_ids & (excluded | protected):
        raise RuntimeError("Discovery selection overlaps a consumed or protected split")
    records = [
        {
            **item,
            "split": "envsolve-v0-discovery-5",
            "tags": [],
        }
        for item in selected
    ]
    return records, sorted(excluded)


def preregistration(records: list[dict[str, Any]], excluded: list[str]) -> dict[str, Any]:
    selected = [
        {
            "case_id": item["case_id"],
            "rank_sha256": rank(item),
        }
        for item in records
    ]
    source_hashes = {
        relative: sha256_file(WORKSPACE_ROOT / relative)
        for relative in METHOD_SOURCES
    }
    source_hashes["experiments/tools/freeze_envsolve_v0_discovery.py"] = sha256_file(
        Path(__file__)
    )
    analysis_hashes = {
        relative: sha256_file(WORKSPACE_ROOT / relative)
        for relative in ANALYSIS_SOURCES
    }
    return {
        "schema_version": "1.0.0",
        "preregistration_id": "envsolve-v0-paired-discovery5-round1-v1",
        "registered_at": REGISTERED_AT,
        "purpose": (
            "Obtain the first outcome-blind EnvSolve v0 failure distribution and a "
            "same-backbone paired reference before selecting any additional mechanism."
        ),
        "development_only": True,
        "selection": {
            "source": "experiments/cases/train_untouched201.jsonl",
            "source_sha256": EXPECTED_HASHES[
                "experiments/cases/train_untouched201.jsonl"
            ],
            "algorithm": (
                "Exclude P0 post-freeze consumed cases, rank the remainder by "
                "SHA256(salt|repository@revision), and take the first five."
            ),
            "salt": SALT,
            "size": SIZE,
            "outcome_blind": True,
            "selected_before_execution": True,
            "excluded_consumed_case_ids": excluded,
            "protected_splits": list(PROTECTED_CASE_FILES),
            "selected": selected,
        },
        "frozen_artifacts": {
            "case_file": {
                "path": "experiments/cases/envsolve_v0_discovery5.jsonl",
                "sha256": sha256_file(OUTPUT),
            },
            "config": {
                "path": "experiments/configs/local_mac.json",
                "sha256": EXPECTED_HASHES["experiments/configs/local_mac.json"],
            },
            "protocol": {
                "path": "experiments/protocols/envbench_python_official_v1.json",
                "sha256": EXPECTED_HASHES[
                    "experiments/protocols/envbench_python_official_v1.json"
                ],
            },
            "method_sources": source_hashes,
            "analysis_sources": analysis_hashes,
        },
        "paired_conditions": [
            {
                "condition": "freeagent",
                "runner": "envbench-agent",
                "method": "envbench-react-freeagent",
            },
            {
                "condition": "envsolve_v0",
                "runner": "envsolve-v0",
                "method": "envsolve-v0",
                "only_added_mechanism": (
                    "A fixed python -m pip check tool must pass at the final action-state "
                    "boundary before trajectory distillation."
                ),
            },
        ],
        "execution": {
            "model": "deepseek/deepseek-v4-pro",
            "provider_protocol": "OpenAI-compatible API via environment variables",
            "provider_base_url": "https://openrouter.ai/api/v1",
            "seed": 0,
            "attempts_per_case_condition": 1,
            "max_workers": 1,
            "order": (
                "Process cases by frozen rank; on odd ranks run EnvSolve v0 then "
                "FreeAgent, and on even ranks reverse the order."
            ),
            "automatic_case_retries": 0,
            "infrastructure_retry": (
                "Preserve the first attempt as Unknown; any retry requires a separate "
                "preregistration with unchanged method sources and execution limits."
            ),
            "official_evaluator_after_generation": True,
        },
        "resource_limits": {
            "generation_timeout_seconds": 7200,
            "model_request_timeout_seconds": 180,
            "model_max_retries": 2,
            "model_max_output_tokens_per_request": 16384,
            "model_max_requests": 30,
            "model_max_total_tokens": 1000000,
            "model_max_estimated_cost_usd": 5.0,
            "agent_max_iterations": 30,
            "bash_command_timeout_seconds": 900,
        },
        "analysis_policy": {
            "collect_before_analysis": "Complete and preserve all ten first attempts.",
            "unit": "Paired case plus complete action/result trajectory.",
            "labels": [
                "solver_error",
                "verifier_rejection",
                "official_failure",
                "unsafe_or_unreplayable_action",
                "evaluator_error",
                "infrastructure_unknown",
            ],
            "mechanism_admission": (
                "Add no mechanism unless one error family appears in at least two "
                "EnvSolve v0 cases and is the plurality of attributable failures."
            ),
            "no_dominant_error": (
                "Freeze another outcome-blind discovery batch instead of choosing a "
                "mechanism from a singleton."
            ),
            "validation": (
                "Any admitted mechanism must improve a separately frozen unseen "
                "development batch before Canary-20 execution."
            ),
        },
        "forbidden": [
            "Per-case policy or repository-identity branches",
            "Method, prompt, verifier, budget, or script changes during the batch",
            "Canary-20 or Official-Test-100 inspection",
            "Treating infrastructure Unknown as solver Fail or Pass",
            "Claiming confirmatory or leaderboard evidence from this development batch",
        ],
        "integrity": {
            "p0_consumed_cases_excluded": True,
            "dev5_excluded_by_source": True,
            "dev_extension3_excluded_by_source": True,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "case_specific_policy": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    validate_frozen_inputs()
    records, excluded = selected_records()
    if args.verify:
        if read_jsonl(OUTPUT) != records:
            raise RuntimeError("Frozen EnvSolve v0 Discovery-5 case file changed")
        expected = preregistration(records, excluded)
        if read_json(PREREGISTRATION) != expected:
            raise RuntimeError("Frozen EnvSolve v0 preregistration changed")
        print("EnvSolve v0 Discovery-5 preregistration is valid")
        return 0
    write_jsonl(OUTPUT, records)
    write_json(PREREGISTRATION, preregistration(records, excluded))
    print(f"Wrote {OUTPUT.relative_to(WORKSPACE_ROOT)}")
    print(f"Wrote {PREREGISTRATION.relative_to(WORKSPACE_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
