from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner


@dataclass(frozen=True)
class RunnerOptions:
    source_run: Path | None = None


RunnerFactory = Callable[
    [HarnessConfig, ExperimentProtocol, RunSpec, RunnerOptions],
    SolverRunner,
]


@dataclass(frozen=True)
class RunnerRegistration:
    default_method: str
    factory: RunnerFactory


_RUNNERS: dict[str, RunnerRegistration] = {}
_BUILTINS_LOADED = False


def register_solver_runner(
    runner_id: str,
    default_method: str,
    factory: RunnerFactory,
) -> None:
    if runner_id in _RUNNERS:
        raise ValueError(f"Solver runner {runner_id!r} is already registered")
    _RUNNERS[runner_id] = RunnerRegistration(default_method, factory)


def _load_builtin_runners() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    from envsolve_harness.runners.deterministic import DeterministicScriptRunner
    from envsolve_harness.runners.codex_cli import CodexCliRunner
    from envsolve_harness.runners.envbench_agent import EnvBenchAgentRunner
    from envsolve_harness.runners.envsolve_v0 import EnvSolveV0Runner
    from envsolve_harness.runners.envsolve_p6 import EnvSolveP6Runner
    from envsolve_harness.runners.recorded_envbench import RecordedEnvBenchTrajectoryRunner
    from envsolve_harness.runners.recorded_codex import RecordedCodexCliRunner
    from envsolve_harness.runners.repo2run import Repo2RunRunner

    def codex_cli(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        benchmark = config.benchmark(protocol.benchmark)
        image = benchmark.settings.get("image")
        if not isinstance(image, str) or not image:
            raise ValueError("Codex CLI requires a benchmark execution image")
        configured = config.solver_roots.get("codex-cli")
        executable = configured or Path("/Applications/ChatGPT.app/Contents/Resources/codex")
        if executable.is_dir():
            executable = executable / "codex"
        return CodexCliRunner(
            codex_executable=executable,
            harness_root=config.workspace_root,
            image=image,
            timeout=config.generation_timeout,
            command_timeout=config.bash_timeout,
            container_create_timeout=config.create_container_timeout,
            git_fetch_timeout=config.git_fetch_timeout,
            reasoning_effort=config.model_reasoning_effort,
        )

    def deterministic(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        benchmark = config.benchmark(protocol.benchmark)
        relative_script = benchmark.settings.get("deterministic_script")
        if not isinstance(relative_script, str):
            raise ValueError(
                f"Benchmark {protocol.benchmark!r} does not configure deterministic_script"
            )
        return DeterministicScriptRunner(benchmark.root / relative_script)

    def repo2run(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        pricing = config.model_pricing.get(run_spec.model) if run_spec.model else None
        return Repo2RunRunner(
            config.solver_root("repo2run"),
            timeout=config.generation_timeout,
            model_request_timeout=config.model_request_timeout,
            model_max_retries=config.model_max_retries,
            max_model_requests=config.model_max_requests,
            max_total_tokens=config.model_max_total_tokens,
            max_estimated_cost_usd=config.model_max_estimated_cost_usd,
            pricing=pricing,
            harness_root=config.workspace_root,
        )

    def envbench_agent(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        pricing = config.model_pricing.get(run_spec.model) if run_spec.model else None
        return EnvBenchAgentRunner(
            config.solver_root("envbench-agent"),
            timeout=config.generation_timeout,
            max_iterations=config.agent_max_iterations,
            bash_timeout=config.bash_timeout,
            model_request_timeout=config.model_request_timeout,
            model_max_retries=config.model_max_retries,
            model_max_output_tokens=config.model_max_output_tokens,
            max_model_requests=config.model_max_requests,
            max_total_tokens=config.model_max_total_tokens,
            max_estimated_cost_usd=config.model_max_estimated_cost_usd,
            pricing=pricing,
            harness_root=config.workspace_root,
        )

    def recorded_codex(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        if options.source_run is None:
            raise ValueError("source_run is required for the recorded Codex runner")
        return RecordedCodexCliRunner(options.source_run)

    def recorded_envbench(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        if options.source_run is None:
            raise ValueError("source_run is required for the recorded trajectory runner")
        return RecordedEnvBenchTrajectoryRunner(options.source_run)

    def envsolve_v0(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        benchmark = config.benchmark(protocol.benchmark)
        image = benchmark.settings.get("image")
        if not isinstance(image, str) or not image:
            raise ValueError("EnvSolve v0 requires a benchmark image")
        pricing = config.model_pricing.get(run_spec.model) if run_spec.model else None
        return EnvSolveV0Runner(
            config.solver_root("envbench-agent"),
            image=image,
            timeout=config.generation_timeout,
            max_iterations=config.agent_max_iterations,
            bash_timeout=config.bash_timeout,
            model_request_timeout=config.model_request_timeout,
            model_max_retries=config.model_max_retries,
            model_max_output_tokens=config.model_max_output_tokens,
            max_model_requests=config.model_max_requests,
            max_total_tokens=config.model_max_total_tokens,
            max_estimated_cost_usd=config.model_max_estimated_cost_usd,
            pricing=pricing,
            harness_root=config.workspace_root,
        )

    def envsolve_p6(
        config: HarnessConfig,
        protocol: ExperimentProtocol,
        run_spec: RunSpec,
        options: RunnerOptions,
    ) -> SolverRunner:
        benchmark = config.benchmark(protocol.benchmark)
        image = benchmark.settings.get("image")
        if not isinstance(image, str) or not image:
            raise ValueError("EnvSolve requires a benchmark execution image")
        pricing = config.model_pricing.get(run_spec.model) if run_spec.model else None
        return EnvSolveP6Runner(
            envbench_root=config.solver_root("envbench-agent"),
            harness_root=config.workspace_root,
            source_cache_root=config.runs_root / "_source_cache/envbench-python",
            image=image,
            pricing=pricing,
            timeout=config.generation_timeout,
            max_candidates=config.envsolve_max_candidates,
            max_environments=config.envsolve_max_environments,
            max_commands=config.envsolve_max_commands,
            command_timeout=config.bash_timeout,
            container_create_timeout=config.create_container_timeout,
            model_request_timeout=config.model_request_timeout,
            model_max_retries=config.model_max_retries,
            model_max_output_tokens=config.model_max_output_tokens,
            model_reasoning_effort=config.model_reasoning_effort,
            model_response_format=config.model_response_format,
            max_model_requests=config.model_max_requests,
            max_total_tokens=config.model_max_total_tokens,
            max_estimated_cost_usd=config.model_max_estimated_cost_usd,
        )

    register_solver_runner("deterministic", "benchmark-deterministic", deterministic)
    register_solver_runner("codex-cli", "codex-cli-native", codex_cli)
    register_solver_runner("codex-recorded", "codex-cli-native-recorded", recorded_codex)
    register_solver_runner("repo2run", "repo2run", repo2run)
    register_solver_runner("envbench-agent", "envbench-react-freeagent", envbench_agent)
    register_solver_runner("envsolve-v0", "envsolve-v0", envsolve_v0)
    register_solver_runner("envsolve", "envsolve-full", envsolve_p6)
    register_solver_runner(
        "envbench-recorded",
        "envbench-react-freeagent",
        recorded_envbench,
    )
    _BUILTINS_LOADED = True


def registered_solver_runners() -> tuple[str, ...]:
    _load_builtin_runners()
    return tuple(sorted(_RUNNERS))


def default_method_for(runner_id: str) -> str:
    _load_builtin_runners()
    try:
        return _RUNNERS[runner_id].default_method
    except KeyError as exc:
        raise ValueError(f"Unknown solver runner: {runner_id!r}") from exc


def create_solver_runner(
    runner_id: str,
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions | None = None,
) -> SolverRunner:
    _load_builtin_runners()
    try:
        registration = _RUNNERS[runner_id]
    except KeyError as exc:
        raise ValueError(f"Unknown solver runner: {runner_id!r}") from exc
    return registration.factory(config, protocol, run_spec, options or RunnerOptions())
