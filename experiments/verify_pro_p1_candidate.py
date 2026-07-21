#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.runtime import (
    DockerFreshEnvironmentProvider,
    PythonDeploymentVerifier,
    WorkspacePrecondition,
    collect_repository_constraints,
)
from envsolve.solver import DeploymentCandidate
from envsolve_harness.core.io import write_json, write_text_atomic
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify one frozen candidate under the P1 fresh-effect interface."
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    parser.add_argument("--pre-bootstrap-directory", action="append", default=[])
    parser.add_argument("--command-timeout", type=int, default=900)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source_repository.resolve()
    script_path = args.script.resolve()
    try:
        recorded_script_path = str(script_path.relative_to(ROOT))
    except ValueError:
        recorded_script_path = str(script_path)
    output = args.output_root.resolve()
    if output.exists():
        if not args.overwrite:
            raise FileExistsError(f"Candidate verification output exists: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    preconditions = tuple(
        WorkspacePrecondition(path, producer="benchmark-adapter")
        for path in args.pre_bootstrap_directory
    )
    constraints = collect_repository_constraints(source)
    scratch_root = Path(tempfile.mkdtemp(prefix="envsolve-pro-p1-"))
    provider = DockerFreshEnvironmentProvider(
        source_repository=source,
        worktrees_root=scratch_root / "worktrees",
        repository=args.repository,
        revision=args.revision,
        image=args.image,
        workspace_preconditions=preconditions,
    )
    candidate = DeploymentCandidate(
        "frozen-candidate",
        script_path.read_text(encoding="utf-8"),
        "Replay a frozen consumed-case candidate under P1",
        metadata={
            "candidate_validation": {
                "policy_id": "open-candidate-program-v1",
                "details": {"source_script_sha256": sha256_file(script_path)},
            }
        },
    )
    environment = None
    try:
        base_runtime = provider.observe_base_runtime()
        environment = provider.provision(candidate)
        result = PythonDeploymentVerifier(
            command_timeout=args.command_timeout,
            package_requirements=constraints.evidence,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                args.revision,
                required_preconditions=preconditions,
            ),
        ).verify(candidate, environment)
        write_text_atomic(output / "bootstrap.stdout", result.bootstrap.stdout)
        write_text_atomic(output / "bootstrap.stderr", result.bootstrap.stderr)
        payload = {
            "schema": "envsolve-pro-p1-frozen-candidate-verification-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repository": args.repository,
            "revision": args.revision,
            "source_repository_head": args.revision,
            "source_script": recorded_script_path,
            "source_script_sha256": sha256_file(script_path),
            "model_requests": 0,
            "base_runtime": base_runtime.to_dict(),
            "workspace_preconditions": [item.to_dict() for item in preconditions],
            "environment_receipt": environment.receipt.to_dict(),
            "verification": {
                "verifier": result.verifier,
                "check_profile": result.check_profile,
                "channel": result.channel.value,
                "passed": result.passed,
                "summary": result.summary,
                "bootstrap": {
                    **asdict(result.bootstrap),
                    "stdout_path": "bootstrap.stdout",
                    "stderr_path": "bootstrap.stderr",
                },
                "details": result.details,
                "counterexamples": [asdict(item) for item in result.counterexamples],
                "hypotheses": [asdict(item) for item in result.hypotheses],
            },
        }
        payload["verification"]["bootstrap"].pop("stdout")
        payload["verification"]["bootstrap"].pop("stderr")
        write_json(output / "result.json", payload)
        print(f"passed={result.passed}")
        print(f"summary={result.summary}")
        print(f"bootstrap_exit_code={result.bootstrap.exit_code}")
        print(f"artifacts={output}")
        return 0 if result.passed is False else 1
    finally:
        if environment is not None:
            provider.release(environment)
        shutil.rmtree(scratch_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
