#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


# ruff: noqa: E402 - register the experimental runner before CLI parsing.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.adapters.registry import (
    goal_contract_for,
    workspace_preconditions_for,
)
from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from envsolve_harness.runners.stateful_codex import (
    RAW_HISTORY_METHOD,
    RAW_HISTORY_METHOD_V2,
    RAW_HISTORY_METHOD_V21,
    RAW_HISTORY_METHOD_V22,
    RAW_HISTORY_METHOD_V23,
    RAW_HISTORY_METHOD_V24,
    STRUCTURED_METHOD,
    STRUCTURED_METHOD_V2,
    STRUCTURED_METHOD_V21,
    STRUCTURED_METHOD_V22,
    STRUCTURED_METHOD_V23,
    STRUCTURED_METHOD_V24,
    StatefulCodexCliRunner,
)


RUNNER_METHODS = {
    "codex-stateful-raw": RAW_HISTORY_METHOD,
    "envsolve-pro-stateful-agent": STRUCTURED_METHOD,
    "codex-stateful-raw-v2": RAW_HISTORY_METHOD_V2,
    "envsolve-pro-stateful-agent-v2": STRUCTURED_METHOD_V2,
    "codex-stateful-raw-v2.1": RAW_HISTORY_METHOD_V21,
    "envsolve-pro-stateful-agent-v2.1": STRUCTURED_METHOD_V21,
    "codex-stateful-raw-v2.2": RAW_HISTORY_METHOD_V22,
    "envsolve-pro-stateful-agent-v2.2": STRUCTURED_METHOD_V22,
    "codex-stateful-raw-v2.3": RAW_HISTORY_METHOD_V23,
    "envsolve-pro-stateful-agent-v2.3": STRUCTURED_METHOD_V23,
    "codex-stateful-raw-v2.4": RAW_HISTORY_METHOD_V24,
    "envsolve-pro-stateful-agent-v2.4": STRUCTURED_METHOD_V24,
}


def _factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    benchmark = config.benchmark(protocol.benchmark)
    image = benchmark.settings.get("image")
    if not isinstance(image, str) or not image:
        raise ValueError("Stateful Codex requires a benchmark execution image")
    if run_spec.method not in set(RUNNER_METHODS.values()):
        raise ValueError(f"Unsupported Stateful Codex method {run_spec.method!r}")
    configured = config.solver_roots.get("codex-cli")
    executable = configured or Path(
        "/Applications/ChatGPT.app/Contents/Resources/codex"
    )
    if executable.is_dir():
        executable = executable / "codex"
    v22 = run_spec.method in {STRUCTURED_METHOD_V22, RAW_HISTORY_METHOD_V22}
    v23 = run_spec.method in {STRUCTURED_METHOD_V23, RAW_HISTORY_METHOD_V23}
    v24 = run_spec.method in {STRUCTURED_METHOD_V24, RAW_HISTORY_METHOD_V24}
    v21 = v22 or run_spec.method in {
        STRUCTURED_METHOD_V21,
        RAW_HISTORY_METHOD_V21,
    }
    v2 = v21 or run_spec.method in {
        STRUCTURED_METHOD_V2,
        RAW_HISTORY_METHOD_V2,
    }
    return StatefulCodexCliRunner(
        codex_executable=executable,
        harness_root=config.workspace_root,
        image=image,
        timeout=config.generation_timeout,
        command_timeout=config.bash_timeout,
        container_create_timeout=config.create_container_timeout,
        git_fetch_timeout=config.git_fetch_timeout,
        reasoning_effort=config.model_reasoning_effort,
        workspace_preconditions=workspace_preconditions_for(config, protocol),
        goal_contract=goal_contract_for(config, protocol),
        max_rounds=config.envsolve_max_candidates,
        feedback_mode=(
            "structured"
            if run_spec.method
            in {
                STRUCTURED_METHOD,
                STRUCTURED_METHOD_V2,
                STRUCTURED_METHOD_V21,
                STRUCTURED_METHOD_V22,
                STRUCTURED_METHOD_V23,
                STRUCTURED_METHOD_V24,
            }
            else "raw"
        ),
        method_profile=(
            "stateful-agent-v2.4"
            if v24
            else "stateful-agent-v2.3"
            if v23
            else "stateful-agent-v2.2"
            if v22
            else "stateful-agent-v2.1"
            if v21
            else "stateful-agent-v2"
            if v2
            else "stateful-agent-v1"
        ),
        initial_probe=v2 and not v23,
        enforce_project_namespace_provenance=v2 and not v23,
        restore_shell_invariants=v2 and not v23,
    )


def main() -> int:
    registered_solver_runners()
    for runner_id, method in RUNNER_METHODS.items():
        register_solver_runner(runner_id, method, _factory)
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
