from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from envsolve.constraints import ConstraintEngine, InitialConstraintEvidence
from envsolve.solver import (
    CandidateOperationGuard,
    CandidateValidator,
    CounterexampleGuidedDeploymentLoop,
    DeploymentPolicy,
    EpisodeBudget,
    ExecutableVerifier,
    FreshEnvironmentProvider,
    ImmutableArtifactStore,
    SolverStateSession,
)
from envsolve_harness.core.io import read_json, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest


class EnvSolveEpisodeRunner:
    """Benchmark-independent runner for one frozen EnvSolve online episode."""

    def __init__(
        self,
        *,
        policy: DeploymentPolicy,
        environment_provider: FreshEnvironmentProvider,
        verifier: ExecutableVerifier,
        candidate_validator: CandidateValidator,
        operation_guard: CandidateOperationGuard | None = None,
        budget: EpisodeBudget,
        max_candidates: int,
        retain_admissible_candidate: bool = True,
        condition: str = "envsolve-full",
        repository_profile: dict[str, Any] | None = None,
        initial_evidence: tuple[InitialConstraintEvidence, ...] = (),
        initial_observation_summary: dict[str, Any] | None = None,
    ) -> None:
        if max_candidates <= 0:
            raise ValueError("EnvSolve episode candidate budget must be positive")
        if not condition.strip():
            raise ValueError("EnvSolve episode condition cannot be empty")
        self.policy = policy
        self.environment_provider = environment_provider
        self.verifier = verifier
        self.candidate_validator = candidate_validator
        self.operation_guard = operation_guard
        self.budget = budget
        self.max_candidates = max_candidates
        self.retain_admissible_candidate = retain_admissible_candidate
        self.condition = condition
        self.repository_profile = repository_profile
        self.initial_evidence = initial_evidence
        self.initial_observation_summary = initial_observation_summary

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def run(
        self,
        case: Case,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        started_at = self._now()
        write_json(artifacts.status, {"state": "generating", "updated_at": started_at})
        metadata: dict[str, Any] = {
            "runner": "envsolve-episode",
            "runner_version": "0.3.0",
            "condition": self.condition,
            "started_at": started_at,
            "online_feedback_policy": "internal-execution-only",
            "official_evaluator_access": "post-episode-only",
            "candidate_retention": (
                "best-admissible"
                if self.retain_admissible_candidate
                else "disabled"
            ),
        }
        if self.initial_observation_summary is not None:
            metadata["initial_repository_observation"] = self.initial_observation_summary
        try:
            session = SolverStateSession(
                artifacts.episode_event_log,
                artifacts.episode_snapshot,
                case.to_dict(),
                artifact_store=ImmutableArtifactStore(artifacts.raw_artifacts),
                run_id=run_spec.run_id,
                episode_id=f"{run_spec.run_id}:{case.case_id}",
            )
            if self.repository_profile is not None and not session.reconstruct().repository_profile:
                session.profile_repository(self.repository_profile)
            constraint_engine = ConstraintEngine()
            admitted_constraints: list[str] = []
            for item in self.initial_evidence:
                state = session.reconstruct()
                existing = state.evidence.get(item.evidence_id)
                if existing is None:
                    session.record_evidence(
                        kind=item.kind,
                        source=item.source,
                        value=item.value,
                        confidence=item.confidence,
                        evidence_id=item.evidence_id,
                    )
                elif any(
                    existing.get(key) != value
                    for key, value in {
                        "kind": item.kind,
                        "source": item.source,
                        "value": item.value,
                        "confidence": item.confidence,
                    }.items()
                ):
                    raise ValueError(
                        f"Initial evidence identity mismatch: {item.evidence_id}"
                    )
                admitted_constraints.extend(
                    constraint_engine.ingest_evidence(session, item.evidence_id)
                )
            constraint_engine.propagate_constraints(session)
            metadata["initial_constraint_admission"] = {
                "evidence_count": len(self.initial_evidence),
                "constraint_count": len(set(admitted_constraints)),
            }
            loop = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=self.max_candidates,
                candidate_validator=self.candidate_validator,
                budget=self.budget,
                constraint_engine=constraint_engine,
                operation_guard=self.operation_guard,
                retain_admissible_candidate=self.retain_admissible_candidate,
            )
            loop_result = loop.run(
                self.policy,
                self.environment_provider,
                self.verifier,
            )
            metadata["episode"] = loop_result.to_dict()
            if loop_result.accepted_candidate is None:
                result = SolverResult(
                    generation_completed=False,
                    method=run_spec.method,
                    trajectory_path=str(
                        artifacts.episode_event_log.relative_to(artifacts.root)
                    ),
                    error=loop_result.stop_reason,
                    metadata=metadata,
                )
            else:
                write_text_atomic(
                    artifacts.generated_script,
                    loop_result.accepted_candidate.script,
                )
                metadata["candidate_output"] = {
                    "certification": loop_result.candidate_certification,
                    "internal_goal_status": loop_result.goal_status,
                    "assessment": (
                        loop_result.candidate_assessment.to_dict()
                        if loop_result.candidate_assessment is not None
                        else None
                    ),
                }
                result = SolverResult(
                    generation_completed=True,
                    method=run_spec.method,
                    script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
                    trajectory_path=str(
                        artifacts.episode_event_log.relative_to(artifacts.root)
                    ),
                    metadata=metadata,
                )
        except Exception as exc:
            result = SolverResult(
                generation_completed=False,
                method=run_spec.method,
                trajectory_path=(
                    str(artifacts.episode_event_log.relative_to(artifacts.root))
                    if artifacts.episode_event_log.is_file()
                    else None
                ),
                error=f"{type(exc).__name__}: {exc}",
                metadata=metadata,
            )

        finalize_budget = getattr(self.budget, "finalize", None)
        if callable(finalize_budget):
            try:
                finalize_budget()
            except Exception as exc:
                result = SolverResult(
                    generation_completed=False,
                    method=run_spec.method,
                    trajectory_path=result.trajectory_path,
                    error=f"Budget finalization failed: {type(exc).__name__}: {exc}",
                    metadata=result.metadata,
                )
        ledger_path = getattr(self.budget, "path", None)
        if isinstance(ledger_path, Path) and ledger_path.is_file():
            result.metadata["online_budget"] = read_json(ledger_path)
            result.metadata["audit_requirements"] = {"online_budget": True}
        result.metadata["finished_at"] = self._now()
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(
            artifacts.solver_log,
            result.error or "EnvSolve episode completed successfully.\n",
        )
        if artifacts.manifest.is_file():
            update_manifest(artifacts, solver=result.to_dict())
        write_json(
            artifacts.status,
            {
                "state": "generated" if result.generation_completed else "failed",
                "updated_at": self._now(),
            },
        )
        return result
