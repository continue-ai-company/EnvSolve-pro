#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_jsonl


SOURCE = ROOT / "experiments/cases/train_untouched201.jsonl"
ROUND1_CASES = ROOT / "experiments/cases/envsolve_v0_discovery5.jsonl"
P0_PREREGISTRATION = (
    ROOT / "experiments/validations/p0_post_freeze_dev3_preregistration.json"
)
QUALIFICATION = (
    ROOT
    / "experiments/validations/envsolve_v0_round1_agent_state_qualification_results.json"
)
OUTPUT = ROOT / "experiments/cases/envsolve_v0_discovery5_round2.jsonl"
PREREGISTRATION = (
    ROOT
    / "experiments/validations/envsolve_v0_discovery5_round2_preregistration.json"
)
SALT = "envsolve-v0-discovery-round2-v1-2026-07-15"
REGISTERED_AT = "2026-07-15T04:33:00Z"
SIZE = 5

EXPECTED_INPUTS = {
    "experiments/cases/train_untouched201.jsonl": "076ef72dbab0bb5cdefa72b10b2a84d4391914716fb640c5ab5f579b46677bfe",
    "experiments/cases/envsolve_v0_discovery5.jsonl": "0c697c2c653b117c46d3c85a2854bb2b835234790b495b22a3a1d979fc05b37c",
    "experiments/validations/p0_post_freeze_dev3_preregistration.json": "612dad9cdab7af3cedde84a31b8dfc01e1b74b4d45ed11432edb1b4a60db7728",
    "experiments/validations/envsolve_v0_round1_agent_state_qualification_results.json": "247cdd8e0c7c1f23a6c16dc1f8ec84d7fbca8d13c8e489d1785af25843d55444",
    "experiments/configs/local_mac.json": "2a10d8206875741a1adbf1a0ee38174bd916b865f2a30d8de518c7c7b680f1ea",
    "experiments/protocols/envbench_python_official_v1.json": "f495b4949c8b1fd7b45b63dd1fb8ab47869867b977fc74b0d30e733b42cc92af",
}
METHOD_SOURCES = (
    "envsolve/v0/agent.py",
    "envsolve/v0/verification.py",
    "envsolve/v0/finalization.py",
    "envsolve/tools/run_v0_inference.py",
    "envsolve_harness/runners/envsolve_v0.py",
    "envsolve_harness/runners/envbench_agent.py",
)
EXECUTION_SOURCES = ("experiments/run_v0_discovery.py",)
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


def validate_inputs() -> None:
    actual = {relative: sha256_file(ROOT / relative) for relative in EXPECTED_INPUTS}
    if actual != EXPECTED_INPUTS:
        raise RuntimeError(f"Round 2 frozen input mismatch: {actual}")
    qualification = read_json(QUALIFICATION)
    if qualification["qualification"]["passed"] is not True:
        raise RuntimeError("Agent-state qualification did not pass")


def selection() -> tuple[list[dict[str, Any]], list[str]]:
    source = read_jsonl(SOURCE)
    excluded = {
        item["case_id"] for item in read_json(P0_PREREGISTRATION)["selected"]
    }
    excluded.update(item["case_id"] for item in read_jsonl(ROUND1_CASES))
    protected: set[str] = set()
    for relative in PROTECTED_CASE_FILES:
        protected.update(item["case_id"] for item in read_jsonl(ROOT / relative))
    selected = sorted(
        (item for item in source if item["case_id"] not in excluded),
        key=rank,
    )[:SIZE]
    selected_ids = {item["case_id"] for item in selected}
    if len(selected_ids) != SIZE or selected_ids & (excluded | protected):
        raise RuntimeError("Round 2 selection overlaps a consumed or protected case")
    return (
        [{**item, "split": "envsolve-v0-discovery-5-round2", "tags": []} for item in selected],
        sorted(excluded),
    )


def hashes(paths: tuple[str, ...]) -> dict[str, str]:
    return {relative: sha256_file(ROOT / relative) for relative in paths}


def build_preregistration(
    records: list[dict[str, Any]], excluded: list[str]
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "preregistration_id": "envsolve-v0-paired-discovery5-round2-v1",
        "registered_at": REGISTERED_AT,
        "purpose": "Collect the first valid outcome-blind paired failure distribution after qualifying the generic LangGraph transport repair.",
        "development_only": True,
        "selection": {
            "source": "experiments/cases/train_untouched201.jsonl",
            "source_sha256": EXPECTED_INPUTS["experiments/cases/train_untouched201.jsonl"],
            "algorithm": "Exclude P0 and Round-1 consumed cases, rank by SHA256(salt|repository@revision), and take the first five.",
            "salt": SALT,
            "size": SIZE,
            "outcome_blind": True,
            "selected_before_execution": True,
            "excluded_consumed_case_ids": excluded,
            "protected_splits": list(PROTECTED_CASE_FILES),
            "selected": [
                {"case_id": item["case_id"], "rank_sha256": rank(item)}
                for item in records
            ],
        },
        "qualification": {
            "path": "experiments/validations/envsolve_v0_round1_agent_state_qualification_results.json",
            "sha256": EXPECTED_INPUTS[
                "experiments/validations/envsolve_v0_round1_agent_state_qualification_results.json"
            ],
            "passed": True,
            "scope": "Transport only; no effectiveness claim inherited.",
        },
        "frozen_artifacts": {
            "case_file": {
                "path": "experiments/cases/envsolve_v0_discovery5_round2.jsonl",
                "sha256": sha256_file(OUTPUT),
            },
            "config": {
                "path": "experiments/configs/local_mac.json",
                "sha256": EXPECTED_INPUTS["experiments/configs/local_mac.json"],
            },
            "protocol": {
                "path": "experiments/protocols/envbench_python_official_v1.json",
                "sha256": EXPECTED_INPUTS[
                    "experiments/protocols/envbench_python_official_v1.json"
                ],
            },
            "method_sources": hashes(METHOD_SOURCES),
            "execution_sources": {
                **hashes(EXECUTION_SOURCES),
                "experiments/tools/freeze_envsolve_v0_discovery_round2.py": sha256_file(
                    Path(__file__)
                ),
            },
            "analysis_sources": hashes(ANALYSIS_SOURCES),
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
                "only_added_mechanism": "A fixed python -m pip check tool must pass at the final action-state boundary before distillation.",
            },
        ],
        "execution": {
            "model": "deepseek/deepseek-v4-pro",
            "provider_base_url": "https://openrouter.ai/api/v1",
            "seed": 0,
            "attempts_per_case_condition": 1,
            "max_workers": 1,
            "order": "Odd ranks run v0 then FreeAgent; even ranks reverse the order.",
            "automatic_case_retries": 0,
            "run_ids": {
                "envsolve_v0": "envsolve-v0-discovery5-r2-v0",
                "freeagent": "envsolve-v0-discovery5-r2-freeagent",
            },
            "coordinator_run_id": "envsolve-v0-discovery5-r2-paired",
            "analysis_output": "experiments/validations/envsolve_v0_discovery5_round2_results.json",
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
            "labels": [
                "solver_error",
                "verifier_rejection",
                "unsafe_or_unreplayable_action",
                "evaluator_error",
                "official_failure",
                "infrastructure_unknown",
                "success",
            ],
            "mechanism_admission": "Add no mechanism unless one error family appears in at least two valid v0 trajectories and is the plurality of attributable failures.",
            "no_dominant_error": "Freeze another outcome-blind discovery batch instead of choosing from a singleton.",
            "validation": "Any admitted mechanism must improve a separately frozen unseen batch before Canary-20.",
        },
        "forbidden": [
            "Per-case or repository-identity policy",
            "Method, prompt, verifier, budget, or replay change during the batch",
            "Canary-20 or Official-Test-100 inspection",
            "Treating infrastructure Unknown as solver Fail or Pass",
            "Confirmatory or leaderboard claims from this development batch",
        ],
        "integrity": {
            "p0_and_round1_consumed_cases_excluded": True,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "case_specific_policy": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    validate_inputs()
    records, excluded = selection()
    if args.verify:
        if read_jsonl(OUTPUT) != records:
            raise RuntimeError("Round 2 case file changed")
        if read_json(PREREGISTRATION) != build_preregistration(records, excluded):
            raise RuntimeError("Round 2 preregistration changed")
        print("EnvSolve v0 Discovery-5 Round 2 preregistration is valid")
        return 0
    write_jsonl(OUTPUT, records)
    write_json(PREREGISTRATION, build_preregistration(records, excluded))
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {PREREGISTRATION.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
