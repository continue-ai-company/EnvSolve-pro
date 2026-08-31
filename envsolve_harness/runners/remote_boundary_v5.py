from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve_harness.boundary_v5 import (
    REPOSITORY_POLICY,
    BoundaryV5MinimalBExecutableGoalVerifier,
    BoundaryV5OpenCandidateProgramValidator,
    install_boundary_v5_local_distribution_audit,
)
from envsolve_harness.codex.minimal_b_mcp import CleanReplayService
from envsolve_harness.core.io import read_json, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.execution.remote_docker import (
    RemoteExactRevisionSourceCache,
    RemoteDockerCommandAdapter,
    SshDockerTransport,
    untracked_rebuildable_excludes,
)
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.runners.certification_repair_boundary_v5 import (
    MINIMAL_B_METHOD,
    BoundaryV5QualifiedCodexCliRunner,
    BoundaryV5QualifiedMinimalBRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file


class RemoteBoundaryV5QualifiedCodexCliRunner(BoundaryV5QualifiedCodexCliRunner):
    """Keep Codex local while every deployment command executes on an SSH host."""

    runner_name = "codex-cli-qualified-boundary-v5-remote-docker"
    runner_version = "5.0.1+remote.3"
    infrastructure_profile = "codex-qualified-ssh-remote-docker-v1"
    agent_interface = "native-codex-agent+ssh-remote-container-terminal-mcp-v1"

    def __init__(
        self,
        *,
        ssh_target: str,
        remote_workspace_root: str,
        expose_gpus: bool = False,
        ssh_executable: str | None = None,
        rsync_executable: str | None = None,
        docker_executable: str = "docker",
        ssh_identity: str | None = None,
        ssh_port: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.expose_gpus = expose_gpus
        self.transport = SshDockerTransport(
            target=ssh_target,
            remote_root=remote_workspace_root,
            ssh_executable=ssh_executable or shutil.which("ssh") or "ssh",
            rsync_executable=rsync_executable or shutil.which("rsync") or "rsync",
            docker_executable=docker_executable,
            ssh_identity=ssh_identity,
            ssh_port=ssh_port,
        )
        self._generation_remote_path: str | None = None
        self._generation_local_path: Path | None = None
        self._generation_container_id: str | None = None
        self._remote_owner: str | None = None
        self._remote_source_paths: dict[Path, str] = {}

    def _acquire_repository(self, case: Case, destination: Path) -> dict[str, Any]:
        acquisition = RemoteExactRevisionSourceCache(
            self.transport,
            self.git_fetch_timeout,
        ).acquire(
            repository=case.repository,
            revision=case.revision,
            destination=destination,
        )
        self._remote_source_paths[destination.resolve()] = str(
            acquisition["remote_checkout_path"]
        )
        return acquisition

    def _host_owner(self) -> str:
        if self._remote_owner is None:
            uid = self.transport.checked_remote(
                ["id", "-u"],
                timeout=self.container_create_timeout,
            )
            gid = self.transport.checked_remote(
                ["id", "-g"],
                timeout=self.container_create_timeout,
            )
            self._remote_owner = f"{uid}:{gid}"
        return self._remote_owner

    def _image_digest(self) -> str:
        inspect = ["image", "inspect", "--format", "{{.Id}}", self.image]
        try:
            return self.transport.checked_docker(
                inspect,
                timeout=self.container_create_timeout,
            )
        except RuntimeError:
            self.transport.checked_docker(
                ["pull", self.image],
                timeout=max(self.container_create_timeout, 900),
            )
            return self.transport.checked_docker(
                inspect,
                timeout=self.container_create_timeout,
            )

    def _create_container(self, workspace: Path, image_digest: str) -> str:
        remote_path = self._remote_source_paths.pop(
            workspace.resolve(),
            self.transport.workspace_path(workspace, "generation"),
        )
        self.transport.sync_to_remote(
            workspace,
            remote_path,
            timeout=max(self.git_fetch_timeout, self.container_create_timeout),
        )
        command = [
            "create",
            "--init",
            "--entrypoint",
            "/bin/bash",
            "--mount",
            f"type=bind,src={remote_path},dst=/data/project",
            "--workdir",
            "/data/project",
            image_digest,
            "-lc",
            "while true; do sleep 1000; done",
        ]
        if self.expose_gpus:
            command[1:1] = ["--gpus", "all"]
        container_id = self.transport.checked_docker(
            command,
            timeout=self.container_create_timeout,
        )
        try:
            self.transport.checked_docker(
                ["start", container_id],
                timeout=self.container_create_timeout,
            )
            if self.transport.requires_bind_mount_chown(
                timeout=self.container_create_timeout
            ):
                self.transport.checked_docker(
                    [
                        "exec",
                        "--user",
                        "0:0",
                        container_id,
                        "chown",
                        "-R",
                        "0:0",
                        "/data/project",
                    ],
                    timeout=self.container_create_timeout,
                )
        except Exception:
            self.transport.run_docker(
                ["rm", "-f", container_id],
                capture_output=True,
                text=True,
                check=False,
            )
            raise
        self._generation_remote_path = remote_path
        self._generation_local_path = workspace
        self._generation_container_id = container_id
        return container_id

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        module_index = arguments.index(
            "envsolve_harness.codex.container_mcp_qualified"
        )
        arguments[module_index] = "envsolve_harness.codex.remote_container_mcp"
        docker_index = arguments.index("--docker")
        del arguments[docker_index : docker_index + 2]
        arguments.extend(
            [
                "--ssh-target",
                self.transport.target,
                "--ssh-executable",
                self.transport.ssh_executable,
                "--docker",
                self.transport.docker_executable,
            ]
        )
        if self.transport.ssh_identity is not None:
            arguments.extend(["--ssh-identity", self.transport.ssh_identity])
        if self.transport.ssh_port is not None:
            arguments.extend(["--ssh-port", str(self.transport.ssh_port)])
        return arguments

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        if self._generation_remote_path is None or self._generation_local_path is None:
            raise RuntimeError("Remote generation workspace was not initialized")
        if self._generation_container_id is None:
            raise RuntimeError("Remote generation container was not initialized")
        translate_ownership = self.transport.requires_bind_mount_chown(
            timeout=self.container_create_timeout
        )
        if translate_ownership:
            self.transport.checked_docker(
                [
                    "exec",
                    "--user",
                    "0:0",
                    self._generation_container_id,
                    "chown",
                    "-R",
                    self._host_owner(),
                    "/data/project",
                ],
                timeout=self.container_create_timeout,
            )
        self.transport.sync_from_remote(
            self._generation_remote_path,
            self._generation_local_path,
            timeout=max(self.command_timeout, self.git_fetch_timeout),
            excludes=untracked_rebuildable_excludes(self._generation_local_path),
        )
        super()._augment_generation_metadata(artifacts, metadata)
        metadata["execution_backend"] = {
            "profile": self.infrastructure_profile,
            "ssh_target": self.transport.target,
            "workspace_transport": "rsync-exact-tree-v1",
            "transport_excludes": list(
                untracked_rebuildable_excludes(self._generation_local_path)
            ),
            "container_runtime": "remote-docker",
            "accelerator_exposure": "all" if self.expose_gpus else "none",
            "agent_host_role": "control-only",
            "execution_host_role": "generation-and-clean-replay",
            "workspace_owner_during_execution": (
                "0:0" if translate_ownership else "docker-desktop-host-user"
            ),
            "workspace_owner_during_transport": (
                self._host_owner()
                if translate_ownership
                else "docker-desktop-host-user"
            ),
        }

    def _nonfeedback_submission_qualification(
        self,
        script: str,
        case: Case,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if self.goal_contract is None:
            return super()._nonfeedback_submission_qualification(
                script,
                case,
                artifacts,
                metadata,
            )
        root = artifacts.generation_dir / "submission-qualification"
        adapter = RemoteDockerCommandAdapter(
            self.transport,
            sync_timeout=max(self.command_timeout, self.git_fetch_timeout),
            expose_gpus=self.expose_gpus,
        )
        provider = DockerFreshEnvironmentProvider(
            source_repository=artifacts.generation_dir / "workspace",
            worktrees_root=root / "worktrees",
            repository=case.repository,
            revision=case.revision,
            image=str(metadata["image_digest"]),
            workspace_preconditions=self.workspace_preconditions,
            create_timeout=self.container_create_timeout,
            run_command=adapter,
        )
        install_boundary_v5_local_distribution_audit()
        verifier = BoundaryV5MinimalBExecutableGoalVerifier(
            self.goal_contract,
            observation_timeout=self.command_timeout,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                case.revision,
                required_preconditions=self.workspace_preconditions,
            ),
            run_command=adapter,
        )
        service = CleanReplayService(
            provider=provider,
            verifier=verifier,
            repository=case.repository,
            revision=case.revision,
            image_digest=str(metadata["image_digest"]),
            goal_contract_sha256=self.goal_contract.sha256,
            trace_path=root / "replays.jsonl",
            certification_path=root / "certification.json",
            programs_root=root / "programs",
        )
        service.validator = BoundaryV5OpenCandidateProgramValidator()
        result = service.submit(script)
        result_path = root / "result.json"
        write_json(result_path, result)
        metadata["submission_qualification"] = {
            "feedback_returned_to_agent": False,
            "execution_backend": self.infrastructure_profile,
            "result_path": str(result_path.relative_to(artifacts.root)),
            "result_sha256": sha256_file(result_path),
            "status": result.get("status"),
            "certified": result.get("certified") is True,
        }
        valid = result.get("status") == "pass" and result.get("certified") is True
        return {
            "policy": REPOSITORY_POLICY,
            "valid": valid,
            "qualification": "post-session-fresh-remote-replay-without-agent-feedback",
            "program_sha256": result.get("program_sha256"),
            "replay_id": result.get("replay_id"),
            "violations": (
                []
                if valid
                else [
                    {
                        "kind": "submitted_program_qualification_failed",
                        "path": None,
                        "detail": str(
                            result.get("verification", {}).get("summary")
                            or result.get("candidate_validation", {}).get("reason")
                            or result.get("status")
                        ),
                    }
                ]
            ),
        }

    def run(
        self,
        case: Case,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        self._generation_remote_path = None
        self._generation_local_path = None
        self._generation_container_id = None
        self._remote_source_paths = {}
        try:
            return super().run(case, artifacts, run_spec)
        finally:
            if self._generation_container_id is not None:
                self.transport.run_docker(
                    ["rm", "-f", self._generation_container_id],
                    capture_output=True,
                    text=True,
                    check=False,
                )


class OfficialPrimaryRemoteBoundaryV5CodexCliRunner(
    RemoteBoundaryV5QualifiedCodexCliRunner
):
    """Submit every completed, safety-admissible Agent program to Official evaluation."""

    runner_name = "codex-cli-boundary-v5-official-primary-remote-docker"
    runner_version = "1.0.1"

    def run(
        self,
        case: Case,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        result = super().run(case, artifacts, run_spec)
        if result.generation_completed:
            return result
        metadata = dict(result.metadata)
        if metadata.get("process_exit_code") != 0 or metadata.get("timed_out") is True:
            return result
        output_path = artifacts.generation_dir / "codex-control" / "final-output.json"
        if not output_path.is_file():
            return result
        submission = read_json(output_path)
        if not isinstance(submission, dict) or not isinstance(
            submission.get("bootstrap_script"),
            str,
        ):
            return result
        script = submission["bootstrap_script"].strip()
        validation = self._validate_bootstrap(script)
        if not validation.accepted:
            return result
        script = (validation.normalized_script or script).strip()
        write_text_atomic(artifacts.generated_script, script + "\n")
        metadata["official_primary_submission"] = {
            "eligible": True,
            "qualification_is_advisory": True,
            "qualification_feedback_returned_to_agent": False,
            "source_error": result.error,
            "program_sha256": sha256_file(artifacts.generated_script),
        }
        recovered = SolverResult(
            True,
            run_spec.method,
            script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
            trajectory_path=result.trajectory_path,
            metadata={**metadata, "finished_at": self._now()},
        )
        previous_log = (
            artifacts.solver_log.read_text(encoding="utf-8")
            if artifacts.solver_log.is_file()
            else ""
        )
        return self._finish(
            artifacts,
            recovered,
            previous_log
            + "\n[official-primary]\n"
            + "Preserved advisory qualification and emitted the completed, "
            + "safety-admissible submission for Official evaluation.\n",
        )


class RemoteBoundaryV5QualifiedMinimalBRunner(
    RemoteBoundaryV5QualifiedCodexCliRunner,
    BoundaryV5QualifiedMinimalBRunner,
):
    """Keep one local Agent session while clean replays execute remotely."""

    runner_name = "envsolve-pro-minimal-b-boundary-v5-remote-docker"
    runner_version = "1.0.0"
    agent_interface = "continuous-agent+online-clean-remote-replay-mcp-v1"

    def _goal_contract_for_run(self, run_spec: RunSpec):  # type: ignore[no-untyped-def]
        return self.goal_contract if run_spec.method == MINIMAL_B_METHOD else None

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = BoundaryV5QualifiedMinimalBRunner._mcp_server_args(
            self,
            **kwargs,
        )
        module_index = arguments.index(
            "envsolve_harness.codex.minimal_b_mcp_boundary_v5_qualified"
        )
        arguments[module_index] = (
            "envsolve_harness.codex.remote_minimal_b_mcp_boundary_v5"
        )
        docker_index = arguments.index("--docker")
        del arguments[docker_index : docker_index + 2]
        arguments.extend(
            [
                "--ssh-target",
                self.transport.target,
                "--remote-workspace-root",
                self.transport.remote_root,
                "--ssh-executable",
                self.transport.ssh_executable,
                "--docker",
                self.transport.docker_executable,
            ]
        )
        if self.expose_gpus:
            arguments.append("--expose-gpus")
        if self.transport.ssh_identity is not None:
            arguments.extend(["--ssh-identity", self.transport.ssh_identity])
        if self.transport.ssh_port is not None:
            arguments.extend(["--ssh-port", str(self.transport.ssh_port)])
        return arguments

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        minimal_b = metadata.get("minimal_b")
        if isinstance(minimal_b, dict):
            minimal_b["feedback_returned_to_agent"] = True
            minimal_b["replay_execution_backend"] = self.infrastructure_profile
