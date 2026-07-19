#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.state import audit_state_artifacts


SCHEMA_VERSION = "1.0.0"
POLICY_ID = "envsolve-context-transfer-runtime-validation-v1"
OUTPUT_PATH = Path("envsolve/protocols/p4c_context_transfer_freeze_v1.json")
NEGATIVE_PATH = Path("experiments/validations/p4c_neps_runtime_results.json")
POSITIVE_PATH = Path("experiments/validations/p4c_neps_runtime_results_v2.json")
SOURCE_PATHS = (
    Path("envsolve/execution/__init__.py"),
    Path("envsolve/execution/runtime.py"),
    Path("envsolve/provenance/__init__.py"),
    Path("envsolve/provenance/context_transfer.py"),
    Path("envsolve/tests/test_context_transfer.py"),
    Path("envsolve/tests/test_runtime_execution.py"),
    Path("envsolve/tools/p4c_freeze.py"),
    Path("envsolve/tools/run_p4c_runtime_validation.py"),
    Path("research/P4C_CONTEXT_TRANSFER_PROTOCOL.md"),
)
EXPECTED_COMMANDS = [
    "pyenv local 3.11.7 && hash -r",
    "python --version",
]
EXPECTED_CONTRACT = {
    "manager": "pyenv",
    "path_prepend": ["/root/.pyenv/shims"],
    "required_executable": "/root/.pyenv/shims/python",
    "source_evidence_id": "evidence-transferred-evidence-context-tool-pyenv",
    "tool_path": "/root/.pyenv/bin/pyenv",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path, paths: tuple[Path, ...]) -> dict[str, str]:
    missing = [str(path) for path in paths if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P4C freeze source files are missing: {missing}")
    return {str(path): _sha256(root / path) for path in sorted(paths)}


def _local_image_id(reference: str) -> str:
    process = subprocess.run(
        ["docker", "image", "inspect", reference, "--format", "{{.Id}}"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError(process.stderr.strip() or "evaluator image inspect failed")
    return process.stdout.strip()


def _artifact(root: Path, value: dict, expected_events: int) -> dict:
    artifact = value["artifact"]
    artifact_root = root / artifact["root"]
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    plan = artifact_root / "plan.json"
    audit = audit_state_artifacts(event_log, snapshot, artifact["case_id"])
    if not audit.valid:
        raise ValueError(f"P4C artifact audit failed: {audit.errors}")
    if audit.event_count != expected_events or audit.event_count != artifact["event_count"]:
        raise ValueError("P4C artifact event count changed")
    if audit.snapshot_hash != artifact["snapshot_hash"]:
        raise ValueError("P4C artifact snapshot hash changed")
    hashes = {
        "event_log_sha256": _sha256(event_log),
        "snapshot_sha256": _sha256(snapshot),
        "plan_sha256": _sha256(plan),
    }
    for name, digest in hashes.items():
        if digest != artifact[name]:
            raise ValueError(f"P4C artifact {name} changed")
    return {
        **artifact,
        "snapshot_verifications": json.loads(
            snapshot.read_text(encoding="utf-8")
        ).get("verifications", []),
    }


def _check_lineage_files(root: Path, value: dict) -> None:
    lineage = value["lineage"]
    paths = {
        "target_manifest_sha256": Path(
            "runs/p0-post-freeze-dev3-deterministic-v2/"
            "envbench-python-automl__neps__"
            "6a6c0c273f59036b8605086c43a6a714ea02bd23/manifest.json"
        ),
        "target_audit_sha256": Path(
            "runs/p0-post-freeze-dev3-deterministic-v2/"
            "envbench-python-automl__neps__"
            "6a6c0c273f59036b8605086c43a6a714ea02bd23/audit.json"
        ),
        "target_raw_result_sha256": Path(lineage["target_raw_result_path"]),
        "source_summary_sha256": Path(
            "experiments/validations/p4b_context_image_results.json"
        ),
    }
    for field, path in paths.items():
        if _sha256(root / path) != lineage[field]:
            raise ValueError(f"P4C lineage source changed: {field}")


def _validation(root: Path) -> dict:
    negative_path = root / NEGATIVE_PATH
    positive_path = root / POSITIVE_PATH
    negative = json.loads(negative_path.read_text(encoding="utf-8"))
    positive = json.loads(positive_path.read_text(encoding="utf-8"))
    if negative.get("validation_id") != "p4c-neps-runtime-transfer-v1":
        raise ValueError("Unexpected P4C negative validation identifier")
    if positive.get("validation_id") != "p4c-neps-runtime-transfer-v2":
        raise ValueError("Unexpected P4C positive validation identifier")
    for value in (negative, positive):
        if value.get("commands") != EXPECTED_COMMANDS:
            raise ValueError("P4C repair commands changed")
        if value.get("development_only") is not True:
            raise ValueError("P4C result lost its development-only label")
        if value.get("isolation") != {
            "mounts": [],
            "network": "none",
            "official_evaluation": False,
            "repository_mounted": False,
        }:
            raise ValueError("P4C isolation record changed")
        integrity = value.get("integrity", {})
        if integrity != {
            "canary20_inspected": False,
            "model_requests": 0,
            "new_benchmark_cases": 0,
            "new_benchmark_executions": 0,
            "official_test100_inspected": False,
        }:
            raise ValueError("P4C integrity record changed")
        _check_lineage_files(root, value)
    if any(
        negative.get(field) != positive.get(field)
        for field in ("repository", "revision", "image", "lineage", "context", "plan")
    ):
        raise ValueError("P4C v1 and v2 do not share the same frozen inputs and plan")
    image = positive["image"]
    if _local_image_id(image["reference"]) != image["id"]:
        raise ValueError("P4C evaluator image identity changed")
    if negative["execution"]["goal_status"] != "blocked":
        raise ValueError("P4C diagnostic trajectory is no longer blocked")
    if negative["post_state"]["satisfiable"] is not False:
        raise ValueError("P4C diagnostic trajectory unexpectedly became satisfiable")
    if negative["superseded_constraint_ids"]:
        raise ValueError("P4C diagnostic trajectory superseded an unverified fact")
    if positive.get("runtime_execution_contract") != EXPECTED_CONTRACT:
        raise ValueError("P4C runtime execution contract changed")
    if positive["execution"] != {
        "actions_executed": 2,
        "actions_failed": 0,
        "actions_succeeded": 2,
        "goal_status": "satisfied",
        "snapshot_hash": positive["artifact"]["snapshot_hash"],
        "stop_reason": "typed repair verified",
    }:
        raise ValueError("Unexpected P4C positive execution result")
    if positive["post_state"] != {
        "conflicts": [],
        "managed_constraints": 2,
        "provisional_constraints": [],
        "satisfiable": True,
        "statuses": {
            "constraint-runtime-06d6189fa3d42d1f": "satisfied",
            "constraint-runtime-5c1dbf41085db040": "satisfied",
        },
    }:
        raise ValueError("Unexpected P4C post-repair state")
    if positive["superseded_constraint_ids"] != [
        "constraint-runtime-0e500c0b8ce1c1f2"
    ]:
        raise ValueError("P4C did not supersede exactly the contradicted runtime fact")
    negative_artifact = _artifact(root, negative, 25)
    positive_artifact = _artifact(root, positive, 27)
    verifications = positive_artifact.pop("snapshot_verifications")
    if len(verifications) != 1 or verifications[0].get("passed") is not True:
        raise ValueError("P4C positive artifact lacks its passing V1 verification")
    negative_verifications = negative_artifact.pop("snapshot_verifications")
    if (
        len(negative_verifications) != 1
        or negative_verifications[0].get("passed") is not False
    ):
        raise ValueError("P4C negative artifact lacks its failed verification")
    return {
        "negative": {
            "path": str(NEGATIVE_PATH),
            "sha256": _sha256(negative_path),
            "execution": negative["execution"],
            "post_state": negative["post_state"],
            "artifact": negative_artifact,
        },
        "positive": {
            "path": str(POSITIVE_PATH),
            "sha256": _sha256(positive_path),
            "execution": positive["execution"],
            "post_state": positive["post_state"],
            "artifact": positive_artifact,
            "runtime_execution_contract": positive["runtime_execution_contract"],
        },
        "shared": {
            "repository": positive["repository"],
            "revision": positive["revision"],
            "image": positive["image"],
            "lineage": positive["lineage"],
            "plan": positive["plan"],
            "commands": positive["commands"],
            "isolation": positive["isolation"],
            "integrity": positive["integrity"],
        },
    }


def build_freeze(root: Path, created_at: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "created_at": created_at,
        "source_files": _file_map(root, SOURCE_PATHS),
        "validation": {
            "p4c_synthetic_tests": 6,
            "p4b_regression_tests": 11,
            "p4a_regression_tests": 13,
            "p3_regression_tests": 17,
            "p2_regression_tests": 7,
            "p0_regression_tests": 44,
            "compile_check": True,
            "runtime_transition": _validation(root),
        },
        "scope": {
            "p0_scoring_changed": False,
            "p2_semantics_changed": False,
            "p3_semantics_changed": False,
            "p4a_semantics_changed": False,
            "p4b_semantics_changed": False,
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "new_benchmark_cases": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "repository_specific_rules": False,
            "p4_complete": False,
        },
        "change_policy": (
            "Any image-lineage gate, transfer-selection rule, target evidence "
            "identity, runtime execution contract, validation command, or "
            "verification-gated transition change requires a new P4C freeze."
        ),
    }


def verify_freeze(root: Path, freeze: dict) -> list[str]:
    errors: list[str] = []
    if freeze.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema version mismatch")
    if freeze.get("policy_id") != POLICY_ID:
        errors.append("policy identifier mismatch")
    try:
        current_files = _file_map(root, SOURCE_PATHS)
    except FileNotFoundError as exc:
        errors.append(str(exc))
        current_files = {}
    if freeze.get("source_files") != current_files:
        errors.append("P4C source file set or content changed")
    try:
        current_validation = _validation(root)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"P4C validation failed: {type(exc).__name__}: {exc}")
        current_validation = None
    expected = freeze.get("validation", {}).get("runtime_transition")
    if current_validation is not None and expected != current_validation:
        errors.append("P4C runtime transition validation changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the P4C context-transfer freeze."
    )
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=WORKSPACE_ROOT / OUTPUT_PATH)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.verify:
        freeze = json.loads(output.read_text(encoding="utf-8"))
        errors = verify_freeze(WORKSPACE_ROOT, freeze)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    freeze = build_freeze(WORKSPACE_ROOT, datetime.now(timezone.utc).isoformat())
    output.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
