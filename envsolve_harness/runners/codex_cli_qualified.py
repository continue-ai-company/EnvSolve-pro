from __future__ import annotations

from pathlib import Path
from typing import Any

from envsolve_harness.core.models import Case
from envsolve_harness.execution.process import checked_output
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache
from envsolve_harness.runners.codex_cli import CodexCliRunner
from envsolve_harness.runners.envsolve_pro_minimal_b import (
    EnvSolveProMinimalBRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts


class QualifiedCodexInfrastructureMixin:
    infrastructure_profile = "codex-qualified-infrastructure-v1"

    def __init__(self, *, source_cache_root: Path, **kwargs: Any) -> None:
        self.source_cache_root = source_cache_root.resolve()
        super().__init__(**kwargs)

    @staticmethod
    def _checked(
        command: list[str],
        *,
        timeout: int,
        cwd: Path | None = None,
    ) -> str:
        return checked_output(command, timeout=timeout, cwd=cwd)

    def _acquire_repository(self, case: Case, destination: Path) -> dict[str, Any]:
        return ExactRevisionSourceCache(
            self.source_cache_root,
            self.git_fetch_timeout,
        ).acquire(
            repository=case.repository,
            revision=case.revision,
            destination=destination,
        )

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        replacements = {
            "envsolve_harness.codex.container_mcp": (
                "envsolve_harness.codex.container_mcp_qualified"
            ),
            "envsolve_harness.codex.minimal_b_mcp": (
                "envsolve_harness.codex.minimal_b_mcp_qualified"
            ),
        }
        for index, value in enumerate(arguments):
            replacement = replacements.get(value)
            if replacement is not None:
                arguments[index] = replacement
                break
        else:
            raise RuntimeError("Qualified runner could not identify its MCP module")
        return arguments

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        metadata["infrastructure_profile"] = self.infrastructure_profile


class QualifiedCodexCliRunner(QualifiedCodexInfrastructureMixin, CodexCliRunner):
    runner_name = "codex-cli-qualified"
    runner_version = "1.0.0"


class QualifiedEnvSolveProMinimalBRunner(
    QualifiedCodexInfrastructureMixin,
    EnvSolveProMinimalBRunner,
):
    runner_name = "envsolve-pro-minimal-b-qualified"
    runner_version = "1.0.0"
