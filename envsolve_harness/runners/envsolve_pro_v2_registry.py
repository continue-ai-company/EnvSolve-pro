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


def _factory(replay_mode: ReplayMode, *, public_goal_visible: bool = True):
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
            public_goal_visible=public_goal_visible,
            workspace_preconditions=workspace_preconditions_for(config, protocol),
            goal_contract=goal_contract_for(config, protocol),
        )

    return create


def register_envsolve_pro_v2_runners() -> None:
    registered = set(registered_solver_runners())
    if "deepseek-repository-agent" not in registered:
        register_solver_runner(
            "deepseek-repository-agent",
            "free-feedback-search-repository-signals",
            _factory("none", public_goal_visible=False),
        )
    if "deepseek-goal-aware-agent" not in registered:
        register_solver_runner(
            "deepseek-goal-aware-agent",
            "free-feedback-search-public-goal",
            _factory("none"),
        )
    if "deepseek-free-agent" not in registered:
        register_solver_runner(
            "deepseek-free-agent",
            "free-feedback-search",
            _factory("none"),
        )
    if "envsolve-pro-v2-atomic" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-atomic",
            "envsolve-pro-atomic-submit-replay",
            _factory("atomic"),
        )
    if "envsolve-pro-v2-atomic-handoff" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-atomic-handoff",
            "envsolve-pro-verified-atomic-handoff",
            _factory("atomic-handoff"),
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
    if "envsolve-pro-v2-current-goal" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-current-goal",
            "envsolve-pro-current-goal-constraints",
            _factory("current"),
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
    if "envsolve-pro-v2-operation-frontier" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-operation-frontier",
            "envsolve-pro-operation-triggered-compatibility-frontier",
            _factory("operation-frontier"),
        )
    if "envsolve-pro-v2-verifier-handoff" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-verifier-handoff",
            "envsolve-pro-verifier-triggered-handoff",
            _factory("handoff"),
        )
    if "envsolve-pro-v2-stateful-replay" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-stateful-replay",
            "envsolve-pro-stateful-replay-obligation-ledger",
            _factory("stateful"),
        )
    if "envsolve-pro-v2-incremental-program" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-incremental-program",
            "envsolve-pro-incremental-executable-program",
            _factory("incremental"),
        )
    if "envsolve-pro-v2-incremental-program-annotated" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-incremental-program-annotated",
            "envsolve-pro-annotated-incremental-executable-program",
            _factory("incremental-annotated"),
        )
    if "envsolve-pro-v2-incremental-program-editable" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-incremental-program-editable",
            "envsolve-pro-editable-incremental-executable-program",
            _factory("incremental-editable"),
        )
    if "envsolve-pro-v2-incremental-program-transactional-editable" not in registered:
        register_solver_runner(
            "envsolve-pro-v2-incremental-program-transactional-editable",
            "envsolve-pro-transactional-editable-incremental-executable-program",
            _factory("incremental-transactional-editable"),
        )
