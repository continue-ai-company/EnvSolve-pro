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

from envsolve.analysis.discovery import observable_outcome, paired_aggregate
from envsolve.analysis.trajectory import analyze_trajectory_file
from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, write_json


PREREGISTRATION = (
    ROOT / "experiments/validations/envsolve_v0_discovery5_round1_preregistration.json"
)
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trajectory_analysis(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return analyze_trajectory_file(path)
    except (OSError, TypeError, ValueError) as exc:
        return {
            "path": str(path),
            "sha256": sha256_file(path),
            "analysis_error": f"{type(exc).__name__}: {exc}",
        }


def condition_records(run_root: Path, condition: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for manifest_path in sorted(run_root.glob("*/manifest.json")):
        case_root = manifest_path.parent
        manifest = read_json(manifest_path)
        solver = manifest.get("solver") or {}
        evaluation = manifest.get("result")
        trajectory_path = case_root / "generation/trajectory.jsonl"
        trajectory = trajectory_analysis(trajectory_path)
        records.append(
            {
                "case_id": manifest["case"]["case_id"],
                "repository": manifest["case"]["repository"],
                "revision": manifest["case"]["revision"],
                "condition": condition,
                "generation_completed": solver.get("generation_completed"),
                "generation_error": solver.get("error"),
                "evaluation_completed": (
                    evaluation.get("evaluation_completed")
                    if isinstance(evaluation, dict)
                    else None
                ),
                "official_pass": (
                    evaluation.get("official_pass")
                    if isinstance(evaluation, dict)
                    else None
                ),
                "raw_metrics": (
                    evaluation.get("raw_metrics", {})
                    if isinstance(evaluation, dict)
                    else {}
                ),
                "v0_completion": (solver.get("metadata") or {}).get("v0_completion"),
                "observable_outcome": observable_outcome(solver, evaluation),
                "trajectory": trajectory,
                "audit": audit_run(case_root).to_dict(),
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=PREREGISTRATION)
    parser.add_argument("--v0-run-root", type=Path)
    parser.add_argument("--freeagent-run-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    preregistration_path = args.preregistration.resolve()
    preregistration = read_json(preregistration_path)
    artifacts = preregistration["frozen_artifacts"]
    expected_sources = {
        artifacts["case_file"]["path"]: artifacts["case_file"]["sha256"],
        **artifacts["method_sources"],
        **artifacts.get("execution_sources", {}),
        **artifacts["analysis_sources"],
    }
    mismatches = {
        relative: {"expected": expected, "actual": sha256_file(ROOT / relative)}
        for relative, expected in expected_sources.items()
        if sha256_file(ROOT / relative) != expected
    }
    if mismatches:
        raise RuntimeError(f"Frozen discovery analysis source mismatch: {mismatches}")
    execution = preregistration["execution"]
    run_ids = execution["run_ids"]
    v0_run_root = args.v0_run_root or ROOT / "runs" / run_ids["envsolve_v0"]
    freeagent_run_root = (
        args.freeagent_run_root or ROOT / "runs" / run_ids["freeagent"]
    )
    output = args.output or ROOT / execution["analysis_output"]
    expected_ids = {
        item["case_id"] for item in preregistration["selection"]["selected"]
    }
    records = condition_records(v0_run_root.resolve(), "envsolve_v0")
    records.extend(condition_records(freeagent_run_root.resolve(), "freeagent"))
    observed = {item["case_id"] for item in records}
    if observed != expected_ids or len(records) != 2 * len(expected_ids):
        raise RuntimeError(
            f"Discovery analysis requires all ten frozen attempts; observed={sorted(observed)}"
        )
    result = {
        "schema_version": "1.0.0",
        "analysis_id": f"{preregistration['preregistration_id']}-observable-analysis",
        "preregistration": {
            "path": str(preregistration_path.relative_to(ROOT)),
            "sha256": sha256_file(preregistration_path),
        },
        "aggregate": paired_aggregate(records),
        "records": records,
        "interpretation_boundary": {
            "root_causes_assigned": False,
            "infrastructure_unknown_inferred_from_exit_code": False,
            "mechanism_selected": False,
            "mechanism_admission_rule": preregistration["analysis_policy"][
                "mechanism_admission"
            ],
        },
    }
    write_json(output.resolve(), result)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
