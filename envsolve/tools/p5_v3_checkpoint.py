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

from envsolve.tools.run_p5_v3_dev5 import load_preregistration


FILES = (
    "envsolve/verification/hierarchy.py",
    "envsolve/verification/imports.py",
    "envsolve/verification/smoke.py",
    "envsolve/verification/installed_metadata.py",
    "envsolve/tools/run_p5_v3_in_container.py",
    "envsolve/tools/run_p5_v3_dev5.py",
    "envsolve/tests/test_hierarchical_verifier.py",
    "envsolve/tests/test_import_verifier.py",
    "envsolve/tests/test_installed_metadata.py",
    "envsolve/tests/test_smoke_verifier.py",
    "envsolve/tests/test_v3_container_tool.py",
    "experiments/validations/p5_round9_git_checkout_dev5_preregistration.json",
    "experiments/validations/p5_round9_git_checkout_dev5_results.json",
    "experiments/validations/p5_round9_git_checkout_dev5_analysis.json",
)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, Any]:
    prereg_path = ROOT / "experiments/validations/p5_round9_git_checkout_dev5_preregistration.json"
    result_path = ROOT / "experiments/validations/p5_round9_git_checkout_dev5_results.json"
    analysis_path = ROOT / "experiments/validations/p5_round9_git_checkout_dev5_analysis.json"
    prereg = load_preregistration(prereg_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    if result["preregistration"]["sha256"] != sha_file(prereg_path):
        raise ValueError("result preregistration hash mismatch")
    if analysis["source_result"]["sha256"] != sha_file(result_path):
        raise ValueError("analysis result hash mismatch")
    expected = {(item["repository"], item["revision"]) for item in prereg["targets"]}
    observed = {(item["repository"], item["revision"]) for item in result["cases"]}
    if expected != observed or len(result["cases"]) != len(expected):
        raise ValueError("Round 9 target identity mismatch")

    probes = 0
    provenance = Counter()
    metadata_sources = Counter()
    for case in result["cases"]:
        if case["source"]["source_materialization"] != "detached_git_checkout":
            raise ValueError("source is not a detached Git checkout")
        if case["source"]["head"] != case["revision"]:
            raise ValueError("source HEAD mismatch")
        if case["source"]["pre_bootstrap_status_sha256"] != EMPTY_SHA256:
            raise ValueError("source was dirty before bootstrap")
        if case["bootstrap"]["exit_code"] != 0 or case["container"]["exit_code"] != 0:
            raise ValueError("bootstrap or container failed")
        if not case["container"]["networks_before_disconnect"]:
            raise ValueError("missing pre-disconnect network evidence")
        if case["container"]["networks_after_disconnect"]:
            raise ValueError("V3 container retained a Docker network")
        v3 = case["v3"]
        if v3 is None or v3["decision"]["passed"] is not True:
            raise ValueError("V3 did not pass")
        if v3.get("collection_errors"):
            raise ValueError("V3 metadata collection error")
        for distribution in v3["distributions"]:
            if distribution["decision"]["passed"] is not True:
                raise ValueError("distribution V3 did not pass")
            provenance[distribution["provenance"]["kind"]] += 1
            metadata_sources[distribution["metadata_source"]] += 1
            if len(distribution["provenance"]["sha256"]) != 64:
                raise ValueError("invalid provenance hash")
            if len(distribution["snapshot"]["metadata_sha256"]) != 64:
                raise ValueError("invalid metadata hash")
            for outcome in distribution["outcomes"]:
                probes += 1
                if outcome["exit_code"] != 0 or outcome["timed_out"]:
                    raise ValueError("V3 probe failed")
    if probes != 24:
        raise ValueError(f"unexpected V3 probe count: {probes}")
    if provenance != Counter({"pep610-direct-url": 3, "legacy-egg-link": 2}):
        raise ValueError("unexpected provenance distribution")
    if metadata_sources != Counter({"METADATA": 3, "PKG-INFO": 2}):
        raise ValueError("unexpected metadata-source distribution")
    if result["aggregate"] != {
        "cases": 5,
        "bootstrap_pass": 5,
        "v3_pass": 5,
        "v3_fail": 0,
        "v3_unknown": 0,
    }:
        raise ValueError("Round 9 aggregate mismatch")
    for value in result["implementation"].values():
        if sha_file(ROOT / value["path"]) != value["sha256"]:
            raise ValueError(f"implementation hash mismatch: {value['path']}")
    return {
        "checkpoint_id": "p5-v3-dev5-checkpoint-v1",
        "scope": "development-only V3 checkpoint; not P5 freeze or Robust Pass",
        "files": {path: sha_file(ROOT / path) for path in FILES},
        "result": {
            "cases": 5,
            "bootstrap_pass": 5,
            "v3_pass": 5,
            "semantic_probes": probes,
            "probe_failures": 0,
            "provenance": dict(sorted(provenance.items())),
            "metadata_sources": dict(sorted(metadata_sources.items())),
        },
        "integrity": {
            "official_verifier_executions": 0,
            "official_results_modified": False,
            "canary20_inspected": False,
            "official_test100_inspected": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the P5 V3 checkpoint.")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "envsolve/protocols/p5_v3_dev5_checkpoint_v1.json",
    )
    args = parser.parse_args()
    current = build()
    output = args.output.resolve()
    if args.verify:
        expected = json.loads(output.read_text(encoding="utf-8"))
        errors = [] if expected == current else ["P5 V3 checkpoint content mismatch"]
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    output.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
