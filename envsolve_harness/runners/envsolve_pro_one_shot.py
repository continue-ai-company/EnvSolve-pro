from __future__ import annotations

from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.codex_cli import CodexCliRunner
from envsolve_harness.runners.codex_cli_qualified import (
    QualifiedCodexInfrastructureMixin,
)
from envsolve_harness.runners.envsolve_pro_minimal_b import (
    EnvSolveProMinimalBRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts

METHOD = "envsolve-pro-one-shot-certification-v1"


class EnvSolveProOneShotCertificationRunner(EnvSolveProMinimalBRunner):
    """One active Agent session with exactly one clean certification call."""

    runner_name = "envsolve-pro-one-shot-certification"
    runner_version = "1.0.0"
    agent_interface = "continuous-agent+one-shot-clean-certification-mcp-v1"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == METHOD else None

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        prompt = CodexCliRunner._prompt(self, case, goal_contract)
        if goal_contract is None:
            return prompt
        return (
            prompt
            + "\n"
            + """\
This is the frozen EnvSolve-Pro one-shot certification interface. Keep diagnosis and
repair inside this one conversation and the persistent construction container. Before
returning your final JSON, you MUST call `submit_and_replay` exactly once with the
complete self-contained bootstrap program. The tool runs that program in a distinct
clean checkout and container and returns only internal public-goal and integrity
evidence to this same session.

There is no second clean replay in this condition. Submit only when the complete
program is ready. Return the exact same `bootstrap_script` only if that one replay
returns `status=pass` and `certified=true`; otherwise the episode cannot be certified.
The terminal Official evaluator remains unavailable.

The shared admissibility boundary rejects candidate-generated compatibility packages,
local distributions that expose modules absent from the repository, unowned import
artifacts, and deletion or falsification of installation metadata. Do not create a
module or stub solely to silence a missing-import finding.
"""
        )

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        for index, value in enumerate(arguments):
            if value == "envsolve_harness.codex.minimal_b_mcp":
                arguments[index] = "envsolve_harness.codex.one_shot_mcp"
                break
        else:
            raise RuntimeError("One-shot runner could not identify its MCP module")
        return arguments

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        metadata["minimal_b"]["condition"] = "one-shot-certification"
        metadata["minimal_b"]["replay_policy"] = {
            "maximum_executed_replays": 1,
            "feedback_returned_to_same_session": True,
            "retry_after_replay": False,
        }


class QualifiedEnvSolveProOneShotCertificationRunner(
    QualifiedCodexInfrastructureMixin,
    EnvSolveProOneShotCertificationRunner,
):
    runner_name = "envsolve-pro-one-shot-certification-qualified"
    runner_version = "1.0.0"

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = EnvSolveProOneShotCertificationRunner._mcp_server_args(
            self,
            **kwargs,
        )
        for index, value in enumerate(arguments):
            if value == "envsolve_harness.codex.one_shot_mcp":
                arguments[index] = "envsolve_harness.codex.one_shot_mcp_qualified"
                break
        else:
            raise RuntimeError(
                "Qualified one-shot runner could not identify its MCP module"
            )
        return arguments
