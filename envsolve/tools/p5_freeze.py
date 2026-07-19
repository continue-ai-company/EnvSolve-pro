#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.verification.hierarchy import VerificationLevel, build_report
from envsolve.verification.replay_equivalence import snapshot_from_artifact


ARTIFACTS = {
    "v0_v3": "experiments/validations/p5_round11_v3_dev5_results.json",
    "v1": "experiments/validations/p5_round13_v1_dev5_results.json",
    "v2_baseline": "experiments/validations/p4e_dev5_scope_audit.json",
    "v2_inflect": "experiments/validations/p4e_round2_retry_results.json",
    "v4": "experiments/validations/p5_round14_v4_dev5_results.json",
    "v6_preregistration": "experiments/validations/p5_round16_v6_dev5_preregistration.json",
    "v6": "experiments/validations/p5_round16_v6_dev5_results.json",
    "v6_analysis": "experiments/validations/p5_round16_v6_dev5_analysis.json",
}

SOURCE_FILES = (
    "envsolve/tools/p5_freeze.py",
    "envsolve/tools/run_p5_v1_in_container.py",
    "envsolve/tools/run_p5_v3_dev5.py",
    "envsolve/tools/run_p5_v3_in_container.py",
    "envsolve/tools/run_p5_v4_in_container.py",
    "envsolve/tools/run_p5_v6_dev5.py",
    "envsolve/tools/run_p5_v6_in_container.py",
    "envsolve/verification/environment_state.py",
    "envsolve/verification/hierarchy.py",
    "envsolve/verification/imports.py",
    "envsolve/verification/installed_metadata.py",
    "envsolve/verification/metadata_consistency.py",
    "envsolve/verification/native_project.py",
    "envsolve/verification/network_isolation.py",
    "envsolve/verification/project_provenance.py",
    "envsolve/verification/replay_equivalence.py",
    "envsolve/verification/smoke.py",
    "envsolve/tests/test_hierarchical_verifier.py",
    "envsolve/tests/test_import_verifier.py",
    "envsolve/tests/test_installed_metadata.py",
    "envsolve/tests/test_metadata_consistency.py",
    "envsolve/tests/test_native_project.py",
    "envsolve/tests/test_replay_equivalence.py",
    "envsolve/tests/test_smoke_verifier.py",
    "envsolve/tests/test_v1_container_tool.py",
    "envsolve/tests/test_v3_container_tool.py",
    "envsolve/tests/test_v6_runner.py",
    "envsolve/tests/test_p5_freeze.py",
    "research/P5_HIERARCHICAL_VERIFIER_PROTOCOL.md",
    "research/P5_HIERARCHICAL_VERIFIER_PROTOCOL_ZH.md",
    "research/P5_ROUND16_V6_RESULTS.md",
    "research/P5_ROUND16_V6_RESULTS_ZH.md",
) + tuple(ARTIFACTS.values())


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: str) -> dict[str, Any]:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"artifact is not an object: {path}")
    return value


def _case_map(artifact: dict[str, Any], field: str = "cases") -> dict[str, dict[str, Any]]:
    cases = artifact.get(field)
    if not isinstance(cases, list):
        raise ValueError(f"artifact has no case list: {field}")
    mapped = {str(item["repository"]): item for item in cases}
    if len(mapped) != len(cases):
        raise ValueError("duplicate repository in evidence")
    return mapped


def _decision(value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("verifier evidence must be an object or null")
    decision = value.get("decision")
    if not isinstance(decision, dict) or decision.get("passed") not in (True, False, None):
        raise ValueError("verifier decision is malformed")
    return decision["passed"]


def _v2_decisions(
    baseline: dict[str, Any], inflect: dict[str, Any]
) -> dict[str, bool]:
    outcomes = baseline.get("outcomes")
    if not isinstance(outcomes, list):
        raise ValueError("V2 baseline outcomes are missing")
    decisions = {
        str(item["repository"]): item["terminal_class"] == "official_pass"
        for item in outcomes
    }
    target = inflect["target"]
    outcome = inflect["outcome"]
    if outcome.get("terminal_class") != "official_pass" or not outcome.get("repair_verified"):
        raise ValueError("final Inflect V2 repair is not verified")
    decisions[str(target["repository"])] = True
    return decisions


def _audit_v6(
    preregistration: dict[str, Any],
    result: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, set[str]]:
    prereg_path = ROOT / ARTIFACTS["v6_preregistration"]
    result_path = ROOT / ARTIFACTS["v6"]
    if result["preregistration"]["sha256"] != sha_file(prereg_path):
        raise ValueError("V6 result preregistration hash mismatch")
    if analysis["result"]["sha256"] != sha_file(result_path):
        raise ValueError("V6 analysis result hash mismatch")
    for item in preregistration["frozen_policy_sources"].values():
        if sha_file(ROOT / item["path"]) != item["sha256"]:
            raise ValueError(f"frozen V6 source changed: {item['path']}")

    provenance: dict[str, set[str]] = {}
    for case in result["cases"]:
        snapshots = []
        kinds: set[str] = set()
        for replay_name in ("replay_a", "replay_b"):
            replay_ref = case[replay_name]
            raw_path = ROOT / replay_ref["result"]["path"]
            if sha_file(raw_path) != replay_ref["result"]["sha256"]:
                raise ValueError("V6 raw replay hash mismatch")
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            if raw["container"]["id"] != replay_ref["container_id"]:
                raise ValueError("V6 container identity mismatch")
            artifact = raw.get("v6")
            snapshot_value = artifact.get("snapshot") if isinstance(artifact, dict) else None
            if snapshot_value is None:
                snapshots.append(None)
                continue
            if raw["container"]["networks_after_disconnect"] != []:
                raise ValueError("V6 host network isolation failed")
            if artifact.get("network") != {
                "host_disconnect_marker": True,
                "default_route_present": False,
            }:
                raise ValueError("V6 container network isolation failed")
            snapshot = snapshot_from_artifact(snapshot_value)
            snapshots.append(snapshot.sha256)
            kinds.update(item.provenance_kind for item in snapshot.project_distributions)
        if case["replay_a"]["container_id"] == case["replay_b"]["container_id"]:
            raise ValueError("V6 replay reused a container")
        passed = case["decision"]["passed"]
        if passed is True and (None in snapshots or snapshots[0] != snapshots[1]):
            raise ValueError("V6 Pass is not backed by equal complete snapshots")
        if passed is False and (None in snapshots or snapshots[0] == snapshots[1]):
            raise ValueError("V6 Fail is not backed by state drift")
        if passed is None and None not in snapshots:
            raise ValueError("V6 Unknown has two complete snapshots")
        provenance[str(case["repository"])] = kinds
    return provenance


def _level_counts(matrix: list[dict[str, Any]], level: str) -> dict[str, int]:
    values = [item["levels"][level] for item in matrix]
    return {
        "pass": sum(value is True for value in values),
        "fail": sum(value is False for value in values),
        "unknown": sum(value is None for value in values),
    }


def build() -> dict[str, Any]:
    artifacts = {name: read_json(path) for name, path in ARTIFACTS.items()}
    v0_v3 = _case_map(artifacts["v0_v3"])
    v1 = _case_map(artifacts["v1"])
    v4 = _case_map(artifacts["v4"])
    v6 = _case_map(artifacts["v6"])
    repositories = set(v0_v3)
    if len(repositories) != 5 or any(set(value) != repositories for value in (v1, v4, v6)):
        raise ValueError("P5 evidence target sets differ")
    v2 = _v2_decisions(artifacts["v2_baseline"], artifacts["v2_inflect"])
    if set(v2) != repositories:
        raise ValueError("V2 target set differs from P5 evidence")
    provenance = _audit_v6(
        artifacts["v6_preregistration"], artifacts["v6"], artifacts["v6_analysis"]
    )

    matrix = []
    for repository in sorted(repositories):
        levels = {
            "V0": v0_v3[repository]["bootstrap"]["exit_code"] == 0,
            "V1": _decision(v1[repository].get("v1")),
            "V2": v2[repository],
            "V3": _decision(v0_v3[repository].get("v3")),
            "V4": _decision(v4[repository].get("v4")),
            "V5": None,
            "V6": v6[repository]["decision"]["passed"],
        }
        report = build_report(
            tuple(
                VerificationLevel(level, levels[level], f"p5-{level.lower()}", ARTIFACTS[key])
                for level, key in (
                    ("V0", "v0_v3"),
                    ("V1", "v1"),
                    ("V2", "v2_baseline"),
                    ("V3", "v0_v3"),
                    ("V4", "v4"),
                    ("V6", "v6"),
                )
            )
        )
        matrix.append(
            {
                "repository": repository,
                "revision": v0_v3[repository]["revision"],
                "levels": levels,
                "official_pass": report.official_pass,
                "robust_pass": report.robust_pass,
                "native_pass": report.native_pass,
                "v6_project_provenance": sorted(provenance[repository]),
            }
        )

    level_counts = {level: _level_counts(matrix, level) for level in (f"V{i}" for i in range(7))}
    clean_replay_provenance = Counter(
        kind
        for item in matrix
        if item["levels"]["V6"] is True
        for kind in item["v6_project_provenance"]
    )
    v2_only_blocked = sum(
        item["levels"]["V2"] is False
        and all(item["levels"][level] is True for level in ("V0", "V1", "V3", "V4", "V6"))
        for item in matrix
    )
    if level_counts != {
        "V0": {"pass": 5, "fail": 0, "unknown": 0},
        "V1": {"pass": 4, "fail": 0, "unknown": 1},
        "V2": {"pass": 2, "fail": 3, "unknown": 0},
        "V3": {"pass": 5, "fail": 0, "unknown": 0},
        "V4": {"pass": 5, "fail": 0, "unknown": 0},
        "V5": {"pass": 0, "fail": 0, "unknown": 5},
        "V6": {"pass": 4, "fail": 0, "unknown": 1},
    }:
        raise ValueError("unexpected P5 pass curve")
    if clean_replay_provenance != Counter(
        {"pep610-direct-url": 3, "legacy-egg-link": 1}
    ):
        raise ValueError("clean replay does not cover expected provenance classes")

    return {
        "policy_id": "envsolve-p5-hierarchical-verifier-v1",
        "schema_version": "1.0.0",
        "change_policy": (
            "Any verifier level semantic, pass aggregation, evidence collector, "
            "snapshot normalization, or replay decision change requires a new P5 version."
        ),
        "scope": {
            "development_only": True,
            "p5_complete": True,
            "completion_basis": (
                "The hierarchical verifier fails closed, separates Official from Robust "
                "Pass, and has prospective real V1/V3/V4/V6 evidence including exact "
                "fresh-container replay under modern and legacy provenance."
            ),
            "unknowns_retained": 2,
            "unknown_cases_are_not_tuning_obligations": True,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "repository_specific_verifier_rules": False,
        },
        "artifacts": {
            name: {"path": path, "sha256": sha_file(ROOT / path)}
            for name, path in ARTIFACTS.items()
        },
        "source_files": {path: sha_file(ROOT / path) for path in SOURCE_FILES},
        "validation": {
            "cases": len(matrix),
            "level_counts": level_counts,
            "official_pass": sum(item["official_pass"] for item in matrix),
            "robust_pass": sum(item["robust_pass"] for item in matrix),
            "native_pass": None,
            "v2_only_blocked_with_all_other_robust_levels_passed": v2_only_blocked,
            "clean_replay_provenance": dict(sorted(clean_replay_provenance.items())),
            "matrix": matrix,
            "full_suite_tests": 206,
            "compile_check": True,
        },
        "integrity": {
            "model_requests_for_freeze": 0,
            "official_verifier_executions_for_freeze": 0,
            "heldout_cases_inspected": 0,
            "official_results_modified": False,
            "development_unknown_promoted_to_pass": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the P5 freeze manifest.")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "envsolve/protocols/p5_hierarchical_verifier_freeze_v1.json",
    )
    args = parser.parse_args()
    current = build()
    output = args.output.resolve()
    if args.verify:
        expected = json.loads(output.read_text(encoding="utf-8"))
        valid = expected == current
        print(json.dumps({"valid": valid, "errors": [] if valid else ["P5 freeze content mismatch"]}, indent=2))
        return 0 if valid else 1
    output.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
