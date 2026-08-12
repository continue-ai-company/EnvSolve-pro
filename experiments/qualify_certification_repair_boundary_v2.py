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
from envsolve.solver import DeploymentCandidate
from envsolve_harness.adapters.envbench_goal import envbench_python_goal_contract
from envsolve_harness.boundary_v2 import (
    BoundaryV2MinimalBExecutableGoalVerifier,
)
from envsolve_harness.core.io import write_json
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def repository_effect_audit(details: dict[str, object]) -> dict[str, object] | None:
    direct = details.get("repository_effect_audit")
    if isinstance(direct, dict):
        return direct
    report_details = details.get("report_details")
    if not isinstance(report_details, dict):
        return None
    nested = report_details.get("repository_effect_audit")
    return nested if isinstance(nested, dict) else None


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a consumed program against certification boundary v2."
    )
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--worktrees", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--expected-program-sha256", required=True)
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    parser.add_argument("--timeout", type=int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = _args()
    program_bytes = args.program.read_bytes()
    source_program_sha256 = hashlib.sha256(program_bytes).hexdigest()
    if source_program_sha256 != args.expected_program_sha256:
        raise ValueError("Consumed program hash does not match the frozen input")
    program = program_bytes.decode("utf-8").strip()
    canonical_program_sha256 = _sha256(program)
    candidate = DeploymentCandidate(
        "readux-consumed-c-boundary-v2",
        program,
        "Counterfactual replay of the exact consumed Readux C program",
        metadata={
            "environment_fresh": True,
            "execution_role": "consumed-boundary-qualification",
        },
    )
    validation = OpenCandidateProgramValidator().validate(candidate)
    if not validation.accepted:
        raise RuntimeError(f"Frozen candidate failed v2 validation: {validation.reason}")
    candidate = DeploymentCandidate(
        candidate.candidate_id,
        (validation.normalized_script or program).strip(),
        candidate.rationale,
        metadata=candidate.metadata,
    )
    provider = DockerFreshEnvironmentProvider(
        source_repository=args.source_repository,
        worktrees_root=args.worktrees,
        repository=args.repository,
        revision=args.revision,
        image=args.image,
    )
    contract = envbench_python_goal_contract()
    environment = provider.provision(candidate)
    try:
        outcome = BoundaryV2MinimalBExecutableGoalVerifier(
            contract,
            observation_timeout=args.timeout,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                args.revision,
            ),
        ).verify(candidate, environment)
    finally:
        provider.release(environment)

    candidate_completed = (
        "ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1=" in outcome.bootstrap.stdout
    )
    goal_report_observed = (
        "ENVSOLVE_GOAL_REPORT_BEGIN_V1=" in outcome.bootstrap.stdout
        and "ENVSOLVE_GOAL_REPORT_END_V1=" in outcome.bootstrap.stdout
    )
    repository_audit = repository_effect_audit(outcome.details)
    repository_integrity_pass = (
        isinstance(repository_audit, dict)
        and repository_audit.get("valid") is True
    )
    qualification_pass = (
        outcome.passed is False
        and candidate_completed
        and goal_report_observed
        and repository_integrity_pass
    )
    censored = not candidate_completed or not goal_report_observed
    payload = {
        "schema_version": "1.0.0",
        "qualification_id": (
            "envsolve-pro-certification-repair-boundary-v2-readux-consumed"
        ),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "repository": args.repository,
        "revision": args.revision,
        "source_program_sha256": source_program_sha256,
        "canonical_program_sha256": canonical_program_sha256,
        "goal_contract": {
            "contract_id": contract.contract_id,
            "sha256": contract.sha256,
        },
        "candidate_validation": {
            "accepted": validation.accepted,
            "policy_id": validation.policy_id,
            "details": validation.details,
        },
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
            "repository_integrity_pass": repository_integrity_pass,
        },
        "classification": (
            "qualified-boundary-rejection"
            if qualification_pass
            else (
                "infrastructure-censored-before-trusted-goal"
                if censored
                else "qualification-failed"
            )
        ),
        "qualification_pass": qualification_pass,
        "qualification_rule": (
            "The exact verifier-interfering Readux C program must not receive "
            "a passing v2 clean-replay certificate."
        ),
        "claim_scope": "consumed-boundary-qualification-only",
    }
    write_json(args.output, payload)
    if payload["qualification_pass"]:
        return 0
    return 2 if censored else 1


if __name__ == "__main__":
    raise SystemExit(main())
