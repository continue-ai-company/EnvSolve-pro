from __future__ import annotations

from typing import Any

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import CandidateValidation, DeploymentCandidate
from envsolve_harness.boundary_v3 import (
    BoundaryV3MinimalBExecutableGoalVerifier,
    BoundaryV3OpenCandidateProgramValidator,
    OPEN_PROGRAM_POLICY,
    REPOSITORY_POLICY,
    install_boundary_v3_local_distribution_audit,
)
from envsolve_harness.codex.minimal_b_mcp import CleanReplayService
from envsolve_harness.core.io import (
    read_json,
    read_jsonl,
    write_json,
    write_text_atomic,
)
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.runners.codex_cli import codex_validation_metadata
from envsolve_harness.runners.certification_repair_boundary_v2 import (
    BoundaryV2QualifiedCodexCliRunner,
    BoundaryV2QualifiedMinimalBRunner,
    BoundaryV2QualifiedOneShotRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file


CONTROL_METHOD = "codex-cli-goal-aware-boundary-v3"
ONE_SHOT_METHOD = "envsolve-pro-one-shot-certification-boundary-v3"
MINIMAL_B_METHOD = "envsolve-pro-minimal-b-boundary-v3"


class _BoundaryV3MetadataMixin:
    boundary_version = "certification-repair-boundary-v3"

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        prompt = super()._prompt(case, goal_contract)
        legacy = BoundaryV3OpenCandidateProgramValidator.__mro__[1].prompt_contract
        if prompt.count(legacy) != 1:
            raise RuntimeError("Boundary v3 could not replace the candidate contract")
        return prompt.replace(
            legacy,
            BoundaryV3OpenCandidateProgramValidator.prompt_contract,
            1,
        )

    def _validate_bootstrap(self, script: str) -> CandidateValidation:
        return BoundaryV3OpenCandidateProgramValidator().validate(
            DeploymentCandidate(
                candidate_id="codex-bootstrap",
                script=script,
                rationale="Codex CLI final bootstrap submission",
            )
        )

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        metadata["admissibility_boundary"] = {
            "version": self.boundary_version,
            "trusted_goal_shell": "noninterfering-privileged-bash",
            "repository_policy": REPOSITORY_POLICY,
            "candidate_policy": OPEN_PROGRAM_POLICY,
            "audited_object": "submitted-program-fresh-execution-state",
            "construction_workspace_role": "trajectory-only",
        }

    def _certificate_integrity(
        self,
        script: str,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
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
            == "minimal-b-executable-goal-contract-boundary-v3"
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

    def _nonfeedback_submission_qualification(
        self,
        script: str,
        case: Case,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if self.goal_contract is None:
            return {
                "policy": REPOSITORY_POLICY,
                "valid": False,
                "qualification": "missing-public-goal-contract",
                "violations": [
                    {
                        "kind": "qualification_configuration",
                        "path": None,
                        "detail": "boundary-v3 qualification requires a goal contract",
                    }
                ],
            }
        root = artifacts.generation_dir / "submission-qualification"
        provider = DockerFreshEnvironmentProvider(
            source_repository=artifacts.generation_dir / "workspace",
            worktrees_root=root / "worktrees",
            repository=case.repository,
            revision=case.revision,
            image=str(metadata["image_digest"]),
            workspace_preconditions=self.workspace_preconditions,
            create_timeout=self.container_create_timeout,
        )
        install_boundary_v3_local_distribution_audit()
        verifier = BoundaryV3MinimalBExecutableGoalVerifier(
            self.goal_contract,
            observation_timeout=self.command_timeout,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                case.revision,
                required_preconditions=self.workspace_preconditions,
            ),
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
        service.validator = BoundaryV3OpenCandidateProgramValidator()
        result = service.submit(script)
        result_path = root / "result.json"
        write_json(result_path, result)
        metadata["submission_qualification"] = {
            "feedback_returned_to_agent": False,
            "result_path": str(result_path.relative_to(artifacts.root)),
            "result_sha256": sha256_file(result_path),
            "status": result.get("status"),
            "certified": result.get("certified") is True,
        }
        valid = result.get("status") == "pass" and result.get("certified") is True
        return {
            "policy": REPOSITORY_POLICY,
            "valid": valid,
            "qualification": "post-session-fresh-replay-without-agent-feedback",
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

    def _qualify_submission_integrity(
        self,
        script: str,
        case: Case,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        certificate = self._certificate_integrity(script, artifacts, metadata)
        if certificate is not None:
            return certificate
        return self._nonfeedback_submission_qualification(
            script,
            case,
            artifacts,
            metadata,
        )

    def _finish_boundary_v3_recovery(
        self,
        artifacts: RunArtifacts,
        result: SolverResult,
        note: str,
    ) -> SolverResult:
        previous_log = (
            artifacts.solver_log.read_text(encoding="utf-8")
            if artifacts.solver_log.is_file()
            else ""
        )
        return self._finish(
            artifacts,
            result,
            previous_log + "\n[boundary-v3]\n" + note + "\n",
        )

    def run(
        self,
        case: Case,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        initial = super().run(case, artifacts, run_spec)
        construction_rejected = (
            not initial.generation_completed
            and str(initial.error).startswith(
                "RuntimeError: Codex CLI repository integrity failed:"
            )
        )
        if not initial.generation_completed and not construction_rejected:
            return initial

        metadata = dict(initial.metadata)
        output_path = artifacts.generation_dir / "codex-control" / "final-output.json"
        if not output_path.is_file():
            return initial
        submission = read_json(output_path)
        if not isinstance(submission, dict) or not isinstance(
            submission.get("bootstrap_script"),
            str,
        ):
            return initial
        script = submission["bootstrap_script"].strip()
        validation = self._validate_bootstrap(script)
        metadata["candidate_validation"] = codex_validation_metadata(validation)
        metadata["construction_workspace_integrity"] = metadata.pop(
            "repository_integrity",
            {},
        )
        if not validation.accepted:
            failed = SolverResult(
                False,
                run_spec.method,
                trajectory_path=initial.trajectory_path,
                error=(
                    "RuntimeError: Boundary v3 candidate validation failed: "
                    f"{validation.reason}"
                ),
                metadata={**metadata, "finished_at": self._now()},
            )
            return self._finish_boundary_v3_recovery(
                artifacts,
                failed,
                str(failed.error),
            )

        script = (validation.normalized_script or script).strip()
        try:
            self._validate_additional_submission(script, artifacts, metadata)
            integrity = self._qualify_submission_integrity(
                script,
                case,
                artifacts,
                metadata,
            )
            metadata["repository_integrity"] = integrity
            if integrity.get("valid") is not True:
                raise RuntimeError(
                    "submitted program integrity failed: "
                    f"{integrity.get('violations', [])}"
                )
        except (OSError, RuntimeError, ValueError) as exc:
            failed = SolverResult(
                False,
                run_spec.method,
                trajectory_path=initial.trajectory_path,
                error=f"{type(exc).__name__}: {exc}",
                metadata={**metadata, "finished_at": self._now()},
            )
            return self._finish_boundary_v3_recovery(
                artifacts,
                failed,
                str(failed.error),
            )

        write_text_atomic(artifacts.generated_script, script + "\n")
        recovered = SolverResult(
            True,
            run_spec.method,
            script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
            trajectory_path=initial.trajectory_path,
            metadata={**metadata, "finished_at": self._now()},
        )
        return self._finish_boundary_v3_recovery(
            artifacts,
            recovered,
            (
                "Qualified the submitted program in fresh state; construction "
                "residue is trajectory-only."
            ),
        )


class BoundaryV3QualifiedCodexCliRunner(
    _BoundaryV3MetadataMixin,
    BoundaryV2QualifiedCodexCliRunner,
):
    runner_name = "codex-cli-qualified-boundary-v3"
    runner_version = "3.0.0"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == CONTROL_METHOD else None


class BoundaryV3QualifiedOneShotRunner(
    _BoundaryV3MetadataMixin,
    BoundaryV2QualifiedOneShotRunner,
):
    runner_name = "envsolve-pro-one-shot-certification-qualified-boundary-v3"
    runner_version = "3.0.0"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == ONE_SHOT_METHOD else None

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        for index, value in enumerate(arguments):
            if value == (
                "envsolve_harness.codex.one_shot_mcp_boundary_v2_qualified"
            ):
                arguments[index] = (
                    "envsolve_harness.codex."
                    "one_shot_mcp_boundary_v3_qualified"
                )
                break
        else:
            raise RuntimeError("Boundary v3 could not identify one-shot MCP module")
        return arguments


class BoundaryV3QualifiedMinimalBRunner(
    _BoundaryV3MetadataMixin,
    BoundaryV2QualifiedMinimalBRunner,
):
    runner_name = "envsolve-pro-minimal-b-qualified-boundary-v3"
    runner_version = "3.0.0"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == MINIMAL_B_METHOD else None

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        for index, value in enumerate(arguments):
            if value == (
                "envsolve_harness.codex.minimal_b_mcp_boundary_v2_qualified"
            ):
                arguments[index] = (
                    "envsolve_harness.codex."
                    "minimal_b_mcp_boundary_v3_qualified"
                )
                break
        else:
            raise RuntimeError("Boundary v3 could not identify Minimal B MCP module")
        return arguments
