#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402 - allow direct execution from the experiments directory.

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve.solver import DeploymentCandidate
from envsolve_harness.adapters.envbench_goal import envbench_python_goal_contract
from envsolve_harness.boundary_v3 import (
    BoundaryV3MinimalBExecutableGoalVerifier,
    BoundaryV3OpenCandidateProgramValidator,
    MANAGED_DEPENDENCY_MARKER,
    install_boundary_v3_local_distribution_audit,
)
from envsolve_harness.codex.minimal_b_mcp import canonical_script
from envsolve_harness.core.io import write_json
from envsolve_harness.integrity.repository import inspect_repository
from envsolve.runtime.integrity import marked_json_payload


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qualify an exact consumed candidate under boundary v3."
    )
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--worktrees", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--expected-program-sha256", required=True)
    parser.add_argument("--expected-boundary-sha256", required=True)
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    parser.add_argument("--workspace-directory", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=1800)
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    args = _args()
    boundary_path = ROOT / "envsolve_harness" / "boundary_v3.py"
    boundary_sha256 = _sha256_file(boundary_path)
    if boundary_sha256 != args.expected_boundary_sha256:
        raise ValueError("Boundary implementation hash does not match frozen input")
    source_program_sha256 = _sha256_file(args.program)
    if source_program_sha256 != args.expected_program_sha256:
        raise ValueError("Consumed program hash does not match frozen input")
    program = canonical_script(args.program.read_text(encoding="utf-8"))
    candidate = DeploymentCandidate(
        "consumed-boundary-v3-validation",
        program,
        "Outcome-excluded qualification of an exact consumed candidate",
        metadata={
            "environment_fresh": True,
            "execution_role": "consumed-boundary-validation",
        },
    )
    validation = BoundaryV3OpenCandidateProgramValidator().validate(candidate)
    base = {
        "schema_version": "1.0.0",
        "validation_id": "envsolve-pro-boundary-v3-consumed-candidate-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "repository": args.repository,
        "revision": args.revision,
        "source_program_sha256": source_program_sha256,
        "canonical_program_sha256": hashlib.sha256(
            program.encode("utf-8")
        ).hexdigest(),
        "boundary_implementation_sha256": boundary_sha256,
        "candidate_validation": {
            "accepted": validation.accepted,
            "policy_id": validation.policy_id,
            "reason": validation.reason,
            "details": validation.details,
        },
        "claim_scope": "consumed-boundary-validation-only-outcome-excluded",
    }
    if not validation.accepted:
        payload = {
            **base,
            "classification": "candidate-policy-rejected",
            "validation_pass": False,
        }
        write_json(args.output, payload)
        return 1

    candidate = DeploymentCandidate(
        candidate.candidate_id,
        (validation.normalized_script or program).strip(),
        candidate.rationale,
        metadata=candidate.metadata,
    )
    install_boundary_v3_local_distribution_audit()
    preconditions = tuple(
        WorkspacePrecondition(
            path=value,
            kind="directory",
            producer="envbench-python-build-v1",
        )
        for value in args.workspace_directory
    )
    provider = DockerFreshEnvironmentProvider(
        source_repository=args.source_repository,
        worktrees_root=args.worktrees,
        repository=args.repository,
        revision=args.revision,
        image=args.image,
        workspace_preconditions=preconditions,
    )
    contract = envbench_python_goal_contract()
    environment = provider.provision(candidate)
    try:
        outcome = BoundaryV3MinimalBExecutableGoalVerifier(
            contract,
            observation_timeout=args.timeout,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                args.revision,
                required_preconditions=preconditions,
            ),
        ).verify(candidate, environment)
    finally:
        provider.release(environment)

    provenance = marked_json_payload(
        outcome.bootstrap.stdout,
        MANAGED_DEPENDENCY_MARKER,
    )
    candidate_completed = "ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1=" in (
        outcome.bootstrap.stdout
    )
    goal_report_observed = (
        "ENVSOLVE_GOAL_REPORT_BEGIN_V1=" in outcome.bootstrap.stdout
        and "ENVSOLVE_GOAL_REPORT_END_V1=" in outcome.bootstrap.stdout
    )
    censored = not candidate_completed or not goal_report_observed
    payload = {
        **base,
        "goal_contract": {
            "contract_id": contract.contract_id,
            "sha256": contract.sha256,
        },
        "workspace_preconditions": [item.to_dict() for item in preconditions],
        "environment_receipt": environment.receipt.to_dict(),
        "outcome": {
            "passed": outcome.passed,
            "summary": outcome.summary,
            "check_profile": outcome.check_profile,
            "bootstrap": asdict(outcome.bootstrap),
            "observations": [asdict(item) for item in outcome.observations],
            "counterexamples": [asdict(item) for item in outcome.counterexamples],
            "details": outcome.details,
        },
        "mechanism_evidence": {
            "candidate_completed": candidate_completed,
            "goal_report_observed": goal_report_observed,
            "managed_dependency_provenance": provenance,
        },
        "classification": (
            "boundary-v3-qualified"
            if outcome.passed
            else (
                "infrastructure-censored-before-trusted-goal"
                if censored
                else "boundary-v3-not-qualified"
            )
        ),
        "validation_pass": outcome.passed,
    }
    write_json(args.output, payload)
    if outcome.passed:
        return 0
    return 2 if censored else 1


if __name__ == "__main__":
    raise SystemExit(main())
