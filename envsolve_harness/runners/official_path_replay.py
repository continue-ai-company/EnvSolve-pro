from __future__ import annotations

from pathlib import Path
from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.codex.envbench_replay_mcp import EXECUTOR_PROFILE
from envsolve_harness.core.io import read_jsonl
from envsolve_harness.core.models import Case
from envsolve_harness.runners.codex_cli import CodexCliRunner
from envsolve_harness.runners.remote_boundary_v6 import (
    RemoteBoundaryV6QualifiedMinimalBRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file


class RemoteOfficialPathMinimalBRunner(RemoteBoundaryV6QualifiedMinimalBRunner):
    """Same active Agent session with complete-program EnvBench-path replay."""

    runner_name = "envsolve-pro-minimal-b-official-path-remote"
    runner_version = "1.0.0"
    agent_interface = "continuous-agent+online-envbench-path-replay-mcp-v1"

    def __init__(
        self,
        *,
        local_envbench_root: Path,
        remote_envbench_root: str,
        remote_evaluation_root: str,
        evaluation_process_timeout: int,
        evaluation_container_timeout: int,
        evaluation_max_workers: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.local_envbench_root = local_envbench_root.resolve()
        self.remote_envbench_root = remote_envbench_root
        self.remote_evaluation_root = remote_evaluation_root
        self.evaluation_process_timeout = evaluation_process_timeout
        self.evaluation_container_timeout = evaluation_container_timeout
        self.evaluation_max_workers = evaluation_max_workers

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
You have one additional EnvSolve-Pro operation in this same active session.
Before returning the final JSON, call `submit_and_replay` with the complete
self-contained bootstrap program. It executes the program from a clean checkout
through the same EnvBench candidate-execution path used after the episode and
returns public target-state execution feedback to this session.

You may call `submit_and_replay` repeatedly. If it fails, use the returned
bootstrap and missing-import observations to repair the complete program and
submit again. Return a `bootstrap_script` only after those exact program bytes
receive `status=pass` and `certified=true`. The terminal postepisode result is
still unavailable to you.
"""
        )

    def _mcp_server_args(
        self,
        *,
        trace_path: Path,
        container_id: str,
        case: Case | None,
        image_digest: str | None,
    ) -> list[str]:
        if case is None:
            raise ValueError("Official-path replay requires case identity")
        if image_digest is None:
            raise ValueError("Official-path replay requires a pinned image")
        if self.goal_contract is None:
            raise ValueError("Official-path replay requires a public goal contract")
        root = self._minimal_b_root(trace_path)
        arguments = [
            "-m",
            "envsolve_harness.codex.envbench_replay_mcp",
            "--container-id",
            container_id,
            "--workdir",
            "/data/project",
            "--command-trace",
            str(trace_path),
            "--replay-trace",
            str(root / "replays.jsonl"),
            "--certification",
            str(root / "certification.json"),
            "--programs-root",
            str(root / "programs"),
            "--repository",
            case.repository,
            "--revision",
            case.revision,
            "--case-id",
            case.case_id,
            "--image",
            image_digest,
            "--goal-contract-sha256",
            self.goal_contract.sha256,
            "--local-envbench-root",
            str(self.local_envbench_root),
            "--remote-envbench-root",
            self.remote_envbench_root,
            "--remote-evaluation-root",
            self.remote_evaluation_root,
            "--process-timeout",
            str(self.evaluation_process_timeout),
            "--container-timeout",
            str(self.evaluation_container_timeout),
            "--container-create-timeout",
            str(self.container_create_timeout),
            "--git-fetch-timeout",
            str(self.git_fetch_timeout),
            "--max-workers",
            str(self.evaluation_max_workers),
            "--command-timeout",
            str(self.command_timeout),
            "--max-output-chars",
            "16000",
            "--ssh-target",
            self.transport.target,
            "--remote-workspace-root",
            self.transport.remote_root,
            "--ssh-executable",
            self.transport.ssh_executable,
            "--docker",
            self.transport.docker_executable,
        ]
        if self.transport.ssh_identity is not None:
            arguments.extend(["--ssh-identity", self.transport.ssh_identity])
        if self.transport.ssh_port is not None:
            arguments.extend(["--ssh-port", str(self.transport.ssh_port)])
        return arguments

    def _mcp_tool_timeout_seconds(self) -> int:
        return self.evaluation_process_timeout + 120

    def _certificate_integrity(
        self,
        script: str,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        del script
        minimal_b = metadata.get("minimal_b")
        if not isinstance(minimal_b, dict):
            return None
        certificate = minimal_b.get("accepted_certificate")
        final_digest = minimal_b.get("final_program_sha256")
        if not isinstance(certificate, dict) or not isinstance(final_digest, str):
            return None
        replay_path = artifacts.generation_dir / "minimal-b" / "replays.jsonl"
        records = read_jsonl(replay_path) if replay_path.is_file() else []
        matching = [
            record
            for record in records
            if record.get("replay_id") == certificate.get("replay_id")
            and record.get("program_sha256") == final_digest
            and record.get("status") == "pass"
            and record.get("certified") is True
            and record.get("executor_profile") == EXECUTOR_PROFILE
        ]
        if not matching:
            return None
        return {
            "policy": "envbench-official-path-public-goal-v1",
            "valid": True,
            "qualification": "matching-in-session-envbench-path-replay",
            "program_sha256": final_digest,
            "replay_id": certificate.get("replay_id"),
            "replay_trace_sha256": sha256_file(replay_path),
            "violations": [],
        }

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        minimal_b = metadata.get("minimal_b")
        if isinstance(minimal_b, dict):
            minimal_b.update(
                {
                    "feedback_returned_to_agent": True,
                    "replay_executor_profile": EXECUTOR_PROFILE,
                    "replay_execution_backend": "ssh-remote-envbench",
                }
            )
