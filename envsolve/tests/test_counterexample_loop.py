from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from envsolve.solver import (
    CandidateValidation,
    CommandResult,
    CounterexampleEvidence,
    CounterexampleGuidedDeploymentLoop,
    DeploymentCandidate,
    EnvironmentReceipt,
    ExecutableVerification,
    FeedbackChannel,
    HypothesisEvidence,
    ProvisionedEnvironment,
    RecoverablePolicyError,
    SolverStateSession,
    StopDecision,
)
from envsolve.state import EnvironmentState, EventStore, audit_state_artifacts


CASE = {
    "case_id": "counterexample-loop-synthetic",
    "repository": "example/project",
    "revision": "a" * 40,
}


class RecordingPolicy:
    def __init__(self, decisions: list[DeploymentCandidate | StopDecision]) -> None:
        self.decisions = list(decisions)
        self.observed_states: list[EnvironmentState] = []

    def propose(self, state: EnvironmentState) -> DeploymentCandidate | StopDecision:
        self.observed_states.append(state)
        return self.decisions.pop(0)


class RecoveringPolicy:
    def __init__(self) -> None:
        self.calls = 0
        self.observed_states: list[EnvironmentState] = []

    def propose(self, state: EnvironmentState) -> DeploymentCandidate:
        self.calls += 1
        self.observed_states.append(state)
        if self.calls == 1:
            raise RecoverablePolicyError(
                "malformed model object",
                details={"response_sha256": "a" * 64},
            )
        return candidate(1)


class QueueVerifier:
    def __init__(self, outcomes: list[ExecutableVerification]) -> None:
        self.outcomes = list(outcomes)

    def verify(
        self, candidate: DeploymentCandidate, environment: ProvisionedEnvironment
    ) -> ExecutableVerification:
        return self.outcomes.pop(0)


class MalformedVerifier:
    def verify(self, candidate: DeploymentCandidate, environment: ProvisionedEnvironment) -> object:
        return {"passed": True}


class AcceptingValidator:
    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        return CandidateValidation(True, "synthetic-validator", candidate.script)


class RecordingBudget:
    def __init__(self) -> None:
        self.candidates: list[str] = []
        self.environments: list[str] = []
        self.commands: list[str] = []

    def reserve_candidate(self, candidate_id: str) -> None:
        self.candidates.append(candidate_id)

    def reserve_environment(self, candidate_id: str) -> None:
        self.environments.append(candidate_id)

    def reserve_command(self, candidate_id: str) -> None:
        self.commands.append(candidate_id)


class QueueEnvironmentProvider:
    def __init__(self, environment_ids: list[str] | None = None) -> None:
        self.environment_ids = list(environment_ids or [])
        self.count = 0
        self.released: list[str] = []

    def provision(self, candidate: DeploymentCandidate) -> ProvisionedEnvironment:
        self.count += 1
        environment_id = (
            self.environment_ids.pop(0)
            if self.environment_ids
            else f"fresh-env-{self.count}"
        )
        return ProvisionedEnvironment(
            EnvironmentReceipt(
                environment_id,
                "synthetic-provider",
                "sha256:synthetic-image",
                CASE["repository"],
                CASE["revision"],
                f"2026-01-01T00:00:0{self.count}+00:00",
            )
        )

    def release(self, environment: ProvisionedEnvironment) -> None:
        self.released.append(environment.receipt.environment_id)


def candidate(index: int) -> DeploymentCandidate:
    return DeploymentCandidate(
        candidate_id=f"candidate-{index}",
        script=f"python -m pip install candidate-{index}",
        rationale="Synthetic deployment candidate",
    )


def outcome(
    index: int,
    passed: bool | None,
    *,
    exit_code: int = 0,
    counterexamples: tuple[CounterexampleEvidence, ...] = (),
    stderr: str = "",
    channel: FeedbackChannel = FeedbackChannel.INTERNAL_EXECUTION,
    hypotheses: tuple[HypothesisEvidence, ...] = (),
) -> ExecutableVerification:
    return ExecutableVerification(
        verifier="synthetic-goal-verifier",
        check_profile="synthetic-complete-check",
        channel=channel,
        passed=passed,
        bootstrap=CommandResult(exit_code, stderr=stderr),
        summary=f"synthetic outcome {index}",
        counterexamples=counterexamples,
        hypotheses=hypotheses,
    )


class CounterexampleGuidedDeploymentLoopTests(unittest.TestCase):
    def session(self, root: Path) -> SolverStateSession:
        return SolverStateSession(root / "state.jsonl", root / "snapshot.json", CASE)

    @staticmethod
    def loop(session: SolverStateSession, max_candidates: int):
        return CounterexampleGuidedDeploymentLoop(
            session,
            max_candidates=max_candidates,
            candidate_validator=AcceptingValidator(),
            budget=RecordingBudget(),
        )

    def test_constraint_is_persisted_before_the_next_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = self.session(root)
            policy = RecordingPolicy([candidate(1), candidate(2)])
            verifier = QueueVerifier(
                [
                    outcome(
                        1,
                        False,
                        stderr="ModuleNotFoundError: No module named 'ambient_log_only'",
                        counterexamples=(
                            CounterexampleEvidence(
                                "module-requirement",
                                {"name": "example_dependency", "present": True},
                            ),
                            CounterexampleEvidence(
                                "module-observation",
                                {"name": "example_dependency", "present": False},
                            ),
                        ),
                    ),
                    outcome(2, True),
                ]
            )

            result = self.loop(session, 2).run(
                policy, QueueEnvironmentProvider(), verifier
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.candidates_attempted, 2)
            self.assertEqual(result.verifier_failures, 1)
            self.assertEqual(result.constraints_updated, 2)
            self.assertEqual(result.accepted_candidate.parent_candidate_id, "candidate-1")
            self.assertEqual(len(policy.observed_states), 2)
            second_state = policy.observed_states[1]
            self.assertEqual(len(second_state.constraints), 2)
            self.assertEqual(
                {item["status"] for item in second_state.constraints.values()},
                {"violated"},
            )
            self.assertTrue(
                all(
                    "ambient_log_only" not in item["expression"]
                    for item in second_state.constraints.values()
                )
            )

            events = EventStore(root / "state.jsonl", CASE["case_id"]).read()
            constraint_sequence = next(
                event.sequence
                for event in events
                if event.event_type == "constraint_upserted"
            )
            second_action_sequence = next(
                event.sequence
                for event in events
                if event.event_type == "action_proposed"
                and event.payload["action_id"] == "candidate-2"
            )
            self.assertLess(constraint_sequence, second_action_sequence)
            first = {
                event.event_type: event.sequence
                for event in events
                if event.payload.get("action_id") == "candidate-1"
                and event.event_type
                in {"action_proposed", "action_started", "action_finished"}
            }
            first_verification_sequence = next(
                event.sequence
                for event in events
                if event.event_type == "verification_recorded"
                and event.payload["details"]["candidate_id"] == "candidate-1"
            )
            self.assertLess(first["action_proposed"], first["action_started"])
            self.assertLess(first["action_started"], first["action_finished"])
            self.assertLess(first["action_finished"], first_verification_sequence)
            final_state = session.reconstruct()
            self.assertEqual(
                final_state.actions["candidate-2"]["metadata"]["parent_candidate_id"],
                "candidate-1",
            )
            counterexample_evidence = final_state.evidence[
                "counterexample-candidate-1-0001"
            ]
            self.assertEqual(counterexample_evidence["candidate_id"], "candidate-1")
            self.assertEqual(counterexample_evidence["environment_id"], "fresh-env-1")
            self.assertTrue(
                audit_state_artifacts(
                    root / "state.jsonl", root / "snapshot.json", CASE["case_id"]
                ).valid
            )

    def test_unknown_blocks_without_creating_a_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            policy = RecordingPolicy([candidate(1), candidate(2)])

            result = self.loop(session, 2).run(
                policy,
                QueueEnvironmentProvider(),
                QueueVerifier([outcome(1, None)]),
            )

            self.assertEqual(result.goal_status, "blocked")
            self.assertEqual(result.candidates_attempted, 1)
            self.assertEqual(len(policy.observed_states), 1)
            self.assertFalse(session.reconstruct().constraints)
            categories = {
                item["category"] for item in session.reconstruct().failures.values()
            }
            self.assertIn("executable-verifier-unknown", categories)

    def test_hypothesis_only_failure_can_drive_a_fresh_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            policy = RecordingPolicy([candidate(1), candidate(2)])
            timeout_hypothesis = HypothesisEvidence(
                "hypothesis-candidate-1-execution-timeout",
                "The candidate must reduce installation or verification cost",
                {"command_timeout_seconds": 900, "exit_code": 124},
                1.0,
            )

            result = self.loop(session, 2).run(
                policy,
                QueueEnvironmentProvider(),
                QueueVerifier(
                    [
                        outcome(
                            1,
                            False,
                            exit_code=124,
                            hypotheses=(timeout_hypothesis,),
                        ),
                        outcome(2, True),
                    ]
                ),
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.candidates_attempted, 2)
            self.assertEqual(result.verifier_failures, 1)
            self.assertFalse(session.reconstruct().constraints)
            self.assertIn(
                timeout_hypothesis.hypothesis_id,
                policy.observed_states[1].hypotheses,
            )

    def test_unnormalizable_failure_blocks_before_another_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            policy = RecordingPolicy([candidate(1), candidate(2)])
            verifier = QueueVerifier(
                [
                    outcome(
                        1,
                        False,
                        counterexamples=(
                            CounterexampleEvidence("unsupported-diagnostic", {"raw": "x"}),
                        ),
                    )
                ]
            )

            result = self.loop(session, 2).run(
                policy, QueueEnvironmentProvider(), verifier
            )

            self.assertEqual(result.goal_status, "blocked")
            self.assertEqual(len(policy.observed_states), 1)
            self.assertFalse(session.reconstruct().constraints)
            categories = {
                item["category"] for item in session.reconstruct().failures.values()
            }
            self.assertIn("unnormalizable-verifier-failure", categories)

    def test_noncontradictory_failure_cannot_drive_another_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            policy = RecordingPolicy([candidate(1), candidate(2)])
            verifier = QueueVerifier(
                [
                    outcome(
                        1,
                        False,
                        counterexamples=(
                            CounterexampleEvidence(
                                "module-requirement",
                                {"name": "already_present", "present": True},
                            ),
                            CounterexampleEvidence(
                                "module-observation",
                                {"name": "already_present", "present": True},
                            ),
                        ),
                    )
                ]
            )

            result = self.loop(session, 2).run(
                policy, QueueEnvironmentProvider(), verifier
            )

            self.assertEqual(result.goal_status, "blocked")
            self.assertEqual(len(policy.observed_states), 1)
            categories = {
                item["category"] for item in session.reconstruct().failures.values()
            }
            self.assertIn("noncontradictory-verifier-failure", categories)

    def test_environment_identity_cannot_be_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            verifier = QueueVerifier(
                [
                    outcome(
                        1,
                        False,
                        counterexamples=(
                            CounterexampleEvidence(
                                "capability-requirement",
                                {"name": "compiler", "present": True},
                            ),
                            CounterexampleEvidence(
                                "capability-observation",
                                {"name": "compiler", "present": False},
                            ),
                        ),
                    ),
                    outcome(2, True),
                ]
            )

            result = self.loop(session, 2).run(
                RecordingPolicy([candidate(1), candidate(2)]),
                QueueEnvironmentProvider(["same-environment", "same-environment"]),
                verifier,
            )

            self.assertEqual(result.goal_status, "blocked")
            categories = {
                item["category"] for item in session.reconstruct().failures.values()
            }
            self.assertIn("fresh-environment-contract", categories)

    def test_contradictory_pass_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            result = self.loop(session, 1).run(
                RecordingPolicy([candidate(1)]),
                QueueEnvironmentProvider(),
                QueueVerifier([outcome(1, True, exit_code=1)]),
            )

            self.assertEqual(result.goal_status, "blocked")
            categories = {
                item["category"] for item in session.reconstruct().failures.values()
            }
            self.assertIn("executable-verifier-contract", categories)
            self.assertFalse(session.reconstruct().verifications[0]["passed"])

    def test_malformed_verifier_result_fails_closed_with_terminal_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = self.session(root)
            result = self.loop(session, 1).run(
                RecordingPolicy([candidate(1)]),
                QueueEnvironmentProvider(),
                MalformedVerifier(),
            )

            self.assertEqual(result.goal_status, "blocked")
            action = session.reconstruct().actions["candidate-1"]
            self.assertEqual(action["status"], "failed")
            self.assertTrue(
                audit_state_artifacts(
                    root / "state.jsonl", root / "snapshot.json", CASE["case_id"]
                ).valid
            )

    def test_policy_cannot_claim_unverified_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            result = self.loop(session, 1).run(
                RecordingPolicy([StopDecision("looks ready", "satisfied")]),
                QueueEnvironmentProvider(),
                QueueVerifier([]),
            )

            self.assertEqual(result.goal_status, "blocked")
            categories = {
                item["category"] for item in session.reconstruct().failures.values()
            }
            self.assertIn("unverified-policy-stop", categories)

    def test_unknown_precondition_blocks_before_verifier_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            invalid = DeploymentCandidate(
                candidate_id="candidate-invalid",
                script="python -m pip install -e .",
                rationale="Synthetic invalid precondition",
                preconditions=("constraint-that-does-not-exist",),
            )
            verifier = QueueVerifier([outcome(1, True)])

            result = self.loop(session, 1).run(
                RecordingPolicy([invalid]), QueueEnvironmentProvider(), verifier
            )

            self.assertEqual(result.goal_status, "blocked")
            self.assertEqual(len(verifier.outcomes), 1)
            categories = {
                item["category"] for item in session.reconstruct().failures.values()
            }
            self.assertIn("candidate-state-transition", categories)

    def test_post_episode_feedback_is_rejected_before_constraint_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            result = self.loop(session, 1).run(
                RecordingPolicy([candidate(1)]),
                QueueEnvironmentProvider(),
                QueueVerifier(
                    [
                        outcome(
                            1,
                            False,
                            channel=FeedbackChannel.POST_EPISODE_EVALUATION,
                            counterexamples=(
                                CounterexampleEvidence(
                                    "module-requirement",
                                    {"name": "leaked", "present": True},
                                ),
                                CounterexampleEvidence(
                                    "module-observation",
                                    {"name": "leaked", "present": False},
                                ),
                            ),
                        )
                    ]
                ),
            )

            self.assertEqual(result.goal_status, "blocked")
            self.assertFalse(session.reconstruct().constraints)
            self.assertIn(
                "forbidden-feedback-channel",
                {item["category"] for item in session.reconstruct().failures.values()},
            )

    def test_rejected_candidate_is_budgeted_and_preserved_as_an_artifact(self) -> None:
        class RejectingValidator:
            def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
                return CandidateValidation(
                    False,
                    "rejecting-validator",
                    reason="unsupported candidate",
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = self.session(root)
            budget = RecordingBudget()
            loop = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=1,
                candidate_validator=RejectingValidator(),
                budget=budget,
            )

            result = loop.run(
                RecordingPolicy([candidate(1)]),
                QueueEnvironmentProvider(),
                QueueVerifier([]),
            )

            self.assertEqual(result.candidates_attempted, 1)
            self.assertEqual(budget.candidates, ["candidate-1"])
            action = session.reconstruct().actions["candidate-1"]
            self.assertEqual(action["exit_code"], 252)
            artifact = root / "raw-artifacts" / action["command_artifact"]["path"]
            self.assertEqual(artifact.read_text(), candidate(1).script)

    def test_recoverable_policy_output_failure_is_feedback_not_termination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            policy = RecoveringPolicy()

            result = self.loop(session, 1).run(
                policy,
                QueueEnvironmentProvider(),
                QueueVerifier([outcome(1, True)]),
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.candidates_attempted, 1)
            self.assertEqual(len(policy.observed_states), 2)
            self.assertIn(
                "candidate-policy-output",
                {
                    item["category"]
                    for item in policy.observed_states[1].failures.values()
                },
            )

    def test_rejected_candidate_can_be_repaired_within_candidate_budget(self) -> None:
        class RejectFirstValidator:
            def validate(self, proposed: DeploymentCandidate) -> CandidateValidation:
                if proposed.candidate_id == "candidate-1":
                    return CandidateValidation(
                        False,
                        "reject-first-validator",
                        reason="unsupported first candidate",
                    )
                return CandidateValidation(
                    True,
                    "reject-first-validator",
                    normalized_script=proposed.script,
                )

        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            budget = RecordingBudget()
            loop = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=2,
                candidate_validator=RejectFirstValidator(),
                budget=budget,
            )

            result = loop.run(
                RecordingPolicy([candidate(1), candidate(2)]),
                QueueEnvironmentProvider(),
                QueueVerifier([outcome(2, True)]),
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.candidates_attempted, 2)
            self.assertEqual(budget.candidates, ["candidate-1", "candidate-2"])
            self.assertEqual(budget.environments, ["candidate-2"])
            self.assertIn(
                "candidate-validation-reject",
                {item["category"] for item in session.reconstruct().failures.values()},
            )

    def test_unobserved_prior_facts_remain_in_active_constraint_view(self) -> None:
        first_failure = (
            CounterexampleEvidence(
                "module-requirement", {"name": "dependency_a", "present": True}
            ),
            CounterexampleEvidence(
                "module-observation", {"name": "dependency_a", "present": False}
            ),
        )
        second_failure = (
            CounterexampleEvidence(
                "module-requirement", {"name": "dependency_b", "present": True}
            ),
            CounterexampleEvidence(
                "module-observation", {"name": "dependency_b", "present": False}
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            policy = RecordingPolicy([candidate(1), candidate(2), candidate(3)])
            result = self.loop(session, 3).run(
                policy,
                QueueEnvironmentProvider(),
                QueueVerifier(
                    [
                        outcome(1, False, counterexamples=first_failure),
                        outcome(2, False, counterexamples=second_failure),
                        outcome(3, True),
                    ]
                ),
            )

            third_state = policy.observed_states[2]
            active_facts = [
                json.loads(item["expression"])
                for item in third_state.constraints.values()
                if item["status"] != "superseded"
                and json.loads(item["expression"])["role"] == "fact"
            ]
            self.assertEqual(len(active_facts), 2)
            self.assertEqual(
                {(item["subject"], item["scope_id"]) for item in active_facts},
                {
                    ("dependency_a", "candidate-1"),
                    ("dependency_b", "candidate-2"),
                },
            )
            self.assertEqual(result.goal_status, "satisfied")
            self.assertNotIn(
                "violated",
                {item["status"] for item in session.reconstruct().constraints.values()},
            )

    def test_grounded_hypothesis_can_rank_the_next_candidate_without_hard_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            policy = RecordingPolicy([candidate(1), candidate(2)])
            result = self.loop(session, 2).run(
                policy,
                QueueEnvironmentProvider(),
                QueueVerifier(
                    [
                        ExecutableVerification(
                            verifier="synthetic-goal-verifier",
                            check_profile="synthetic-complete-check",
                            channel=FeedbackChannel.INTERNAL_EXECUTION,
                            passed=False,
                            bootstrap=CommandResult(1),
                            summary="ambiguous internal failure",
                            hypotheses=(
                                HypothesisEvidence(
                                    "hypothesis-build-backend",
                                    "The build backend may be unavailable",
                                    {"backend": "demo"},
                                ),
                            ),
                        ),
                        outcome(2, True),
                    ]
                ),
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(len(policy.observed_states), 2)
            self.assertIn(
                "hypothesis-build-backend", policy.observed_states[1].hypotheses
            )
            self.assertFalse(policy.observed_states[1].constraints)
            evidence = session.reconstruct().evidence[
                "hypothesis-evidence-candidate-1-0001"
            ]
            self.assertEqual(evidence["candidate_id"], "candidate-1")
            self.assertEqual(evidence["environment_id"], "fresh-env-1")


if __name__ == "__main__":
    unittest.main()
