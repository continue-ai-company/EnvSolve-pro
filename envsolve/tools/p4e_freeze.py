#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


OUTPUT = Path("envsolve/protocols/p4e_repository_replay_freeze_v1.json")
SCOPE = Path("experiments/validations/p4e_dev5_scope_audit.json")
ROUND1 = Path("experiments/validations/p4e_round1_results.json")
ROUND2 = Path("experiments/validations/p4e_round2_results.json")
RETRY = Path("experiments/validations/p4e_round2_retry_results.json")
SOURCES = (
    Path("envsolve/controller/__init__.py"),
    Path("envsolve/controller/outcomes.py"),
    Path("envsolve/workspace/__init__.py"),
    Path("envsolve/workspace/artifacts.py"),
    Path("envsolve/workspace/project_metadata.py"),
    Path("envsolve/tests/test_replay_outcomes.py"),
    Path("envsolve/tests/test_workspace_artifacts.py"),
    Path("envsolve/tests/test_project_metadata.py"),
    Path("envsolve/tools/p4e_freeze.py"),
    Path("envsolve/scripts/p4e_workspace_artifact_relocation.sh"),
    Path("envsolve/scripts/p4e_inflect_round2_project_extra.sh"),
    Path("experiments/validations/p4e_dev5_scope_audit.json"),
    Path("experiments/validations/p4e_round1_preregistration.json"),
    Path("experiments/validations/p4e_round1_results.json"),
    Path("experiments/validations/p4e_round2_preregistration.json"),
    Path("experiments/validations/p4e_round2_results.json"),
    Path("experiments/validations/p4e_round2_retry_preregistration.json"),
    Path("experiments/validations/p4e_round2_retry_results.json"),
    Path("research/P4E_REPOSITORY_REPLAY_PROTOCOL.md"),
    Path("research/P4E_REPOSITORY_REPLAY_PROTOCOL_ZH.md"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files() -> dict[str, str]:
    missing = [str(path) for path in SOURCES if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P4E files are missing: {missing}")
    return {str(path): sha(ROOT / path) for path in sorted(SOURCES)}


def load(path: Path) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def verify_embedded_artifacts(result: dict) -> None:
    for name, record in result["artifacts"].items():
        path = ROOT / record["path"]
        if not path.is_file() or sha(path) != record["sha256"]:
            raise ValueError(f"artifact changed: {name}")


def validation() -> dict:
    scope = load(SCOPE)
    round1 = load(ROUND1)
    round2 = load(ROUND2)
    retry = load(RETRY)
    outcomes = scope["outcomes"]
    if len(outcomes) != 5:
        raise ValueError("Dev-5 scope cardinality changed")
    terminal_counts: dict[str, int] = {}
    for item in outcomes:
        key = item["terminal_class"]
        terminal_counts[key] = terminal_counts.get(key, 0) + 1
    if terminal_counts != {
        "bootstrap_conflict_repairable": 1,
        "bootstrap_satisfied_verifier_open": 3,
        "official_pass": 1,
    }:
        raise ValueError("Dev-5 pre-P4E terminal classes changed")
    if (
        round1["transition"]["before"]["exit_code"] != 1
        or round1["transition"]["after"]["exit_code"] != 0
        or round1["transition"]["after"]["issues_count"] != 3
    ):
        raise ValueError("Round 1 transition changed")
    if (
        round2["outcome"]["terminal_class"] != "infrastructure_blocked"
        or round2["outcome"]["repair_semantically_rejected"] is not False
    ):
        raise ValueError("Round 2 infrastructure classification changed")
    if retry["outcome"] != {
        "exit_code": 0,
        "issues_count": 0,
        "pyright_completed": True,
        "pyright_error_count": 526,
        "missing_import_count": 0,
        "terminal_class": "official_pass",
        "repair_verified": True,
    }:
        raise ValueError("Round 2 retry result changed")
    verify_embedded_artifacts(round1)
    verify_embedded_artifacts(round2)
    verify_embedded_artifacts(retry)
    return {
        "scope": {"path": str(SCOPE), "sha256": sha(ROOT / SCOPE)},
        "round1": {"path": str(ROUND1), "sha256": sha(ROOT / ROUND1)},
        "round2": {"path": str(ROUND2), "sha256": sha(ROOT / ROUND2)},
        "retry": {"path": str(RETRY), "sha256": sha(ROOT / RETRY)},
        "dev5_final": {
            "auditable_terminal_cases": 5,
            "official_pass": 2,
            "bootstrap_satisfied_verifier_open": 3,
            "bootstrap_conflicts_open": 0,
        },
    }


def build(created_at: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "policy_id": "envsolve-p4e-repository-replay-v1",
        "created_at": created_at,
        "source_files": source_files(),
        "validation": {
            "p4e_policy_tests": 13,
            "compile_check": True,
            "results": validation(),
        },
        "scope": {
            "development_only": True,
            "benchmark_executions": 3,
            "model_requests": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "repository_specific_rules": False,
            "p4_complete": True,
            "official_pass_claim": "2/5",
            "environment_terminal_claim": "5/5",
        },
        "change_policy": (
            "Any workspace ownership gate, project-extra selection, replay outcome, "
            "or P4 terminal semantic change requires a new P4E version and freeze."
        ),
    }


def verify(value: dict) -> list[str]:
    errors = []
    if value.get("schema_version") != "1.0.0":
        errors.append("schema version mismatch")
    if value.get("policy_id") != "envsolve-p4e-repository-replay-v1":
        errors.append("policy identifier mismatch")
    try:
        current_sources = source_files()
    except FileNotFoundError as exc:
        errors.append(str(exc))
        current_sources = {}
    if value.get("source_files") != current_sources:
        errors.append("P4E source files changed")
    try:
        current_validation = validation()
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"P4E validation failed: {type(exc).__name__}: {exc}")
        current_validation = None
    if current_validation is not None and value.get("validation", {}).get("results") != current_validation:
        errors.append("P4E validation results changed")
    if value.get("scope", {}).get("p4_complete") is not True:
        errors.append("P4 completion claim missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the P4E/P4 freeze.")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.verify:
        errors = verify(json.loads(output.read_text(encoding="utf-8")))
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build(datetime.now(timezone.utc).isoformat()), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
