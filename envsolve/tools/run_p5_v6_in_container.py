#!/usr/bin/env python3
from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import platform
import sys

from packaging.markers import default_environment


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.verification.environment_state import (
    collect_installed_observations,
    collect_project_evidence,
)
from envsolve.verification.network_isolation import default_route_present
from envsolve.verification.project_provenance import find_project_distributions
from envsolve.verification.replay_equivalence import build_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a P5 V6 environment snapshot.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--network-marker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.network_marker.is_file():
        raise RuntimeError("host network-disconnect marker is missing")
    if default_route_present():
        raise RuntimeError("container still has a default network route")

    project_root = args.project_root.resolve()
    installed_objects = tuple(metadata.distributions())
    installed, installed_errors = collect_installed_observations(installed_objects)
    matches = find_project_distributions(
        project_root,
        installed_distributions=installed_objects,
    )
    errors = list(installed_errors)
    projects = []
    for match in matches:
        try:
            project, metadata_source = collect_project_evidence(match)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(
                {
                    "kind": "project-metadata-unreadable",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        projects.append(
            {
                "name": project.name,
                "version": project.version,
                "metadata_sha256": project.metadata_sha256,
                "metadata_source": metadata_source,
                "provenance_kind": project.provenance_kind,
                "provenance_sha256": project.provenance_sha256,
            }
        )
    if not projects:
        errors.append(
            {
                "kind": "project-distribution-missing",
                "detail": "no provenance-matched project distribution",
            }
        )

    python_runtime = {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
    }
    marker_environment = {
        key: str(value) for key, value in default_environment().items()
    }
    snapshot = None
    if not errors:
        state = build_snapshot(
            python_runtime,
            marker_environment,
            ((item.name, item.version) for item in installed),
            (
                (
                    item["name"],
                    item["version"],
                    item["metadata_sha256"],
                    item["provenance_kind"],
                    item["provenance_sha256"],
                )
                for item in projects
            ),
        )
        snapshot = {
            "sha256": state.sha256,
            "python_runtime": dict(state.python_runtime),
            "marker_environment": dict(state.marker_environment),
            "installed_distributions": [item.__dict__ for item in state.installed_distributions],
            "project_distributions": [item.__dict__ for item in state.project_distributions],
        }
    result = {
        "schema": "envsolve-p5-v6-snapshot-v1",
        "network": {"host_disconnect_marker": True, "default_route_present": False},
        "project_root": str(project_root),
        "snapshot": snapshot,
        "collection_errors": errors,
        "decision": {
            "passed": None,
            "reason": "V6 requires comparison with an independent fresh replay",
        },
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
