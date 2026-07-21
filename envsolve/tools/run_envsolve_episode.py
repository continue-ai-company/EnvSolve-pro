#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
ENVBENCH = ROOT / "EnvBench"
for path in (ROOT, ENVBENCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from env_setup_utils.repo_downloader import RepoDownloader
from envsolve.runtime import (
    DockerFreshEnvironmentProvider,
    PythonDeploymentVerifier,
    StructuredModelDeploymentPolicy,
    WorkspacePrecondition,
    collect_repository_constraints,
    profile_python_repository,
)
from envsolve_harness.budget import BudgetLedger, BudgetLimits, TokenPricing
from envsolve_harness.budget.langchain import create_budgeted_chat_model
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.envsolve import EnvSolveEpisodeRunner
from envsolve_harness.scripts import (
    ConstraintOperationGuard,
    OpenCandidateProgramValidator,
    TypedReplayCandidateValidator,
)
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.storage.artifacts import RunArtifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one complete EnvSolve episode.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--source-cache", type=Path, required=True)
    parser.add_argument("--worktrees", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--max-candidates", type=int, required=True)
    parser.add_argument("--max-environments", type=int)
    parser.add_argument("--max-commands", type=int)
    parser.add_argument("--wall-clock-timeout", type=int, required=True)
    parser.add_argument("--container-create-timeout", type=int, required=True)
    parser.add_argument("--command-timeout", type=int, required=True)
    parser.add_argument(
        "--obligation-profile",
        choices=("two-layer", "runtime-only"),
        required=True,
    )
    parser.add_argument(
        "--operation-profile",
        choices=("constraint-driven", "free-form"),
        default="constraint-driven",
    )
    parser.add_argument(
        "--candidate-interface",
        choices=("typed-replay", "open-program"),
        default="typed-replay",
    )
    parser.add_argument(
        "--pre-bootstrap-directory",
        action="append",
        default=[],
    )
    parser.add_argument("--request-timeout", type=int, required=True)
    parser.add_argument("--max-retries", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh", "max"),
    )
    parser.add_argument(
        "--response-format",
        choices=("text", "json_object"),
        default="text",
    )
    parser.add_argument("--max-model-requests", type=int, required=True)
    parser.add_argument("--max-total-tokens", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--input-cost", type=float, required=True)
    parser.add_argument("--output-cost", type=float, required=True)
    parser.add_argument("--cache-read-cost", type=float, required=True)
    parser.add_argument("--pricing-source-url")
    parser.add_argument("--pricing-snapshot-date")
    parser.add_argument("--seed", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_environments = (
        args.max_environments
        if args.max_environments is not None
        else args.max_candidates
    )
    max_commands = (
        args.max_commands if args.max_commands is not None else args.max_candidates
    )
    args.source_cache.mkdir(parents=True, exist_ok=True)
    downloader = RepoDownloader(
        hf_name="JetBrains-Research/EnvBench",
        output_dir=str(args.source_cache),
        language="python",
    )
    if not downloader.download(repo_name=args.repository, commit_sha=args.revision):
        raise RuntimeError("Unable to acquire the requested repository revision")
    source_repository = Path(
        downloader.get_repo_dir_path(
            repo_name=args.repository,
            commit_sha=args.revision,
        )
    )
    profile = profile_python_repository(source_repository)
    workspace_preconditions = tuple(
        WorkspacePrecondition(
            path,
            producer="benchmark-adapter",
        )
        for path in args.pre_bootstrap_directory
    )
    provider = DockerFreshEnvironmentProvider(
        source_repository=source_repository,
        worktrees_root=args.worktrees,
        repository=args.repository,
        revision=args.revision,
        image=args.image,
        workspace_preconditions=workspace_preconditions,
        create_timeout=args.container_create_timeout,
    )
    base_runtime = provider.observe_base_runtime()
    base_runtime_evidence = base_runtime.constraint_evidence()
    repository_constraints = collect_repository_constraints(source_repository)
    admitted_evidence = repository_constraints.admissible_evidence(
        base_runtime_evidence
    )
    common_limits = {
        "budget_max_candidates": args.max_candidates,
        "budget_max_environments": max_environments,
        "budget_max_commands": max_commands,
        "budget_max_wall_clock_seconds": args.wall_clock_timeout,
    }
    model_kwargs = {
        "request_timeout": args.request_timeout,
        "max_retries": args.max_retries,
        "max_tokens": args.max_output_tokens,
        "temperature": 0,
    }
    if args.seed is not None:
        model_kwargs["seed"] = args.seed
    if args.reasoning_effort is not None:
        model_kwargs["reasoning_effort"] = args.reasoning_effort
    if args.response_format == "json_object":
        model_kwargs["model_kwargs"] = {
            "response_format": {"type": "json_object"}
        }
    model = create_budgeted_chat_model(
        model=args.model,
        budget_ledger_path=str(args.ledger),
        budget_max_model_requests=args.max_model_requests,
        budget_max_total_tokens=args.max_total_tokens,
        budget_max_estimated_cost_usd=args.max_cost_usd,
        budget_input_cost_per_million=args.input_cost,
        budget_output_cost_per_million=args.output_cost,
        budget_cache_read_cost_per_million=args.cache_read_cost,
        budget_pricing_source_url=args.pricing_source_url,
        budget_pricing_snapshot_date=args.pricing_snapshot_date,
        **common_limits,
        **model_kwargs,
    )
    limits = BudgetLimits(
        args.max_model_requests,
        args.max_total_tokens,
        args.max_cost_usd,
        max_candidates=args.max_candidates,
        max_environments=max_environments,
        max_commands=max_commands,
        max_wall_clock_seconds=args.wall_clock_timeout,
    )
    pricing = TokenPricing(
        args.model,
        args.input_cost,
        args.output_cost,
        args.cache_read_cost,
        args.pricing_source_url,
        args.pricing_snapshot_date,
    )
    budget = BudgetLedger(args.ledger, limits, pricing)
    case = Case(args.case_id, args.repository, args.revision)
    run_spec = RunSpec(args.run_id, args.method, args.model, args.seed)
    candidate_validator = (
        OpenCandidateProgramValidator()
        if args.candidate_interface == "open-program"
        else TypedReplayCandidateValidator()
    )
    result = EnvSolveEpisodeRunner(
        policy=StructuredModelDeploymentPolicy(
            model,
            profile,
            candidate_language=candidate_validator.prompt_contract,
            operation_profile=args.operation_profile,
        ),
        environment_provider=provider,
        verifier=PythonDeploymentVerifier(
            command_timeout=args.command_timeout,
            obligation_profile=args.obligation_profile,
            package_requirements=repository_constraints.evidence,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                args.revision,
                required_preconditions=workspace_preconditions,
            ),
        ),
        candidate_validator=candidate_validator,
        operation_guard=(
            ConstraintOperationGuard()
            if args.operation_profile == "constraint-driven"
            else None
        ),
        budget=budget,
        max_candidates=args.max_candidates,
        condition=args.method,
        repository_profile=profile,
        initial_evidence=(
            admitted_evidence
            if args.operation_profile == "constraint-driven"
            or args.candidate_interface == "open-program"
            else ()
        ),
        initial_observation_summary={
            "repository": repository_constraints.summary(),
            "base_runtime": base_runtime.to_dict(),
            "conditional_runtime_admission": True,
            "workspace_preconditions": [
                item.to_dict() for item in workspace_preconditions
            ],
        },
    ).run(case, RunArtifacts(args.artifacts_root), run_spec)
    return 0 if result.generation_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
