from __future__ import annotations

from typing import Any

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import CandidateValidation, DeploymentCandidate
from envsolve_harness.boundary_v6 import (
    OPEN_PROGRAM_POLICY,
    REPOSITORY_POLICY,
    BoundaryV6MinimalBExecutableGoalVerifier,
    BoundaryV6OpenCandidateProgramValidator,
    install_boundary_v6_local_distribution_audit,
)
from envsolve_harness.codex.minimal_b_mcp import CleanReplayService
from envsolve_harness.core.io import read_jsonl, write_json
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.runners.certification_repair_boundary_v5 import (
    BoundaryV5QualifiedCodexCliRunner,
    BoundaryV5QualifiedMinimalBRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file


CONTROL_METHOD = "codex-cli-goal-aware-boundary-v6"
MINIMAL_B_METHOD = "envsolve-pro-minimal-b-boundary-v6"


class _BoundaryV6MetadataMixin:
    boundary_version = "open-operation-boundary-v6.0.1"

    def _candidate_prompt_contract(self) -> str:
        return BoundaryV6OpenCandidateProgramValidator.prompt_contract

    def _submission_scope_prompt(self) -> str:
        return (
            "The script must not edit tracked repository source or configuration; "
            "repository-local build outputs and local deployment configuration are "
            "governed by the shared candidate contract below."
        )

    def _validate_bootstrap(self, script: str) -> CandidateValidation:
        return BoundaryV6OpenCandidateProgramValidator().validate(
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
            "operation_space": "open",
            "import_artifact_disposition": (
                "postepisode-executable-source-review"
            ),
        }

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
            == "minimal-b-executable-goal-contract-boundary-v6"
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
                        "detail": "boundary-v6 qualification requires a goal contract",
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
        install_boundary_v6_local_distribution_audit()
        verifier = BoundaryV6MinimalBExecutableGoalVerifier(
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
        service.validator = BoundaryV6OpenCandidateProgramValidator()
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


class BoundaryV6QualifiedCodexCliRunner(
    _BoundaryV6MetadataMixin,
    BoundaryV5QualifiedCodexCliRunner,
):
    runner_name = "codex-cli-qualified-boundary-v6"
    runner_version = "6.0.1"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == CONTROL_METHOD else None


class BoundaryV6QualifiedMinimalBRunner(
    _BoundaryV6MetadataMixin,
    BoundaryV5QualifiedMinimalBRunner,
):
    runner_name = "envsolve-pro-minimal-b-qualified-boundary-v6"
    runner_version = "6.0.1"

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        prompt = super()._prompt(case, goal_contract)
        old = """\
The shared admissibility boundary rejects candidate-generated compatibility packages,
local distributions that expose modules absent from the repository, unowned import
artifacts, and deletion or falsification of installation metadata. Do not create a
module or stub solely to silence a missing-import finding.
"""
        replacement = """\
The shared v6 boundary leaves deployment operations open. New nonempty import
artifacts are recorded for blinded post-episode executable-source review; empty
files, empty namespace shims, tracked-state mutation, and import-path symlink
injection remain invalid. Do not create an artifact solely to game the public goal.
"""
        if goal_contract is None:
            return prompt
        if prompt.count(old) != 1:
            raise RuntimeError("Boundary v6 could not replace the Minimal B boundary")
        return prompt.replace(old, replacement, 1)

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == MINIMAL_B_METHOD else None

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        for index, value in enumerate(arguments):
            if value == "envsolve_harness.codex.minimal_b_mcp_boundary_v5_qualified":
                arguments[index] = (
                    "envsolve_harness.codex.minimal_b_mcp_boundary_v6_qualified"
                )
                break
        else:
            raise RuntimeError("Boundary v6 could not identify Minimal B MCP module")
        return arguments
