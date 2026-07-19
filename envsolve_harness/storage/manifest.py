from __future__ import annotations

from typing import Any
from dataclasses import asdict

from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.core.models import Case, HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import git_provenance, host_provenance, sha256_tree

MANIFEST_SCHEMA_VERSION = "0.6.0"


def initialize_manifest(
    artifacts: RunArtifacts,
    config: HarnessConfig,
    case: Case,
    run_spec: RunSpec,
    protocol: ExperimentProtocol,
) -> dict[str, Any]:
    resource_budget = config.resource_budget()
    if run_spec.model in config.model_pricing:
        resource_budget["model_pricing"] = asdict(config.model_pricing[run_spec.model])
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "protocol": protocol.to_dict(),
        "run": run_spec.to_dict(),
        "case": case.to_dict(),
        "host": host_provenance(),
        "harness": {
            **git_provenance(config.workspace_root),
            "source_sha256": sha256_tree(
                config.workspace_root,
                [
                    config.workspace_root / "envsolve_harness",
                    config.workspace_root / "experiments",
                    config.workspace_root / "envsolve/solver",
                    config.workspace_root / "envsolve/runtime",
                    config.workspace_root / "envsolve/constraints",
                    config.workspace_root / "envsolve/tools/run_envsolve_episode.py",
                    config.workspace_root / "envsolve/verification/counterexamples.py",
                    config.workspace_root / "envsolve/integrations/envbench_findings.py",
                ],
            ),
        },
        "resource_budget": resource_budget,
        "runtime_monitor": {
            "required": True,
            "schema_version": "1.0.0",
            "path": "runtime/heartbeat.jsonl",
            "interval_seconds": 5.0,
            "suspend_gap_seconds": 30.0,
            "state": "pending",
            "sha256": None,
        },
        "solver": None,
        "script": None,
        "evaluator": None,
        "result": None,
    }
    write_json(artifacts.manifest, manifest)
    write_json(artifacts.case_input, case.to_dict())
    return manifest


def ensure_manifest(
    artifacts: RunArtifacts,
    config: HarnessConfig,
    case: Case,
    run_spec: RunSpec,
    protocol: ExperimentProtocol,
) -> dict[str, Any]:
    if artifacts.manifest.is_file():
        return read_json(artifacts.manifest)
    return initialize_manifest(artifacts, config, case, run_spec, protocol)


def update_manifest(artifacts: RunArtifacts, **sections: Any) -> dict[str, Any]:
    manifest = read_json(artifacts.manifest)
    unknown = sections.keys() - manifest.keys()
    if unknown:
        raise ValueError(f"Unknown manifest sections: {sorted(unknown)}")
    manifest.update(sections)
    write_json(artifacts.manifest, manifest)
    return manifest
