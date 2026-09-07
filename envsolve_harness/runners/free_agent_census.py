from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.core.models import Case

from envsolve_harness.runners.v7_persistent_codex import V7PersistentP0RemoteCodexRunner


class FreeAgentCensusRunner(V7PersistentP0RemoteCodexRunner):
    runner_name = "free-agent-voluntary-environments-remote"
    runner_version = "1.0.2"
    agent_interface = (
        "native-codex-agent+ssh-remote-container-terminal-and-voluntary-"
        "clean-environment-mcp-v1"
    )

    def _acquire_repository(self, case: Case, destination: Path) -> dict[str, Any]:
        receipt = super()._acquire_repository(case, destination)
        self._fresh_source_cache = receipt["cache_path"]
        return receipt

    def _mcp_tool_names(self) -> tuple[str, ...]:
        return ("envbench_shell", "envbench_environment")

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        case = kwargs.get("case")
        image_digest = kwargs.get("image_digest")
        if not isinstance(case, Case) or not isinstance(image_digest, str):
            raise ValueError("A concrete case and image digest are required")
        if not hasattr(self, "_fresh_source_cache"):
            raise RuntimeError("Repository must be acquired before MCP setup")
        args = super()._mcp_server_args(**kwargs)
        args += [
            "--fresh-source-cache",
            self._fresh_source_cache,
            "--fresh-revision",
            case.revision,
            "--fresh-image",
            image_digest,
            "--fresh-root",
            self.transport.workspace_path(
                Path(kwargs["trace_path"]), "free-environments"
            ),
            "--fresh-workspace-dirs",
            json.dumps([p.path for p in self.workspace_preconditions]),
            "--container-create-timeout",
            str(self.container_create_timeout),
        ]
        if self.expose_gpus:
            args.append("--expose-gpus")
        return args

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        return super()._prompt(case, goal_contract) + """

You also have envsolve_container.envbench_environment to create and close
independent fresh containers with the original repository revision and base image.
Use envbench_shell with the returned environment_id to run arbitrary commands
there, including any complete setup program or diagnostic you choose. Omit
environment_id to use the original construction container. Files, packages and
shell variables are not copied from construction to a newly created environment.
These tools return raw command results; they do not run a verifier automatically.
Whether and when to use additional environments is your choice. No successful
replay certificate is required for submission. Close environments when finished.
"""
