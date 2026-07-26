from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import hashlib
import json
from typing import TYPE_CHECKING, Any, Protocol

from envsolve.operations import OperationGuardDecision
from envsolve.solver.loop import StopDecision
from envsolve.solver.session import ActionSpec, CommandResult, SolverStateSession
from envsolve.solver.transitions import (
    StateTransitionDisposition,
    assess_state_transition,
)
from envsolve.state import EnvironmentState

if TYPE_CHECKING:
    from envsolve.constraints.engine import ConstraintEngine


class RecoverablePolicyError(ValueError):
    """A grounded proposal failure that the policy can correct on its next turn."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "candidate-policy-output",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.details = details or {}


class EpisodeBudgetExhausted(RuntimeError):
    """A terminal online-budget signal raised across a policy boundary."""

    def __init__(self, scope: str, message: str | None = None) -> None:
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("Budget exhaustion scope cannot be empty")
        self.scope = scope
        super().__init__(message or f"Online episode budget exhausted: {scope}")


class EpisodeProviderAcquisitionFailed(RuntimeError):
    """A terminal provider-response failure after bounded acquisition attempts."""

    def __init__(self, attempts: int) -> None:
        if attempts < 1:
            raise ValueError("Provider acquisition attempts must be positive")
        self.attempts = attempts
        super().__init__(
            f"Provider response acquisition failed after {attempts} attempts"
        )


@dataclass(frozen=True)
class CounterexampleEvidence:
    kind: str
    value: Any
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("Counterexample evidence kind cannot be empty")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Counterexample confidence must be in [0, 1]")
        try:
            json.dumps(self.value, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("Counterexample evidence must be JSON serializable") from exc


@dataclass(frozen=True)
class ObservationEvidence:
    kind: str
    value: Any
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("Observation evidence kind cannot be empty")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Observation confidence must be in [0, 1]")
        try:
            json.dumps(self.value, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("Observation evidence must be JSON serializable") from exc


class FeedbackChannel(str, Enum):
    INTERNAL_EXECUTION = "internal_execution"
    POST_EPISODE_EVALUATION = "post_episode_evaluation"


@dataclass(frozen=True)
class HypothesisEvidence:
    hypothesis_id: str
    statement: str
    value: Any
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip() or not self.statement.strip():
            raise ValueError("Hypothesis evidence requires an identifier and statement")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1:
            raise ValueError("Hypothesis confidence must be in [0, 1]")
        json.dumps(self.value, ensure_ascii=True)


@dataclass(frozen=True)
class EnvironmentReceipt:
    environment_id: str
    provider_id: str
    image_digest: str
    repository: str
    revision: str
    created_at: str

    def __post_init__(self) -> None:
        values = (
            self.environment_id,
            self.provider_id,
            self.image_digest,
            self.repository,
            self.revision,
            self.created_at,
        )
        if not all(isinstance(item, str) and item.strip() for item in values):
            raise ValueError("Fresh environment receipt fields cannot be empty")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ProvisionedEnvironment:
    receipt: EnvironmentReceipt
    handle: Any = field(default=None, repr=False, compare=False)


class FreshEnvironmentProvider(Protocol):
    def provision(self, candidate: "DeploymentCandidate") -> ProvisionedEnvironment: ...

    def release(self, environment: ProvisionedEnvironment) -> None: ...


@dataclass(frozen=True)
class CandidateValidation:
    accepted: bool
    policy_id: str
    normalized_script: str | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("Candidate validation policy_id cannot be empty")
        if self.accepted and not (self.normalized_script or "").strip():
            raise ValueError("Accepted candidate validation requires a complete script")
        if not self.accepted and not (self.reason or "").strip():
            raise ValueError("Rejected candidate validation requires a reason")


class CandidateValidator(Protocol):
    def validate(self, candidate: "DeploymentCandidate") -> CandidateValidation: ...


class CandidateOperationGuard(Protocol):
    def validate(
        self,
        candidate: "DeploymentCandidate",
        state: EnvironmentState,
    ) -> OperationGuardDecision: ...


class EpisodeBudget(Protocol):
    def reserve_candidate(self, candidate_id: str) -> None: ...

    def reserve_environment(self, candidate_id: str) -> None: ...

    def reserve_command(self, candidate_id: str) -> None: ...


@dataclass(frozen=True)
class DeploymentCandidate:
    candidate_id: str
    script: str
    rationale: str
    preconditions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_candidate_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("Deployment candidate identifier cannot be empty")
        if not isinstance(self.script, str) or not self.script.strip():
            raise ValueError("Deployment candidate script cannot be empty")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("Deployment candidate rationale cannot be empty")
        if self.parent_candidate_id is not None and not self.parent_candidate_id.strip():
            raise ValueError("Deployment candidate parent identifier cannot be empty")
        if not isinstance(self.preconditions, tuple) or not all(
            isinstance(item, str) for item in self.preconditions
        ):
            raise ValueError("Deployment candidate preconditions must be strings")
        if not isinstance(self.metadata, dict):
            raise ValueError("Deployment candidate metadata must be an object")
        try:
            json.dumps(self.metadata, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("Deployment candidate metadata must be JSON serializable") from exc

    @property
    def script_sha256(self) -> str:
        return hashlib.sha256(self.script.encode("utf-8")).hexdigest()

    def action_spec(self) -> ActionSpec:
        return ActionSpec(
            action_type="deployment-candidate",
            command=self.script,
            rationale=self.rationale,
            preconditions=self.preconditions,
            action_id=self.candidate_id,
            metadata={
                "candidate_id": self.candidate_id,
                "parent_candidate_id": self.parent_candidate_id,
                **self.metadata,
            },
        )


@dataclass(frozen=True)
class CandidateAssessment:
    admissible: bool
    unresolved_constraints: int
    satisfied_constraints: int
    unknown_constraints: int
    reason: str

    def __post_init__(self) -> None:
        counts = (
            self.unresolved_constraints,
            self.satisfied_constraints,
            self.unknown_constraints,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in counts
        ):
            raise ValueError("Candidate assessment counts must be non-negative integers")
        if not isinstance(self.admissible, bool):
            raise ValueError("Candidate assessment admissible must be boolean")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Candidate assessment reason cannot be empty")
        if self.admissible and self.unknown_constraints:
            raise ValueError("Admissible candidates cannot contain unknown constraints")
        if self.admissible and self.unresolved_constraints == 0:
            raise ValueError("Admissible uncertified candidates require a residual constraint")

    @property
    def rank(self) -> tuple[int, int]:
        return (self.unresolved_constraints, -self.satisfied_constraints)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutableVerification:
    verifier: str
    check_profile: str
    channel: FeedbackChannel
    passed: bool | None
    bootstrap: CommandResult
    summary: str
    counterexamples: tuple[CounterexampleEvidence, ...] = ()
    hypotheses: tuple[HypothesisEvidence, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)
    observations: tuple[ObservationEvidence, ...] = ()
    candidate_assessment: CandidateAssessment | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.verifier, str) or not self.verifier.strip():
            raise ValueError("Executable verifier name cannot be empty")
        if not isinstance(self.check_profile, str) or not self.check_profile.strip():
            raise ValueError("Executable verification check_profile cannot be empty")
        if not isinstance(self.channel, FeedbackChannel):
            raise ValueError("Executable verification channel must be typed")
        if self.passed is not None and not isinstance(self.passed, bool):
            raise ValueError("Executable verification passed must be true, false, or null")
        if not isinstance(self.bootstrap, CommandResult):
            raise ValueError("Executable verification bootstrap must be a CommandResult")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("Executable verification summary cannot be empty")
        if not isinstance(self.observations, tuple) or not all(
            isinstance(item, ObservationEvidence) for item in self.observations
        ):
            raise ValueError("Executable verifier observations must be typed evidence")
        if not isinstance(self.counterexamples, tuple) or not all(
            isinstance(item, CounterexampleEvidence) for item in self.counterexamples
        ):
            raise ValueError("Executable verifier counterexamples must be typed evidence")
        if not isinstance(self.hypotheses, tuple) or not all(
            isinstance(item, HypothesisEvidence) for item in self.hypotheses
        ):
            raise ValueError("Executable verifier hypotheses must be typed evidence")
        if not isinstance(self.details, dict):
            raise ValueError("Executable verifier details must be an object")
        if self.candidate_assessment is not None and not isinstance(
            self.candidate_assessment, CandidateAssessment
        ):
            raise ValueError("Executable verifier candidate assessment must be typed")
        if (
            self.candidate_assessment is not None
            and self.candidate_assessment.admissible
            and (self.passed is not False or self.bootstrap.exit_code != 0)
        ):
            raise ValueError(
                "Admissible uncertified candidates require a complete failing verification"
            )
        try:
            json.dumps(self.details, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("Executable verifier details must be JSON serializable") from exc


class DeploymentPolicy(Protocol):
    def propose(
        self, state: EnvironmentState
    ) -> DeploymentCandidate | StopDecision: ...


class ExecutableVerifier(Protocol):
    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
    ) -> ExecutableVerification: ...


@dataclass(frozen=True)
class CounterexampleLoopResult:
    stop_reason: str
    goal_status: str
    candidates_attempted: int
    verifier_failures: int
    constraints_updated: int
    snapshot_hash: str
    accepted_candidate: DeploymentCandidate | None = None
    accepted_environment: EnvironmentReceipt | None = None
    candidate_certification: str | None = None
    candidate_assessment: CandidateAssessment | None = None

    def __post_init__(self) -> None:
        if self.candidate_certification not in {None, "certified", "uncertified"}:
            raise ValueError("Candidate certification is invalid")
        if self.accepted_candidate is None:
            if any(
                value is not None
                for value in (
                    self.accepted_environment,
                    self.candidate_certification,
                    self.candidate_assessment,
                )
            ):
                raise ValueError("Candidate output metadata requires an accepted candidate")
            return
        if self.accepted_environment is None or self.candidate_certification is None:
            raise ValueError("Accepted candidates require an environment and certification")
        if self.candidate_certification == "certified" and self.goal_status != "satisfied":
            raise ValueError("Certified candidates require a satisfied internal goal")
        if self.candidate_certification == "uncertified" and (
            self.goal_status != "blocked"
            or self.candidate_assessment is None
            or not self.candidate_assessment.admissible
        ):
            raise ValueError(
                "Uncertified candidates require a blocked goal and admissible assessment"
            )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.accepted_candidate is not None:
            value["accepted_candidate"]["script_sha256"] = (
                self.accepted_candidate.script_sha256
            )
        return value


class CounterexampleGuidedDeploymentLoop:
    """One candidate, one fresh verification, then persisted feedback or stop."""

    def __init__(
        self,
        session: SolverStateSession,
        max_candidates: int,
        candidate_validator: CandidateValidator,
        budget: EpisodeBudget,
        constraint_engine: ConstraintEngine | None = None,
        operation_guard: CandidateOperationGuard | None = None,
        max_policy_failures: int = 3,
        retain_admissible_candidate: bool = True,
        environment_strategy: str = "fresh-candidate",
        goal_id: str = "environment-ready",
        goal_description: str = "Construct an executable project environment",
    ) -> None:
        if max_candidates <= 0:
            raise ValueError("Counterexample loop candidate budget must be positive")
        if max_policy_failures <= 0:
            raise ValueError("Counterexample loop policy failure budget must be positive")
        if environment_strategy not in {
            "fresh-candidate",
            "postcondition-persistent",
        }:
            raise ValueError("Unsupported counterexample-loop environment strategy")
        if constraint_engine is None:
            from envsolve.constraints.engine import ConstraintEngine

            constraint_engine = ConstraintEngine()
        self.session = session
        self.max_candidates = max_candidates
        self.candidate_validator = candidate_validator
        self.budget = budget
        self.constraint_engine = constraint_engine
        self.operation_guard = operation_guard
        self.max_policy_failures = max_policy_failures
        self.retain_admissible_candidate = retain_admissible_candidate
        self.environment_strategy = environment_strategy
        self.goal_id = goal_id
        self.goal_description = goal_description
        self._retained_environment: ProvisionedEnvironment | None = None
        self._retained_environment_provider: FreshEnvironmentProvider | None = None

    @property
    def _persistent_environment(self) -> bool:
        return self.environment_strategy == "postcondition-persistent"

    def _release_retained_environment(self) -> str | None:
        environment = self._retained_environment
        provider = self._retained_environment_provider
        self._retained_environment = None
        if environment is None or provider is None:
            return None
        try:
            provider.release(environment)
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        return None

    def _finish(
        self,
        reason: str,
        goal_status: str,
        attempted: int,
        verifier_failures: int,
        constraints_updated: int,
        accepted_candidate: DeploymentCandidate | None = None,
        accepted_environment: EnvironmentReceipt | None = None,
        candidate_certification: str | None = None,
        candidate_assessment: CandidateAssessment | None = None,
    ) -> CounterexampleLoopResult:
        release_error = self._release_retained_environment()
        if release_error is not None:
            self.session.record_failure(
                category="construction-environment-release",
                message=release_error,
            )
        self.session.upsert_goal(
            self.goal_id,
            self.goal_description,
            goal_status,
        )
        snapshot = self.session.refresh_snapshot()
        return CounterexampleLoopResult(
            stop_reason=reason,
            goal_status=goal_status,
            candidates_attempted=attempted,
            verifier_failures=verifier_failures,
            constraints_updated=constraints_updated,
            snapshot_hash=str(snapshot["snapshot_hash"]),
            accepted_candidate=accepted_candidate,
            accepted_environment=accepted_environment,
            candidate_certification=candidate_certification,
            candidate_assessment=candidate_assessment,
        )

    def _block(
        self,
        category: str,
        message: str,
        attempted: int,
        verifier_failures: int,
        constraints_updated: int,
        *,
        action_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> CounterexampleLoopResult:
        self.session.record_failure(
            category=category,
            message=message,
            action_id=action_id,
            details=details,
        )
        return self._finish(
            message,
            "blocked",
            attempted,
            verifier_failures,
            constraints_updated,
        )

    @staticmethod
    def _known_environment_ids(state: EnvironmentState) -> set[str]:
        identities: set[str] = set()
        for verification in state.verifications:
            details = verification.get("details")
            receipt = details.get("environment_receipt") if isinstance(details, dict) else None
            identity = receipt.get("environment_id") if isinstance(receipt, dict) else None
            if isinstance(identity, str) and identity:
                identities.add(identity)
        return identities

    def _record_verification(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
        outcome: ExecutableVerification,
        accepted_pass: bool | None,
        *,
        verification_id: str | None = None,
        verification_role: str | None = None,
    ) -> None:
        resolved_role = verification_role or str(
            candidate.metadata.get("execution_role", "candidate")
        )
        self.session.record_verification(
            level="internal",
            verifier=outcome.verifier,
            passed=accepted_pass,
            details={
                "verifier_details": outcome.details,
                "candidate_id": candidate.candidate_id,
                "parent_candidate_id": candidate.parent_candidate_id,
                "candidate_sha256": candidate.script_sha256,
                "environment_receipt": environment.receipt.to_dict(),
                "feedback_channel": outcome.channel.value,
                "check_profile": outcome.check_profile,
                "reported_passed": outcome.passed,
                "bootstrap_exit_code": outcome.bootstrap.exit_code,
                "summary": outcome.summary,
                "verification_role": resolved_role,
                "environment_fresh": candidate.metadata.get(
                    "environment_fresh",
                    True,
                ),
                "state_lineage_id": candidate.metadata.get("state_lineage_id"),
                "observation_count": len(outcome.observations),
                "counterexample_count": len(outcome.counterexamples),
                "candidate_assessment": (
                    outcome.candidate_assessment.to_dict()
                    if outcome.candidate_assessment is not None
                    else None
                ),
            },
            verification_id=(
                verification_id
                if verification_id is not None
                else f"verification-{candidate.candidate_id}"
            ),
        )

    def _verify_clean_replay(
        self,
        candidate: DeploymentCandidate,
        environment_provider: FreshEnvironmentProvider,
        verifier: ExecutableVerifier,
        environment_ids: set[str],
    ) -> tuple[
        DeploymentCandidate,
        ProvisionedEnvironment,
        ExecutableVerification,
        str,
    ]:
        replay_metadata = {
            **candidate.metadata,
            "environment_fresh": True,
            "execution_role": "clean-replay-certification",
            "source_candidate_id": candidate.candidate_id,
        }
        replay_metadata.pop("state_lineage_id", None)
        replay = DeploymentCandidate(
            candidate_id=f"{candidate.candidate_id}-clean-replay",
            script=candidate.script,
            rationale="Mandatory clean replay of a postcondition-reusable construction state",
            preconditions=candidate.preconditions,
            metadata=replay_metadata,
            parent_candidate_id=candidate.candidate_id,
        )
        replay_spec = replay.action_spec()
        self.session.propose_action(replay_spec)
        self.session.start_action(replay.candidate_id)
        environment: ProvisionedEnvironment | None = None
        try:
            self.budget.reserve_environment(replay.candidate_id)
            environment = environment_provider.provision(replay)
            if not isinstance(environment, ProvisionedEnvironment):
                raise ValueError("Fresh replay provider returned a malformed lease")
            receipt = environment.receipt
            case = self.session.case
            if (
                receipt.environment_id in environment_ids
                or receipt.repository != case.get("repository")
                or receipt.revision != case.get("revision")
            ):
                raise ValueError("Fresh replay environment receipt is invalid")
            environment_ids.add(receipt.environment_id)
            self.budget.reserve_command(replay.candidate_id)
            outcome = verifier.verify(replay, environment)
            if not isinstance(outcome, ExecutableVerification):
                raise ValueError("Fresh replay verifier returned a malformed result")
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self.session.complete_recorded_action(
                replay.candidate_id,
                replay_spec,
                CommandResult(255, stderr=message),
                evidence_source="clean-replay-certification",
            )
            if environment is not None:
                try:
                    environment_provider.release(environment)
                except Exception:
                    pass
            raise
        try:
            environment_provider.release(environment)
        except Exception as exc:
            message = f"environment release failed: {type(exc).__name__}: {exc}"
            self.session.complete_recorded_action(
                replay.candidate_id,
                replay_spec,
                CommandResult(255, stderr=message),
                evidence_source="clean-replay-certification",
            )
            raise RuntimeError(message) from exc
        action_evidence_id = self.session.complete_recorded_action(
            replay.candidate_id,
            replay_spec,
            outcome.bootstrap,
            evidence_source="clean-replay-certification",
        )
        return replay, environment, outcome, action_evidence_id

    def _record_hypotheses(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
        outcome: ExecutableVerification,
    ) -> None:
        for index, hypothesis in enumerate(outcome.hypotheses, start=1):
            evidence_id = self.session.record_evidence(
                kind="hypothesis-observation",
                source=f"internal-verifier:{outcome.verifier}",
                value={
                    "candidate_id": candidate.candidate_id,
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "value": hypothesis.value,
                },
                confidence=hypothesis.confidence,
                evidence_id=(
                    f"hypothesis-evidence-{candidate.candidate_id}-{index:04d}"
                ),
                candidate_id=candidate.candidate_id,
                parent_candidate_id=candidate.parent_candidate_id,
                environment_id=environment.receipt.environment_id,
            )
            self.session.upsert_hypothesis(
                hypothesis.hypothesis_id,
                hypothesis.statement,
                hypothesis.confidence,
                (evidence_id,),
            )

    @staticmethod
    def _verifier_evidence_source(outcome: ExecutableVerification) -> str:
        source = f"executable-verifier:{outcome.verifier}"
        scope_id = outcome.details.get("evidence_scope_id")
        if scope_id is None:
            return source
        if not isinstance(scope_id, str) or not scope_id:
            raise ValueError("Verifier evidence_scope_id must be a non-empty string")
        return f"{source}:{scope_id}"

    def _ingest_verifier_evidence(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
        outcome: ExecutableVerification,
        evidence: tuple[ObservationEvidence | CounterexampleEvidence, ...],
        *,
        identifier_prefix: str,
    ) -> tuple[str, ...]:
        normalized_ids: list[str] = []
        for index, item in enumerate(evidence, start=1):
            evidence_id = self.session.record_evidence(
                kind=item.kind,
                source=self._verifier_evidence_source(outcome),
                value=item.value,
                confidence=item.confidence,
                evidence_id=(
                    f"{identifier_prefix}-{candidate.candidate_id}-{index:04d}"
                ),
                candidate_id=candidate.candidate_id,
                parent_candidate_id=candidate.parent_candidate_id,
                environment_id=environment.receipt.environment_id,
            )
            normalized_ids.extend(
                self.constraint_engine.ingest_evidence(
                    self.session,
                    evidence_id,
                    fact_scope=candidate.candidate_id,
                )
            )
        return tuple(normalized_ids)

    def run(
        self,
        policy: DeploymentPolicy,
        environment_provider: FreshEnvironmentProvider,
        verifier: ExecutableVerifier,
    ) -> CounterexampleLoopResult:
        if self._retained_environment is not None:
            raise RuntimeError(
                "Counterexample loop retained an environment across runs"
            )
        self._retained_environment_provider = (
            environment_provider if self._persistent_environment else None
        )
        state = self.session.reconstruct()
        if self.goal_id not in state.goals:
            self.session.upsert_goal(
                self.goal_id,
                self.goal_description,
                "in_progress",
            )

        attempted = verifier_failures = constraints_updated = 0
        consecutive_policy_failures = 0
        previous_candidate_id: str | None = None
        best_candidate: DeploymentCandidate | None = None
        best_environment: EnvironmentReceipt | None = None
        best_assessment: CandidateAssessment | None = None
        best_attempt: int | None = None
        environment_ids = self._known_environment_ids(self.session.reconstruct())
        while attempted < self.max_candidates:
            try:
                decision = policy.propose(self.session.reconstruct())
            except EpisodeBudgetExhausted as exc:
                return self._block(
                    "episode-budget-exhausted",
                    str(exc),
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    details={"scope": exc.scope},
                )
            except EpisodeProviderAcquisitionFailed as exc:
                return self._block(
                    "provider-acquisition-failure",
                    str(exc),
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    details={"attempts": exc.attempts},
                )
            except RecoverablePolicyError as exc:
                consecutive_policy_failures += 1
                self.session.record_failure(
                    category=exc.category,
                    message=str(exc),
                    details={
                        **exc.details,
                        "consecutive_policy_failures": consecutive_policy_failures,
                        "max_policy_failures": self.max_policy_failures,
                    },
                )
                if consecutive_policy_failures >= self.max_policy_failures:
                    return self._finish(
                        "policy output failure budget exhausted",
                        "blocked",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                    )
                continue
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                return self._block(
                    "candidate-policy-exception",
                    message,
                    attempted,
                    verifier_failures,
                    constraints_updated,
                )
            consecutive_policy_failures = 0
            if isinstance(decision, StopDecision):
                if decision.goal_status == "satisfied":
                    return self._block(
                        "unverified-policy-stop",
                        "Policy cannot declare success without a passing executable verifier",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                    )
                if decision.goal_status != "blocked":
                    return self._block(
                        "malformed-policy-decision",
                        "Deployment policy stop must be satisfied or blocked",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                    )
                return self._finish(
                    decision.reason,
                    "blocked",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                )
            if not isinstance(decision, DeploymentCandidate):
                return self._block(
                    "malformed-policy-decision",
                    "Deployment policy must return a candidate or StopDecision",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                )

            decision = DeploymentCandidate(
                candidate_id=decision.candidate_id,
                script=decision.script,
                rationale=decision.rationale,
                preconditions=decision.preconditions,
                metadata=decision.metadata,
                parent_candidate_id=previous_candidate_id,
            )
            try:
                self.budget.reserve_candidate(decision.candidate_id)
            except Exception as exc:
                return self._block(
                    "episode-budget-exhausted",
                    f"{type(exc).__name__}: {exc}",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                )

            try:
                validation = self.candidate_validator.validate(decision)
            except Exception as exc:
                return self._block(
                    "candidate-validation-exception",
                    f"{type(exc).__name__}: {exc}",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                )
            if not isinstance(validation, CandidateValidation) or not validation.accepted:
                reason = (
                    validation.reason
                    if isinstance(validation, CandidateValidation)
                    else "Candidate validator returned a malformed result"
                )
                raw_spec = decision.action_spec()
                try:
                    self.session.propose_action(raw_spec)
                    self.session.start_action(decision.candidate_id)
                    self.session.complete_recorded_action(
                        decision.candidate_id,
                        raw_spec,
                        CommandResult(252, stderr=str(reason)),
                        evidence_source="candidate-validation",
                    )
                except (TypeError, ValueError) as exc:
                    return self._block(
                        "candidate-state-transition",
                        f"{type(exc).__name__}: {exc}",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                    )
                attempted += 1
                previous_candidate_id = decision.candidate_id
                self.session.record_failure(
                    category="candidate-validation-reject",
                    message=str(reason),
                    action_id=decision.candidate_id,
                    details=(
                        validation.details
                        if isinstance(validation, CandidateValidation)
                        else None
                    ),
                )
                continue
            decision = DeploymentCandidate(
                candidate_id=decision.candidate_id,
                script=str(validation.normalized_script),
                rationale=decision.rationale,
                parent_candidate_id=decision.parent_candidate_id,
                preconditions=decision.preconditions,
                metadata={
                    **decision.metadata,
                    "candidate_validation": {
                        "policy_id": validation.policy_id,
                        "details": validation.details,
                    },
                },
            )
            if self.operation_guard is not None:
                try:
                    guard = self.operation_guard.validate(
                        decision,
                        self.session.reconstruct(),
                    )
                except Exception as exc:
                    return self._block(
                        "candidate-operation-guard-exception",
                        f"{type(exc).__name__}: {exc}",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                    )
                if not isinstance(guard, OperationGuardDecision):
                    return self._block(
                        "candidate-operation-guard-contract",
                        "Candidate operation guard returned a malformed result",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                    )
                decision = DeploymentCandidate(
                    candidate_id=decision.candidate_id,
                    script=decision.script,
                    rationale=decision.rationale,
                    parent_candidate_id=decision.parent_candidate_id,
                    preconditions=decision.preconditions,
                    metadata={
                        **decision.metadata,
                        "operation_guard": guard.to_dict(),
                    },
                )
                if not guard.accepted:
                    reason = str(guard.reason)
                    guarded_spec = decision.action_spec()
                    try:
                        self.session.propose_action(guarded_spec)
                        self.session.start_action(decision.candidate_id)
                        self.session.complete_recorded_action(
                            decision.candidate_id,
                            guarded_spec,
                            CommandResult(251, stderr=reason),
                            evidence_source="candidate-operation-guard",
                        )
                    except (TypeError, ValueError) as exc:
                        return self._block(
                            "candidate-state-transition",
                            f"{type(exc).__name__}: {exc}",
                            attempted,
                            verifier_failures,
                            constraints_updated,
                        )
                    attempted += 1
                    previous_candidate_id = decision.candidate_id
                    self.session.record_failure(
                        category="candidate-operation-reject",
                        message=reason,
                        action_id=decision.candidate_id,
                        details=guard.details,
                    )
                    continue
            action_spec = decision.action_spec()
            try:
                self.session.propose_action(action_spec)
                self.session.start_action(decision.candidate_id)
            except (TypeError, ValueError) as exc:
                return self._block(
                    "candidate-state-transition",
                    f"{type(exc).__name__}: {exc}",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                )
            environment_reused = (
                self._persistent_environment and self._retained_environment is not None
            )
            if environment_reused:
                environment = self._retained_environment
            else:
                try:
                    self.budget.reserve_environment(decision.candidate_id)
                except Exception as exc:
                    self.session.complete_recorded_action(
                        decision.candidate_id,
                        action_spec,
                        CommandResult(255, stderr=f"{type(exc).__name__}: {exc}"),
                        evidence_source="episode-budget",
                    )
                    attempted += 1
                    return self._block(
                        "episode-budget-exhausted",
                        f"{type(exc).__name__}: {exc}",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                        action_id=decision.candidate_id,
                    )
                try:
                    environment = environment_provider.provision(decision)
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    self.session.complete_recorded_action(
                        decision.candidate_id,
                        action_spec,
                        CommandResult(255, stderr=message),
                        evidence_source="fresh-environment-replay",
                    )
                    attempted += 1
                    return self._block(
                        "fresh-environment-provision-exception",
                        message,
                        attempted,
                        verifier_failures,
                        constraints_updated,
                        action_id=decision.candidate_id,
                    )

                if not isinstance(environment, ProvisionedEnvironment):
                    message = "Fresh environment provider returned a malformed lease"
                    self.session.complete_recorded_action(
                        decision.candidate_id,
                        action_spec,
                        CommandResult(255, stderr=message),
                        evidence_source="fresh-environment-replay",
                    )
                    attempted += 1
                    return self._block(
                        "malformed-environment-lease",
                        message,
                        attempted,
                        verifier_failures,
                        constraints_updated,
                        action_id=decision.candidate_id,
                    )

                receipt = environment.receipt
                case = self.session.case
                if (
                    receipt.environment_id in environment_ids
                    or receipt.repository != case.get("repository")
                    or receipt.revision != case.get("revision")
                ):
                    try:
                        environment_provider.release(environment)
                    except Exception as exc:
                        release_error = f"{type(exc).__name__}: {exc}"
                    else:
                        release_error = None
                    self.session.complete_recorded_action(
                        decision.candidate_id,
                        action_spec,
                        CommandResult(255, stderr="Invalid fresh environment receipt"),
                        evidence_source="fresh-environment-replay",
                    )
                    attempted += 1
                    return self._block(
                        "fresh-environment-contract",
                        "Environment provider did not provide a unique case-matched environment",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                        action_id=decision.candidate_id,
                        details={
                            "environment_receipt": receipt.to_dict(),
                            "release_error": release_error,
                        },
                    )
                environment_ids.add(receipt.environment_id)
                if self._persistent_environment:
                    self._retained_environment = environment

            receipt = environment.receipt
            construction_reusable = False
            if self._persistent_environment:
                decision = replace(
                    decision,
                    metadata={
                        **decision.metadata,
                        "environment_fresh": not environment_reused,
                        "execution_role": "construction-state",
                        "state_lineage_id": receipt.environment_id,
                    },
                )

            try:
                self.budget.reserve_command(decision.candidate_id)
            except Exception as exc:
                if self._persistent_environment:
                    self._release_retained_environment()
                else:
                    try:
                        environment_provider.release(environment)
                    except Exception:
                        pass
                message = f"{type(exc).__name__}: {exc}"
                self.session.complete_recorded_action(
                    decision.candidate_id,
                    action_spec,
                    CommandResult(255, stderr=message),
                    evidence_source="episode-budget",
                )
                attempted += 1
                return self._block(
                    "episode-budget-exhausted",
                    message,
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    action_id=decision.candidate_id,
                )

            verification_error: str | None = None
            release_error: str | None = None
            try:
                outcome = verifier.verify(decision, environment)
            except Exception as exc:
                verification_error = f"{type(exc).__name__}: {exc}"
                outcome = None
            finally:
                if not self._persistent_environment:
                    try:
                        environment_provider.release(environment)
                    except Exception as exc:
                        release_error = f"{type(exc).__name__}: {exc}"

            if release_error is not None:
                outcome = None
                verification_error = f"environment release failed: {release_error}"

            if not isinstance(outcome, ExecutableVerification):
                if self._persistent_environment:
                    retained_release_error = self._release_retained_environment()
                    if retained_release_error is not None:
                        verification_error = (
                            f"{verification_error or 'malformed verifier result'}; "
                            f"environment release failed: {retained_release_error}"
                        )
                message = verification_error or "Executable verifier returned a malformed result"
                self.session.complete_recorded_action(
                    decision.candidate_id,
                    action_spec,
                    CommandResult(255, stderr=message),
                    evidence_source="fresh-environment-replay",
                )
                attempted += 1
                return self._block(
                    "malformed-verifier-result",
                    message,
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    action_id=decision.candidate_id,
                )

            if self._persistent_environment:
                transition = assess_state_transition(outcome)
                outcome = replace(
                    outcome,
                    details={
                        **outcome.details,
                        "state_transition": transition.to_dict(),
                    },
                )
                self.session.record_evidence(
                    kind="state-transition-observation",
                    source="postcondition-state-transition-v1",
                    value={
                        "candidate_id": decision.candidate_id,
                        "environment_id": receipt.environment_id,
                        **transition.to_dict(),
                    },
                    confidence=1.0,
                    candidate_id=decision.candidate_id,
                    parent_candidate_id=decision.parent_candidate_id,
                    environment_id=receipt.environment_id,
                )
                if transition.disposition is not StateTransitionDisposition.REUSABLE:
                    retained_release_error = self._release_retained_environment()
                    if retained_release_error is not None:
                        return self._block(
                            "construction-environment-release",
                            retained_release_error,
                            attempted,
                            verifier_failures,
                            constraints_updated,
                            action_id=decision.candidate_id,
                        )
                else:
                    construction_reusable = True

            action_evidence_id = self.session.complete_recorded_action(
                decision.candidate_id,
                action_spec,
                outcome.bootstrap,
                evidence_source=(
                    "construction-state-replay"
                    if self._persistent_environment
                    else "fresh-environment-replay"
                ),
            )
            attempted += 1
            previous_candidate_id = decision.candidate_id

            if outcome.channel is not FeedbackChannel.INTERNAL_EXECUTION:
                self._record_verification(decision, environment, outcome, False)
                return self._block(
                    "forbidden-feedback-channel",
                    "Post-episode evaluation feedback cannot enter the online solver",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    action_id=decision.candidate_id,
                )

            if (
                self._persistent_environment
                and construction_reusable
                and outcome.passed is True
            ):
                construction_candidate = decision
                self._record_verification(
                    construction_candidate,
                    environment,
                    outcome,
                    None,
                    verification_id=(
                        f"verification-construction-"
                        f"{construction_candidate.candidate_id}"
                    ),
                    verification_role="construction-state",
                )
                try:
                    (
                        decision,
                        environment,
                        outcome,
                        action_evidence_id,
                    ) = self._verify_clean_replay(
                        construction_candidate,
                        environment_provider,
                        verifier,
                        environment_ids,
                    )
                except Exception as exc:
                    return self._block(
                        "clean-replay-certification-exception",
                        f"{type(exc).__name__}: {exc}",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                        action_id=construction_candidate.candidate_id,
                    )
                receipt = environment.receipt
                if outcome.channel is not FeedbackChannel.INTERNAL_EXECUTION:
                    self._record_verification(
                        decision,
                        environment,
                        outcome,
                        False,
                        verification_role="clean-replay-certification",
                    )
                    return self._block(
                        "forbidden-feedback-channel",
                        "Post-episode evaluation feedback cannot enter the online solver",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                        action_id=decision.candidate_id,
                    )

            if outcome.passed is None:
                self._record_hypotheses(decision, environment, outcome)
                self._record_verification(
                    decision,
                    environment,
                    outcome,
                    None,
                    verification_role=(
                        "clean-replay-certification"
                        if decision.metadata.get("execution_role")
                        == "clean-replay-certification"
                        else "candidate"
                    ),
                )
                return self._block(
                    "executable-verifier-unknown",
                    outcome.summary,
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    action_id=decision.candidate_id,
                    details=outcome.details,
                )
            if outcome.passed:
                if outcome.bootstrap.exit_code != 0 or outcome.counterexamples:
                    self._record_verification(decision, environment, outcome, False)
                    return self._block(
                        "executable-verifier-contract",
                        "Passing verification contradicts bootstrap or counterexample evidence",
                        attempted,
                        verifier_failures,
                        constraints_updated,
                        action_id=decision.candidate_id,
                    )
                state_before_pass = self.session.reconstruct()
                prior_fact_ids = self.constraint_engine.fact_constraint_ids(
                    state_before_pass
                )
                evidence_scope_id = outcome.details.get("evidence_scope_id")
                prior_goal_constraint_ids: tuple[str, ...] = ()
                if evidence_scope_id is not None:
                    prior_goal_constraint_ids = (
                        self.constraint_engine.constraint_ids_for_evidence_source(
                            state_before_pass,
                            self._verifier_evidence_source(outcome),
                        )
                    )
                observation_ids = self._ingest_verifier_evidence(
                    decision,
                    environment,
                    outcome,
                    outcome.observations,
                    identifier_prefix="observation",
                )
                retired_goal_ids = self.constraint_engine.supersede_constraints(
                    self.session,
                    prior_goal_constraint_ids,
                )
                self.constraint_engine.supersede_facts(self.session, prior_fact_ids)
                constraints_updated += len(set((*observation_ids, *retired_goal_ids)))
                self.constraint_engine.propagate_constraints(self.session)
                self._record_verification(decision, environment, outcome, True)
                return self._finish(
                    outcome.summary,
                    "satisfied",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    accepted_candidate=decision,
                    accepted_environment=receipt,
                    candidate_certification="certified",
                    candidate_assessment=outcome.candidate_assessment,
                )

            verifier_failures += 1
            self._record_hypotheses(decision, environment, outcome)
            self._record_verification(decision, environment, outcome, False)
            assessment = outcome.candidate_assessment
            if (
                self.retain_admissible_candidate
                and assessment is not None
                and assessment.admissible
            ):
                candidate_rank = (*assessment.rank, attempted)
                best_rank = (
                    (*best_assessment.rank, int(best_attempt))
                    if best_assessment is not None and best_attempt is not None
                    else None
                )
                if best_rank is None or candidate_rank < best_rank:
                    best_candidate = decision
                    best_environment = receipt
                    best_assessment = assessment
                    best_attempt = attempted
            self.session.record_failure(
                category="executable-verifier-counterexample",
                message=outcome.summary,
                action_id=decision.candidate_id,
                details=outcome.details,
            )
            state_before_failure = self.session.reconstruct()
            prior_fact_ids = self.constraint_engine.fact_constraint_ids(
                state_before_failure
            )
            prior_goal_constraint_ids: tuple[str, ...] = ()
            if outcome.details.get("finding_set_complete", False):
                prior_goal_constraint_ids = (
                    self.constraint_engine.constraint_ids_for_evidence_source(
                        state_before_failure,
                        self._verifier_evidence_source(outcome),
                    )
                )
            action_constraint_ids = self.constraint_engine.ingest_evidence(
                self.session,
                action_evidence_id,
                fact_scope=decision.candidate_id,
            )
            observation_ids = self._ingest_verifier_evidence(
                decision,
                environment,
                outcome,
                outcome.observations,
                identifier_prefix="observation",
            )
            counterexample_ids = self._ingest_verifier_evidence(
                decision,
                environment,
                outcome,
                outcome.counterexamples,
                identifier_prefix="counterexample",
            )
            normalized_ids = (
                *action_constraint_ids,
                *observation_ids,
                *counterexample_ids,
            )
            if not counterexample_ids:
                replacement_fact_ids = self.constraint_engine.fact_constraint_ids(
                    self.session.reconstruct(),
                    normalized_ids,
                )
                self.constraint_engine.supersede_replaced_facts(
                    self.session,
                    prior_fact_ids,
                    replacement_fact_ids,
                )
                constraints_updated += len(set(normalized_ids))
                self.constraint_engine.propagate_constraints(self.session)
                if outcome.hypotheses:
                    continue
                return self._block(
                    "unnormalizable-verifier-failure",
                    "Verifier failure produced no normalized constraint",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    action_id=decision.candidate_id,
                )
            state_after_ingest = self.session.reconstruct()
            replacement_fact_ids = self.constraint_engine.fact_constraint_ids(
                state_after_ingest,
                normalized_ids,
            )
            self.constraint_engine.supersede_replaced_facts(
                self.session,
                prior_fact_ids,
                replacement_fact_ids,
            )
            current_goal_constraint_ids = set((*observation_ids, *counterexample_ids))
            retired_goal_ids = self.constraint_engine.supersede_constraints(
                self.session,
                set(prior_goal_constraint_ids) - current_goal_constraint_ids,
            )
            constraints_updated += len(set((*normalized_ids, *retired_goal_ids)))
            solve_report = self.constraint_engine.propagate_constraints(self.session)
            if not solve_report.conflicts:
                return self._block(
                    "noncontradictory-verifier-failure",
                    "Verifier failure did not produce a violated constraint",
                    attempted,
                    verifier_failures,
                    constraints_updated,
                    action_id=decision.candidate_id,
                    details={"solve_report": solve_report.to_dict()},
                )

        self.session.record_failure(
            "candidate-budget",
            f"Counterexample loop exhausted {self.max_candidates} candidates",
            details=(
                {
                    "best_admissible_candidate_id": best_candidate.candidate_id,
                    "candidate_assessment": best_assessment.to_dict(),
                }
                if best_candidate is not None and best_assessment is not None
                else None
            ),
        )
        return self._finish(
            (
                "candidate budget exhausted; returning best admissible candidate"
                if best_candidate is not None
                else "candidate budget exhausted"
            ),
            "blocked",
            attempted,
            verifier_failures,
            constraints_updated,
            accepted_candidate=best_candidate,
            accepted_environment=best_environment,
            candidate_certification=(
                "uncertified" if best_candidate is not None else None
            ),
            candidate_assessment=best_assessment,
        )
