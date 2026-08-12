from __future__ import annotations

from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.core.models import RunSpec
from envsolve_harness.runners.codex_cli_qualified import (
    QualifiedCodexCliRunner,
    QualifiedEnvSolveProMinimalBRunner,
)
from envsolve_harness.runners.envsolve_pro_one_shot import (
    QualifiedEnvSolveProOneShotCertificationRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts


CONTROL_METHOD = "codex-cli-goal-aware-boundary-v2"
ONE_SHOT_METHOD = "envsolve-pro-one-shot-certification-boundary-v2"
MINIMAL_B_METHOD = "envsolve-pro-minimal-b-boundary-v2"


class _BoundaryV2MetadataMixin:
    boundary_version = "certification-repair-boundary-v2"

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        metadata["admissibility_boundary"] = {
            "version": self.boundary_version,
            "trusted_goal_shell": "noninterfering-privileged-bash",
            "repository_policy": (
                "clean-tracked-tree-and-provenance-derived-files-v6"
            ),
            "candidate_policy": "open-candidate-program-v2",
        }


class BoundaryV2QualifiedCodexCliRunner(
    _BoundaryV2MetadataMixin,
    QualifiedCodexCliRunner,
):
    runner_name = "codex-cli-qualified-boundary-v2"
    runner_version = "2.0.0"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == CONTROL_METHOD else None


class BoundaryV2QualifiedOneShotRunner(
    _BoundaryV2MetadataMixin,
    QualifiedEnvSolveProOneShotCertificationRunner,
):
    runner_name = "envsolve-pro-one-shot-certification-qualified-boundary-v2"
    runner_version = "2.0.0"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == ONE_SHOT_METHOD else None

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        for index, value in enumerate(arguments):
            if value == "envsolve_harness.codex.one_shot_mcp_qualified":
                arguments[index] = (
                    "envsolve_harness.codex."
                    "one_shot_mcp_boundary_v2_qualified"
                )
                break
        else:
            raise RuntimeError("Boundary v2 could not identify one-shot MCP module")
        return arguments


class BoundaryV2QualifiedMinimalBRunner(
    _BoundaryV2MetadataMixin,
    QualifiedEnvSolveProMinimalBRunner,
):
    runner_name = "envsolve-pro-minimal-b-qualified-boundary-v2"
    runner_version = "2.0.0"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == MINIMAL_B_METHOD else None

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        for index, value in enumerate(arguments):
            if value == "envsolve_harness.codex.minimal_b_mcp_qualified":
                arguments[index] = (
                    "envsolve_harness.codex."
                    "minimal_b_mcp_boundary_v2_qualified"
                )
                break
        else:
            raise RuntimeError("Boundary v2 could not identify Minimal B MCP module")
        return arguments
