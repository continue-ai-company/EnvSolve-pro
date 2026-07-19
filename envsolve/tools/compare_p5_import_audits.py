#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finding_key(value: dict[str, Any]) -> tuple[str, int, str]:
    return value["file"], int(value["line"]), value["module"]


def case_map(value: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (item["repository"], item["revision"]): item
        for item in value["cases"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two P5 import audits.")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    baseline_path = args.baseline.resolve()
    candidate_path = args.candidate.resolve()
    preregistration_path = args.preregistration.resolve()
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    preregistration = json.loads(preregistration_path.read_text(encoding="utf-8"))

    baseline_cases = case_map(baseline)
    candidate_cases = case_map(candidate)
    identities_unchanged = baseline_cases.keys() == candidate_cases.keys()
    changes = []
    finding_identities_unchanged = identities_unchanged
    official_results_unchanged = identities_unchanged
    for identity in sorted(baseline_cases.keys() | candidate_cases.keys()):
        before = baseline_cases.get(identity)
        after = candidate_cases.get(identity)
        if before is None or after is None:
            finding_identities_unchanged = False
            official_results_unchanged = False
            continue
        official_results_unchanged &= before["official"] == after["official"]
        before_findings = {finding_key(item): item for item in before["assessments"]}
        after_findings = {finding_key(item): item for item in after["assessments"]}
        finding_identities_unchanged &= before_findings.keys() == after_findings.keys()
        for key in sorted(before_findings.keys() | after_findings.keys()):
            old = before_findings.get(key)
            new = after_findings.get(key)
            if old is None or new is None or old == new:
                continue
            changes.append(
                {
                    "repository": identity[0],
                    "revision": identity[1],
                    "file": key[0],
                    "line": key[1],
                    "module": key[2],
                    "before": {
                        "disposition": old["disposition"],
                        "active_repair_obligation": old["active_repair_obligation"],
                        "evidence": old["evidence"],
                    },
                    "after": {
                        "disposition": new["disposition"],
                        "active_repair_obligation": new["active_repair_obligation"],
                        "evidence": new["evidence"],
                    },
                }
            )

    allowed_transition_only = all(
        item["before"]["disposition"] == "inactive_platform"
        and item["after"]["disposition"] == "active_obligation"
        and any(
            evidence["kind"] == "inactive-branch"
            for evidence in item["before"]["evidence"]
        )
        and not any(
            evidence["kind"] == "inactive-branch"
            for evidence in item["after"]["evidence"]
        )
        for item in changes
    )
    result = {
        "validation_id": "p5-import-audit-round-difference-v1",
        "inputs": {
            "baseline": {"path": str(baseline_path.relative_to(ROOT)), "sha256": sha_file(baseline_path)},
            "candidate": {"path": str(candidate_path.relative_to(ROOT)), "sha256": sha_file(candidate_path)},
            "preregistration": {
                "path": str(preregistration_path.relative_to(ROOT)),
                "sha256": sha_file(preregistration_path),
                "id": preregistration["preregistration_id"],
            },
        },
        "checks": {
            "case_identities_unchanged": identities_unchanged,
            "finding_identities_unchanged": finding_identities_unchanged,
            "official_results_unchanged": official_results_unchanged,
            "allowed_transition_only": allowed_transition_only,
            "all_passed": all(
                (
                    identities_unchanged,
                    finding_identities_unchanged,
                    official_results_unchanged,
                    allowed_transition_only,
                )
            ),
        },
        "aggregate": {
            "changed_findings": len(changes),
            "active_repair_obligations_before": baseline["aggregate"]["active_repair_obligations"],
            "active_repair_obligations_after": candidate["aggregate"]["active_repair_obligations"],
        },
        "changes": changes,
    }
    args.output.resolve().write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output.resolve())
    return 0 if result["checks"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
