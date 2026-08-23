from __future__ import annotations

from envsolve_harness.adapters.registry import (
    goal_contract_for,
    workspace_preconditions_for,
)
from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.openrouter_agent import OpenRouterAgentRunner, ReplayMode
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)


def _factory(replay_mode: ReplayMode):
    def create(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        del run_spec, options
        benchmark = config.benchmark(protocol.benchmark)
        image = benchmark.settings.get("image")
        if not isinstance(image, str) or not image:
            raise ValueError("OpenRouter Agent requires a benchmark execution image")
        return OpenRouterAgentRunner(
            harness_root=config.workspace_root,
            source_cache_root=(
                config.runs_root / "_source_cache/envbench-python"
            ),
            image=image,
            timeout=config.generation_timeout,
            command_timeout=config.bash_timeout,
            container_create_timeout=config.create_container_timeout,
            git_fetch_timeout=config.git_fetch_timeout,
            max_iterations=config.agent_max_iterations,
            model_request_timeout=config.model_request_timeout,
            model_max_retries=config.model_max_retries,
            model_max_output_tokens=config.model_max_output_tokens,
            reasoning_effort="xhigh",
            replay_mode=replay_mode,
            workspace_preconditions=workspace_preconditions_for(config, protocol),
            goal_contract=goal_contract_for(config, protocol),
        )

    return create


def register_envsolve_pro_v2_runners() -> None:
    registered = set(registered_solver_runners())
    if "deepseek-free-agent" not in registered:
        register_solver_runner(
            "deepseek-free-agent",
            "free-feedback-search",
            _factory("none"),
        )
    if "envsolve-pro-v2" not in registered:
        register_solver_runner(
            "envsolve-pro-v2",
            "envsolve-pro-fsr-minimal-h",
            _factory("soft"),
        )
    if "envsolve-pro-v2-incumbent" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-incumbent",
            "envsolve-pro-goal-triggered-certified-incumbent",
            _factory("incumbent"),
        )
    if "envsolve-pro-v2-ledger" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-ledger",
            "envsolve-pro-active-compatibility-ledger",
            _factory("ledger"),
        )
    if "envsolve-pro-v2-scheduled-observation" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-scheduled-observation",
            "envsolve-pro-scheduled-compatibility-observation",
            _factory("scheduled"),
        )
    if "envsolve-pro-v2-verifier-handoff" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-verifier-handoff",
            "envsolve-pro-verifier-triggered-handoff",
            _factory("handoff"),
        )
