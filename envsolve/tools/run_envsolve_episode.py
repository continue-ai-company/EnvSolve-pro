#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[2]
ENVBENCH = ROOT / "EnvBench"
for path in (ROOT, ENVBENCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from env_setup_utils.repo_downloader import RepoDownloader
from envsolve.runtime import (
    DockerFreshEnvironmentProvider,
    ExecutableGoalContract,
    ExecutableGoalContractVerifier,
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
        choices=("two-layer", "runtime-only", "goal-contract"),
        required=True,
    )
    parser.add_argument(
        "--operation-profile",
        choices=("constraint-driven", "free-form"),
        default="constraint-driven",
    )
    parser.add_argument(
        "--constraint-profile",
        choices=("flat", "causal-frontier", "raw-history"),
        default="flat",
    )
    parser.add_argument(
        "--repository-evidence-profile",
        choices=("disabled", "constraint-routed"),
        default="disabled",
    )
    parser.add_argument(
        "--candidate-anchor-profile",
        choices=("disabled", "retained-admissible"),
        default="disabled",
    )
    parser.add_argument(
        "--candidate-interface",
        choices=("typed-replay", "open-program"),
        default="typed-replay",
    )
    parser.add_argument(
        "--candidate-retention",
        choices=("best-admissible", "disabled"),
        default="best-admissible",
    )
    parser.add_argument(
        "--environment-strategy",
        choices=("fresh-candidate", "postcondition-persistent"),
        default="fresh-candidate",
    )
    parser.add_argument(
        "--pre-bootstrap-directory",
        action="append",
        default=[],
    )
    parser.add_argument("--goal-contract", type=Path)
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
    goal_contract = (
        ExecutableGoalContract.from_dict(
            json.loads(args.goal_contract.read_text(encoding="utf-8"))
        )
        if args.goal_contract is not None
        else None
    )
    if args.obligation_profile == "goal-contract" and goal_contract is None:
        raise ValueError("goal-contract profile requires --goal-contract")
    if args.obligation_profile != "goal-contract" and goal_contract is not None:
        raise ValueError("--goal-contract requires the goal-contract profile")
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
    base_platform_evidence = base_runtime.platform_constraint_evidence()
    repository_constraints = collect_repository_constraints(source_repository)
    admitted_evidence = repository_constraints.admissible_evidence(
        base_runtime_evidence
    )
    if args.constraint_profile == "causal-frontier":
        admitted_evidence = tuple(
            sorted(
                (*admitted_evidence, *base_platform_evidence),
                key=lambda item: item.evidence_id,
            )
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
            goal_contract=goal_contract.to_dict() if goal_contract is not None else None,
            candidate_language=candidate_validator.prompt_contract,
            operation_profile=args.operation_profile,
            constraint_profile=args.constraint_profile,
            repository_evidence_profile=args.repository_evidence_profile,
            candidate_anchor_profile=args.candidate_anchor_profile,
            environment_strategy=args.environment_strategy,
            repository_root=source_repository,
        ),
        environment_provider=provider,
        verifier=(
            ExecutableGoalContractVerifier(
                goal_contract,
                observation_timeout=args.command_timeout,
                effect_auditor=lambda worktree: inspect_repository(
                    worktree,
                    args.revision,
                    required_preconditions=workspace_preconditions,
                ),
            )
            if goal_contract is not None
            else PythonDeploymentVerifier(
                command_timeout=args.command_timeout,
                obligation_profile=args.obligation_profile,
                package_requirements=repository_constraints.evidence,
                effect_auditor=lambda worktree: inspect_repository(
                    worktree,
                    args.revision,
                    required_preconditions=workspace_preconditions,
                ),
            )
        ),
        candidate_validator=candidate_validator,
        operation_guard=(
            ConstraintOperationGuard()
            if args.operation_profile == "constraint-driven"
            else None
        ),
        budget=budget,
        max_candidates=args.max_candidates,
        retain_admissible_candidate=(
            args.candidate_retention == "best-admissible"
        ),
        environment_strategy=args.environment_strategy,
        condition=args.method,
        repository_profile=profile,
        initial_evidence=(
            ()
            if goal_contract is not None
            else admitted_evidence
            if args.operation_profile == "constraint-driven"
            or args.candidate_interface == "open-program"
            else ()
        ),
        initial_observation_summary={
            "repository": repository_constraints.summary(),
            "base_runtime": base_runtime.to_dict(),
            "conditional_runtime_admission": True,
            "constraint_profile": args.constraint_profile,
            "repository_evidence_profile": args.repository_evidence_profile,
            "candidate_anchor_profile": args.candidate_anchor_profile,
            **(
                {"environment_strategy": args.environment_strategy}
                if args.environment_strategy != "fresh-candidate"
                else {}
            ),
            "workspace_preconditions": [
                item.to_dict() for item in workspace_preconditions
            ],
            "goal_contract": (
                {
                    "contract_id": goal_contract.contract_id,
                    "report_schema": goal_contract.report_schema,
                    "sha256": goal_contract.sha256,
                }
                if goal_contract is not None
                else None
            ),
        },
        goal_id=(
            goal_contract.contract_id
            if goal_contract is not None
            else "environment-ready"
        ),
        goal_description=(
            goal_contract.description
            if goal_contract is not None
            else "Construct an executable project environment"
        ),
    ).run(case, RunArtifacts(args.artifacts_root), run_spec)
    return 0 if result.generation_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
