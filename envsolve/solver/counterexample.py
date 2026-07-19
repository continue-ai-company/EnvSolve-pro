from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import TYPE_CHECKING, Any, Protocol

from envsolve.operations import OperationGuardDecision
from envsolve.solver.loop import StopDecision
from envsolve.solver.session import ActionSpec, CommandResult, SolverStateSession
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
        goal_id: str = "environment-ready",
        goal_description: str = "Construct an executable project environment",
    ) -> None:
        if max_candidates <= 0:
            raise ValueError("Counterexample loop candidate budget must be positive")
        if max_policy_failures <= 0:
            raise ValueError("Counterexample loop policy failure budget must be positive")
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
        self.goal_id = goal_id
        self.goal_description = goal_description

    def _finish(
        self,
        reason: str,
        goal_status: str,
        attempted: int,
        verifier_failures: int,
        constraints_updated: int,
        accepted_candidate: DeploymentCandidate | None = None,
        accepted_environment: EnvironmentReceipt | None = None,
    ) -> CounterexampleLoopResult:
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
    ) -> None:
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
                "observation_count": len(outcome.observations),
                "counterexample_count": len(outcome.counterexamples),
            },
            verification_id=f"verification-{candidate.candidate_id}",
        )

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
                source=f"executable-verifier:{outcome.verifier}",
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
        environment_ids = self._known_environment_ids(self.session.reconstruct())
        while attempted < self.max_candidates:
            try:
                decision = policy.propose(self.session.reconstruct())
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

            try:
                self.budget.reserve_command(decision.candidate_id)
            except Exception as exc:
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
                try:
                    environment_provider.release(environment)
                except Exception as exc:
                    release_error = f"{type(exc).__name__}: {exc}"

            if release_error is not None:
                outcome = None
                verification_error = f"environment release failed: {release_error}"

            if not isinstance(outcome, ExecutableVerification):
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

            action_evidence_id = self.session.complete_recorded_action(
                decision.candidate_id,
                action_spec,
                outcome.bootstrap,
                evidence_source="fresh-environment-replay",
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

            if outcome.passed is None:
                self._record_hypotheses(decision, environment, outcome)
                self._record_verification(decision, environment, outcome, None)
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
                prior_fact_ids = self.constraint_engine.fact_constraint_ids(
                    self.session.reconstruct()
                )
                observation_ids = self._ingest_verifier_evidence(
                    decision,
                    environment,
                    outcome,
                    outcome.observations,
                    identifier_prefix="observation",
                )
                self.constraint_engine.supersede_facts(self.session, prior_fact_ids)
                constraints_updated += len(set(observation_ids))
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
                )

            verifier_failures += 1
            self._record_hypotheses(decision, environment, outcome)
            self._record_verification(decision, environment, outcome, False)
            self.session.record_failure(
                category="executable-verifier-counterexample",
                message=outcome.summary,
                action_id=decision.candidate_id,
                details=outcome.details,
            )
            prior_fact_ids = self.constraint_engine.fact_constraint_ids(
                self.session.reconstruct()
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
            constraints_updated += len(set(normalized_ids))
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
        )
        return self._finish(
            "candidate budget exhausted",
            "blocked",
            attempted,
            verifier_failures,
            constraints_updated,
        )
