from __future__ import annotations

from typing import Any

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve_harness.boundary_v6 import (
    REPOSITORY_POLICY,
    BoundaryV6OfficialAlignedExecutableGoalVerifier,
    BoundaryV6OpenCandidateProgramValidator,
)
from envsolve_harness.codex.minimal_b_mcp import CleanReplayService
from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.execution.remote_docker import RemoteDockerCommandAdapter
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.runners.certification_repair_boundary_v6 import (
    MINIMAL_B_METHOD,
    BoundaryV6QualifiedMinimalBRunner,
    _BoundaryV6MetadataMixin,
)
from envsolve_harness.runners.certification_repair_boundary_v5 import (
    BoundaryV5QualifiedMinimalBRunner,
)
from envsolve_harness.runners.remote_boundary_v5 import (
    RemoteBoundaryV5QualifiedCodexCliRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file


class RemoteBoundaryV6QualifiedCodexCliRunner(
    _BoundaryV6MetadataMixin,
    RemoteBoundaryV5QualifiedCodexCliRunner,
):
    runner_name = "codex-cli-qualified-boundary-v6-remote-docker"
    runner_version = "6.0.1+remote.1"

    def _submission_verifier(
        self,
        *,
        case: Case,
        artifacts: RunArtifacts,
        adapter: RemoteDockerCommandAdapter,
    ) -> BoundaryV6OfficialAlignedExecutableGoalVerifier:
        if self.goal_contract is None:
            raise ValueError("submission verifier requires a public goal contract")
        return BoundaryV6OfficialAlignedExecutableGoalVerifier(
            self.goal_contract,
            observation_timeout=self.command_timeout,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                case.revision,
                required_preconditions=self.workspace_preconditions,
            ),
            run_command=adapter,
        )

    def _nonfeedback_submission_qualification(
        self,
        script: str,
        case: Case,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if self.goal_contract is None:
            return _BoundaryV6MetadataMixin._nonfeedback_submission_qualification(
                self,
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
        verifier = self._submission_verifier(
            case=case,
            artifacts=artifacts,
            adapter=adapter,
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
        service.validator = BoundaryV6OpenCandidateProgramValidator()
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


class OfficialPrimaryRemoteBoundaryV6CodexCliRunner(
    RemoteBoundaryV6QualifiedCodexCliRunner
):
    runner_name = "codex-cli-boundary-v6-official-primary-remote-docker"
    runner_version = "1.0.0"

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
            submission.get("bootstrap_script"), str
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
            + "\n[official-primary-v6]\n"
            + "Preserved advisory qualification and emitted the completed, "
            + "safety-admissible submission for Official evaluation.\n",
        )


class RemoteBoundaryV6QualifiedMinimalBRunner(
    RemoteBoundaryV6QualifiedCodexCliRunner,
    BoundaryV6QualifiedMinimalBRunner,
):
    runner_name = "envsolve-pro-minimal-b-boundary-v6-remote-docker"
    runner_version = "1.0.0"

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
            and record.get("verification", {}).get("check_profile")
            == "official-aligned-executable-goal-boundary-v6-v1"
        ]
        if not matching:
            return None
        return {
            "policy": REPOSITORY_POLICY,
            "valid": True,
            "qualification": "matching-in-session-fresh-replay-certificate",
            "program_sha256": final_digest,
            "replay_id": certificate.get("replay_id"),
            "replay_trace_sha256": sha256_file(replay_path),
            "violations": [],
        }

    def _goal_contract_for_run(self, run_spec: RunSpec):  # type: ignore[no-untyped-def]
        return self.goal_contract if run_spec.method == MINIMAL_B_METHOD else None

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = BoundaryV5QualifiedMinimalBRunner._mcp_server_args(
            self, **kwargs
        )
        module_index = arguments.index(
            "envsolve_harness.codex.minimal_b_mcp_boundary_v5_qualified"
        )
        arguments[module_index] = (
            "envsolve_harness.codex.remote_minimal_b_mcp_boundary_v6"
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
