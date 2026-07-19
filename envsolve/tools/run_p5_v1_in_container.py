#!/usr/bin/env python3
from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable

from packaging.markers import default_environment


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.verification.environment_state import (
    collect_installed_observations,
    collect_project_evidence,
)
from envsolve.verification.metadata_consistency import (
    ConsistencyIssue,
    MetadataConsistencyDecision,
    ProjectMetadataEvidence,
    ResolverCheck,
    evaluate_metadata_consistency,
)
from envsolve.verification.network_isolation import default_route_present
from envsolve.verification.project_provenance import find_project_distributions, sha_bytes


def execute_resolver_check(
    workdir: Path,
    timeout_seconds: int = 30,
) -> tuple[ResolverCheck, dict[str, Any]]:
    argv = (sys.executable, "-m", "pip", "check")
    started = time.monotonic()
    try:
        process = subprocess.run(
            argv,
            cwd=workdir,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        exit_code = process.returncode
        stdout = process.stdout
        stderr = process.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, bytes) else (exc.stdout or "").encode()
        stderr = exc.stderr if isinstance(exc.stderr, bytes) else (exc.stderr or "").encode()
        timed_out = True
    elapsed = time.monotonic() - started
    check = ResolverCheck(
        argv=argv,
        exit_code=exit_code,
        stdout_sha256=sha_bytes(stdout),
        stderr_sha256=sha_bytes(stderr),
        network_disabled=True,
    )
    return (
        check,
        {
            "argv": list(argv),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_seconds": elapsed,
            "stdout_sha256": check.stdout_sha256,
            "stderr_sha256": check.stderr_sha256,
            "network_disabled": True,
        },
    )


def aggregate_decisions(
    decisions: Iterable[MetadataConsistencyDecision],
    collection_error_count: int = 0,
) -> MetadataConsistencyDecision:
    if collection_error_count < 0:
        raise ValueError("collection_error_count cannot be negative")
    values = tuple(decisions)
    active = tuple(sorted({item for value in values for item in value.active_requirements}))
    issues = tuple(issue for value in values for issue in value.issues)
    if not values:
        return MetadataConsistencyDecision(
            None, "no provenance-matched project distribution", active, issues
        )
    if any(value.passed is False for value in values):
        return MetadataConsistencyDecision(
            False, "at least one project distribution failed V1", active, issues
        )
    if collection_error_count:
        return MetadataConsistencyDecision(
            None, "V1 evidence collection was incomplete", active, issues
        )
    if all(value.passed is True for value in values):
        return MetadataConsistencyDecision(
            True, "all project distributions passed V1", active, issues
        )
    return MetadataConsistencyDecision(
        None, "at least one project distribution has unknown V1", active, issues
    )


def issue_dict(value: ConsistencyIssue) -> dict[str, Any]:
    return {
        "kind": value.kind,
        "requirement": value.requirement,
        "detail": value.detail,
    }


def decision_dict(value: MetadataConsistencyDecision) -> dict[str, Any]:
    return {
        "passed": value.passed,
        "reason": value.reason,
        "active_requirements": list(value.active_requirements),
        "issues": [issue_dict(item) for item in value.issues],
    }


def project_dict(value: ProjectMetadataEvidence) -> dict[str, Any]:
    return {
        "name": value.name,
        "version": value.version,
        "metadata_sha256": value.metadata_sha256,
        "provenance_kind": value.provenance_kind,
        "provenance_sha256": value.provenance_sha256,
        "requires_dist": list(value.requires_dist),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect and evaluate P5 V1 evidence.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--network-marker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selected-extra", action="append", default=[])
    args = parser.parse_args()
    if not args.network_marker.is_file():
        raise RuntimeError("host network-disconnect marker is missing")
    if default_route_present():
        raise RuntimeError("container still has a default network route")

    selected_extras = tuple(sorted(set(args.selected_extra)))
    installed_distributions = tuple(metadata.distributions())
    installed, installed_errors = collect_installed_observations(installed_distributions)
    matched = find_project_distributions(
        args.project_root,
        installed_distributions=installed_distributions,
    )
    marker_environment = {key: str(value) for key, value in default_environment().items()}
    distributions = []
    decisions = []
    collection_errors = list(installed_errors)
    with tempfile.TemporaryDirectory(prefix="envsolve-v1-empty-") as workdir:
        resolver, resolver_artifact = execute_resolver_check(Path(workdir))
        for match in matched:
            try:
                project, metadata_source = collect_project_evidence(match)
            except (KeyError, TypeError, ValueError) as exc:
                collection_errors.append(
                    {
                        "kind": "project-metadata-unreadable",
                        "distribution": str(match.distribution.metadata.get("Name", "")),
                        "detail": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            decision = evaluate_metadata_consistency(
                project,
                installed,
                marker_environment,
                selected_extras,
                resolver,
            )
            decisions.append(decision)
            distributions.append(
                {
                    "project": project_dict(project),
                    "metadata_source": metadata_source,
                    "decision": decision_dict(decision),
                }
            )

    aggregate = aggregate_decisions(decisions, len(collection_errors))
    result = {
        "schema": "envsolve-p5-v1-container-v1",
        "python": {"executable": sys.executable, "prefix": sys.prefix},
        "network": {"host_disconnect_marker": True, "default_route_present": False},
        "project_root": str(args.project_root.resolve()),
        "selected_extras": list(selected_extras),
        "marker_environment": marker_environment,
        "installed_distributions": [item.__dict__ for item in installed],
        "resolver": resolver_artifact,
        "distributions": distributions,
        "collection_errors": collection_errors,
        "decision": decision_dict(aggregate),
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
