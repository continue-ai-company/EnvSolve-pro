#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.analysis.runtime_compatibility import parse_runtime_compatibility
from envsolve.constraints import build_causal_constraint_frontier
from envsolve.state import EventStore
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qualify a causal constraint frontier on consumed trajectories."
    )
    parser.add_argument("--run-root", type=Path, action="append", required=True)
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _raw_runtime_findings(
    case_root: Path,
    state: Any,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    artifact_root = case_root / "generation" / "raw-artifacts"
    for action in state.actions.values():
        observation = action.get("observation")
        if not isinstance(observation, dict):
            continue
        for channel in ("stdout", "stderr"):
            artifact = observation.get(f"{channel}_artifact")
            relative = artifact.get("path") if isinstance(artifact, dict) else None
            expected_hash = artifact.get("sha256") if isinstance(artifact, dict) else None
            if not isinstance(relative, str) or not isinstance(expected_hash, str):
                continue
            path = artifact_root / relative
            try:
                path.resolve().relative_to(artifact_root.resolve())
            except ValueError:
                continue
            if not path.is_file() or sha256_file(path) != expected_hash:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for finding in parse_runtime_compatibility(text):
                findings.append(
                    {
                        "candidate_id": action.get("action_id"),
                        "channel": channel,
                        "artifact_path": str(path.relative_to(case_root)),
                        "artifact_sha256": expected_hash,
                        "finding": finding.to_dict(),
                    }
                )
    return findings


def analyze_case(case_root: Path) -> dict[str, Any]:
    manifest = read_json(case_root / "manifest.json")
    case = manifest.get("case") or {}
    case_id = str(case["case_id"])
    trajectory = case_root / "generation" / "episode.jsonl"
    state = EventStore(trajectory, case_id).reconstruct()
    frontier = build_causal_constraint_frontier(state)
    return {
        "case_id": case_id,
        "repository": case.get("repository"),
        "revision": case.get("revision"),
        "artifact_root": str(case_root.resolve()),
        "trajectory_sha256": sha256_file(trajectory),
        "frontier": frontier,
        "historical_raw_runtime_compatibility_findings": _raw_runtime_findings(
            case_root,
            state,
        ),
    }


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = [case["frontier"]["summary"] for case in cases]
    roots = [
        root
        for case in cases
        for root in case["frontier"]["causal_roots"]
    ]
    module_roots = [
        root for root in roots if root.get("root_kind") == "runtime_missing_dependency"
    ]
    grouped = sum(
        int(summary["causally_grouped_surface_constraint_count"])
        for summary in summaries
    )
    raw_runtime_findings = sum(
        len(case["historical_raw_runtime_compatibility_findings"])
        for case in cases
    )
    return {
        "case_count": len(cases),
        "causal_root_count": len(roots),
        "module_causal_root_count": len(module_roots),
        "surface_module_obligation_count": sum(
            int(summary["surface_module_obligation_count"])
            for summary in summaries
        ),
        "causally_grouped_surface_constraint_count": grouped,
        "grouped_surface_constraints_per_module_root": (
            grouped / len(module_roots) if module_roots else None
        ),
        "maximum_surface_amplification": max(
            (
                int(summary["maximum_surface_amplification"])
                for summary in summaries
            ),
            default=0,
        ),
        "cases_with_surface_amplification": sum(
            int(summary["maximum_surface_amplification"]) > 1
            for summary in summaries
        ),
        "historical_raw_runtime_compatibility_findings": raw_runtime_findings,
    }


def main() -> int:
    args = parse_args()
    case_roots: dict[str, Path] = {}
    for run_root in args.run_root:
        for manifest_path in sorted(run_root.resolve().glob("*/manifest.json")):
            manifest = read_json(manifest_path)
            case = manifest.get("case") or {}
            case_id = case.get("case_id")
            trajectory = manifest_path.parent / "generation" / "episode.jsonl"
            if isinstance(case_id, str) and case_id and trajectory.is_file():
                case_roots[case_id] = manifest_path.parent
    cases = [analyze_case(case_roots[key]) for key in sorted(case_roots)]
    payload = {
        "schema_version": "1.0.0",
        "study_id": args.study_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "Consumed trajectory mechanism qualification only.",
        "run_roots": [str(path.resolve()) for path in args.run_root],
        "aggregate": aggregate(cases),
        "cases": cases,
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
