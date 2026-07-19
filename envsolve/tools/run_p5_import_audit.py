#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.verification.imports import (
    EnvironmentFacts,
    ImportContextAnalyzer,
    ImportDisposition,
    MissingImportFinding,
    exclusion_rules_from_pyproject,
)


MODULE_PATTERN = re.compile(r'^Import "([^"]+)" could not be resolved$')


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def git_blob(root: Path, revision: str, path: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{path}"],
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise FileNotFoundError(f"cannot read {revision}:{path}: {detail}")
    return process.stdout


def parse_toml(value: bytes) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    parsed = tomllib.loads(value.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def load_exclusions(root: Path, revision: str) -> tuple[tuple, dict[str, str]]:
    try:
        content = git_blob(root, revision, "pyproject.toml")
    except FileNotFoundError:
        return (), {}
    digest = sha_bytes(content)
    return exclusion_rules_from_pyproject(parse_toml(content), digest), {
        "pyproject.toml": digest
    }


def relative_file(value: str) -> str:
    prefix = "/data/project/"
    return value[len(prefix) :] if value.startswith(prefix) else value.lstrip("/")


def audit_target(target: dict[str, Any], facts: EnvironmentFacts) -> dict[str, Any]:
    raw_path = ROOT / target["raw_result"]["path"]
    if sha_file(raw_path) != target["raw_result"]["sha256"]:
        raise ValueError(f"raw result hash mismatch: {raw_path}")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw["repo_name"] != target["repository"] or raw["commit_sha"] != target["revision"]:
        raise ValueError("target identity does not match raw result")
    git_root = ROOT / target["git_object_root"]
    exclusions, config_hashes = load_exclusions(git_root, target["revision"])
    analyzer = ImportContextAnalyzer()
    assessments = []
    blob_hashes: dict[str, str] = {}
    diagnostics = [
        item
        for item in raw.get("pyright", {}).get("generalDiagnostics", [])
        if item.get("rule") == "reportMissingImports"
    ]
    if len(diagnostics) != target["expected_findings"]:
        raise ValueError("finding cardinality changed")
    for diagnostic in diagnostics:
        match = MODULE_PATTERN.fullmatch(str(diagnostic.get("message", "")))
        if match is None:
            raise ValueError(f"unsupported missing-import diagnostic: {diagnostic}")
        path = relative_file(str(diagnostic["file"]))
        line = int(diagnostic["range"]["start"]["line"])
        finding = MissingImportFinding(match.group(1), path, line, diagnostic["message"])
        try:
            source_bytes = git_blob(git_root, target["revision"], path)
            source = source_bytes.decode("utf-8")
            blob_hashes[path] = sha_bytes(source_bytes)
            assessment = analyzer.assess(finding, source, facts, exclusions)
            source_error = None
        except (FileNotFoundError, UnicodeDecodeError) as exc:
            assessment = analyzer.assess(finding, "", facts, exclusions)
            source_error = f"{type(exc).__name__}: {exc}"
        assessments.append(
            {
                "module": finding.module,
                "file": finding.file,
                "line": finding.line,
                "role": assessment.role.value,
                "disposition": assessment.disposition.value,
                "active_repair_obligation": assessment.active_repair_obligation,
                "evidence": [item.__dict__ for item in assessment.evidence],
                "source_error": source_error,
            }
        )
    dispositions = Counter(item["disposition"] for item in assessments)
    roles = Counter(item["role"] for item in assessments)
    return {
        "repository": target["repository"],
        "revision": target["revision"],
        "official": {
            "exit_code": raw["exit_code"],
            "issues_count": raw["issues_count"],
            "official_pass": raw["exit_code"] == 0 and raw["issues_count"] == 0,
        },
        "assessment_summary": {
            "findings": len(assessments),
            "active_repair_obligations": sum(
                1 for item in assessments if item["active_repair_obligation"]
            ),
            "dispositions": dict(sorted(dispositions.items())),
            "roles": dict(sorted(roles.items())),
        },
        "project_config_hashes": config_hashes,
        "exclusion_rules": [item.__dict__ for item in exclusions],
        "source_blob_hashes": dict(sorted(blob_hashes.items())),
        "assessments": assessments,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the preregistered P5 import audit.")
    parser.add_argument(
        "--preregistration",
        type=Path,
        default=ROOT / "experiments/validations/p5_round1_preregistration.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/validations/p5_round1_import_audit_results.json",
    )
    args = parser.parse_args()
    prereg_path = args.preregistration.resolve()
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    facts_value = prereg["environment_facts"]
    facts = EnvironmentFacts(
        sys_platform=facts_value["sys_platform"],
        python_major=int(facts_value["python_major"]),
        platform_name=facts_value["platform_name"],
    )
    cases = [audit_target(target, facts) for target in prereg["targets"]]
    result = {
        "validation_id": prereg["preregistration_id"],
        "preregistration": {
            "path": str(prereg_path.relative_to(ROOT)),
            "sha256": sha_file(prereg_path),
        },
        "environment_facts": facts_value,
        "cases": cases,
        "aggregate": {
            "cases": len(cases),
            "findings": sum(item["assessment_summary"]["findings"] for item in cases),
            "active_repair_obligations": sum(
                item["assessment_summary"]["active_repair_obligations"] for item in cases
            ),
            "official_pass": sum(1 for item in cases if item["official"]["official_pass"]),
        },
        "integrity": {
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "network_requests": 0,
            "repository_mutations": 0,
            "source_mode": "git-object",
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "official_score_modified": False,
        },
    }
    args.output.resolve().write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
