#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.verification.installed_metadata import (
    collect_distribution_snapshot,
    installed_metadata_source,
)
from envsolve.verification.network_isolation import default_route_present
from envsolve.verification.project_provenance import (
    canonical_distribution_name,
    direct_url_project_path,
    find_project_distributions,
    is_project_distribution,
    legacy_egg_link_target,
    sha_bytes,
)
from envsolve.verification.smoke import (
    MetadataSmokePlanner,
    ProbeOutcome,
    SmokeDecision,
    SmokeProbe,
    execute_smoke_plan,
)

class SubprocessProbeRunner:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir

    def run(
        self,
        probe: SmokeProbe,
        *,
        timeout_seconds: int,
        network_disabled: bool,
        empty_workdir: bool,
    ) -> ProbeOutcome:
        if not network_disabled or not empty_workdir:
            raise ValueError("V3 probes require network isolation and an empty workdir")
        started = time.monotonic()
        try:
            process = subprocess.run(
                probe.argv,
                cwd=self.workdir,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
            return ProbeOutcome(
                probe.probe_id,
                process.returncode,
                duration_seconds=time.monotonic() - started,
                stdout_sha256=sha_bytes(process.stdout),
                stderr_sha256=sha_bytes(process.stderr),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, bytes) else (exc.stdout or "").encode()
            stderr = exc.stderr if isinstance(exc.stderr, bytes) else (exc.stderr or "").encode()
            return ProbeOutcome(
                probe.probe_id,
                None,
                timed_out=True,
                duration_seconds=time.monotonic() - started,
                stdout_sha256=sha_bytes(stdout),
                stderr_sha256=sha_bytes(stderr),
            )


def aggregate_decisions(
    decisions: Iterable[SmokeDecision],
    collection_error_count: int = 0,
) -> SmokeDecision:
    if collection_error_count < 0:
        raise ValueError("collection_error_count cannot be negative")
    values = tuple(decisions)
    observed = tuple(
        sorted({identifier for item in values for identifier in item.observed_probe_ids})
    )
    if not values:
        return SmokeDecision(None, "no provenance-matched project distribution", observed)
    if any(item.passed is False for item in values):
        return SmokeDecision(False, "at least one project distribution failed V3", observed)
    if collection_error_count:
        return SmokeDecision(
            None,
            "at least one project distribution could not be collected",
            observed,
        )
    if all(item.passed is True for item in values):
        return SmokeDecision(True, "all project distributions passed V3", observed)
    return SmokeDecision(None, "at least one project distribution has unknown V3", observed)


def snapshot_dict(value: Any) -> dict[str, Any]:
    return {
        "name": value.name,
        "version": value.version,
        "metadata_sha256": value.metadata_sha256,
        "top_level_modules": list(value.top_level_modules),
        "console_scripts": [item.__dict__ for item in value.console_scripts],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute frozen P5 V3 probes in a container.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--network-marker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.network_marker.is_file():
        raise RuntimeError("host network-disconnect marker is missing")
    if default_route_present():
        raise RuntimeError("container still has a default network route")

    matched = find_project_distributions(args.project_root)

    planner = MetadataSmokePlanner()
    distributions = []
    decisions = []
    collection_errors = []
    with tempfile.TemporaryDirectory(prefix="envsolve-v3-empty-") as workdir:
        empty_workdir = Path(workdir)
        for match in matched:
            distribution = match.distribution
            try:
                snapshot = collect_distribution_snapshot(
                    str(distribution.metadata["Name"]), distribution
                )
            except (KeyError, TypeError, ValueError) as exc:
                collection_errors.append(
                    {
                        "distribution": str(distribution.metadata["Name"]),
                        "version": str(distribution.version),
                        "kind": "installed-metadata-missing",
                        "detail": f"{type(exc).__name__}: {exc}",
                        "provenance": {
                            "kind": match.provenance_kind,
                            "sha256": match.provenance_sha256,
                        },
                    }
                )
                continue
            plan = planner.plan(snapshot)
            outcomes, decision = execute_smoke_plan(
                plan, SubprocessProbeRunner(empty_workdir), timeout_seconds=30
            )
            decisions.append(decision)
            distributions.append(
                {
                    "snapshot": snapshot_dict(snapshot),
                    "metadata_source": installed_metadata_source(distribution),
                    "provenance": {
                        "kind": match.provenance_kind,
                        "sha256": match.provenance_sha256,
                    },
                    "plan": {
                        "probes": [
                            {
                                "probe_id": item.probe_id,
                                "kind": item.kind.value,
                                "argv": list(item.argv),
                                "metadata_sha256": item.metadata_sha256,
                            }
                            for item in plan.probes
                        ],
                        "rejections": [item.__dict__ for item in plan.rejections],
                    },
                    "outcomes": [item.__dict__ for item in outcomes],
                    "decision": decision.__dict__,
                }
            )
    aggregate = aggregate_decisions(decisions, len(collection_errors))
    result = {
        "schema": "envsolve-p5-v3-container-v1",
        "python": {"executable": sys.executable, "prefix": sys.prefix},
        "network": {"host_disconnect_marker": True, "default_route_present": False},
        "project_root": str(args.project_root.resolve()),
        "distributions": distributions,
        "collection_errors": collection_errors,
        "decision": aggregate.__dict__,
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
