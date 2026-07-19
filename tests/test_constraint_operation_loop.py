from pathlib import Path
import tempfile
import unittest

from envsolve.solver import (
    CommandResult,
    CounterexampleEvidence,
    CounterexampleGuidedDeploymentLoop,
    DeploymentCandidate,
    EnvironmentReceipt,
    ExecutableVerification,
    FeedbackChannel,
    HypothesisEvidence,
    ProvisionedEnvironment,
    SolverStateSession,
)
from envsolve_harness.scripts import (
    ConstraintOperationGuard,
    TypedReplayCandidateValidator,
)
from envsolve.state import EnvironmentState


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


class CandidateQueue:
    def __init__(self) -> None:
        self.index = 0
        self.scripts = (
            "python -m venv .venv\n"
            "source .venv/bin/activate\n"
            "python -m pip install demo-base",
            "python -m venv .venv\n"
            "source .venv/bin/activate\n"
            "python -m pip install demo-base\n"
            "python -m pip install demo-module-package",
            "python -m venv .venv\n"
            "source .venv/bin/activate\n"
            "apt-get install -y -- demo-system-package\n"
            "python -m pip install demo-base\n"
            "python -m pip install demo-module-package",
        )

    def propose(self, state):
        script = self.scripts[self.index]
        self.index += 1
        return DeploymentCandidate(
            f"candidate-{self.index}",
            script,
            "Synthetic cumulative deployment candidate",
        )


class RecordingProvider:
    def __init__(self) -> None:
        self.provisioned: list[str] = []
        self.released: list[str] = []

    def provision(self, candidate: DeploymentCandidate) -> ProvisionedEnvironment:
        self.provisioned.append(candidate.candidate_id)
        return ProvisionedEnvironment(
            EnvironmentReceipt(
                environment_id=f"environment-{candidate.candidate_id}",
                provider_id="synthetic-provider",
                image_digest="sha256:" + "b" * 64,
                repository="example/project",
                revision="a" * 40,
                created_at="2026-07-17T00:00:00+00:00",
            )
        )

    def release(self, environment: ProvisionedEnvironment) -> None:
        self.released.append(environment.receipt.environment_id)


class TwoStepVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, candidate, environment):
        self.calls += 1
        if self.calls == 1:
            return ExecutableVerification(
                verifier="synthetic-verifier",
                check_profile="synthetic-profile",
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=CommandResult(0),
                summary="demo_module is missing",
                counterexamples=(
                    CounterexampleEvidence(
                        "module-requirement",
                        {"name": "demo_module", "present": True},
                    ),
                    CounterexampleEvidence(
                        "module-observation",
                        {"name": "demo_module", "present": False},
                    ),
                    CounterexampleEvidence(
                        "capability-requirement",
                        {"name": "demo-compiler", "present": True},
                    ),
                    CounterexampleEvidence(
                        "capability-observation",
                        {"name": "demo-compiler", "present": False},
                    ),
                ),
            )
        return ExecutableVerification(
            verifier="synthetic-verifier",
            check_profile="synthetic-profile",
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=True,
            bootstrap=CommandResult(0),
            summary="deployment verified",
        )


class PersistentConflictQueue:
    def __init__(self) -> None:
        self.index = 0
        self.scripts = (
            "python -m pip install demo-base",
            "python -m pip install demo-base\npython -m pip install repair-one",
            "python -m pip install demo-base\npython -m pip install repair-one",
            "python -m pip install demo-base\n"
            "python -m pip install repair-one\n"
            "python -m pip install repair-two",
        )

    def propose(self, state):
        script = self.scripts[self.index]
        self.index += 1
        return DeploymentCandidate(
            f"persistent-candidate-{self.index}",
            script,
            "Synthetic persistent-conflict candidate",
        )


class HypothesisThenPassVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, candidate, environment):
        self.calls += 1
        if self.calls == 1:
            return ExecutableVerification(
                verifier="synthetic-verifier",
                check_profile="synthetic-profile",
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=CommandResult(0),
                summary="demo_module is missing",
                counterexamples=(
                    CounterexampleEvidence(
                        "module-requirement",
                        {"name": "demo_module", "present": True},
                    ),
                    CounterexampleEvidence(
                        "module-observation",
                        {"name": "demo_module", "present": False},
                    ),
                ),
            )
        if self.calls == 2:
            return ExecutableVerification(
                verifier="synthetic-verifier",
                check_profile="synthetic-profile",
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=CommandResult(1, stderr="ambiguous bootstrap failure"),
                summary="candidate failed before the module could be observed",
                hypotheses=(
                    HypothesisEvidence(
                        "bootstrap-failure",
                        "The candidate failed before complete verification",
                        {"exit_code": 1},
                        0.6,
                    ),
                ),
            )
        return ExecutableVerification(
            verifier="synthetic-verifier",
            check_profile="synthetic-profile",
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=True,
            bootstrap=CommandResult(0),
            summary="deployment verified",
        )


class RuntimeMismatchQueue:
    def __init__(self) -> None:
        self.index = 0
        self.scripts = (
            "python -m pip install -e .",
            "pyenv install 3.10.15\n"
            "pyenv global 3.10.15\n"
            "python -m pip install -e .",
        )

    def propose(self, state):
        script = self.scripts[self.index]
        self.index += 1
        return DeploymentCandidate(
            f"runtime-candidate-{self.index}",
            script,
            "Repair the observed runtime mismatch",
        )


class RuntimeMismatchThenPassVerifier:
    diagnostic = (
        "Package 'demo' requires a different Python: "
        "3.13.2 not in '<3.13,>=3.10'"
    )

    def __init__(self) -> None:
        self.calls = 0

    def verify(self, candidate, environment):
        self.calls += 1
        if self.calls == 1:
            return ExecutableVerification(
                verifier="synthetic-verifier",
                check_profile="synthetic-profile",
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=CommandResult(
                    1,
                    stderr=self.diagnostic,
                ),
                summary="base runtime is incompatible",
                hypotheses=(
                    HypothesisEvidence(
                        "runtime-mismatch",
                        "The base Python version is incompatible",
                        {"exit_code": 1},
                        1.0,
                    ),
                ),
            )
        return ExecutableVerification(
            verifier="synthetic-verifier",
            check_profile="synthetic-profile",
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=True,
            bootstrap=CommandResult(0),
            summary="deployment verified",
        )


class SubjectFirstRuntimeMismatchThenPassVerifier(RuntimeMismatchThenPassVerifier):
    diagnostic = (
        "Current Python version (3.13.2) is not allowed by the "
        "project (>=3.8,<3.11)."
    )


class ConstraintOperationLoopTest(unittest.TestCase):
    def test_runtime_mismatch_action_result_becomes_a_hard_operation_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "events.jsonl",
                root / "snapshot.json",
                {
                    "case_id": "runtime-action-result",
                    "repository": "example/project",
                    "revision": "a" * 40,
                },
            )
            provider = RecordingProvider()
            result = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=2,
                candidate_validator=TypedReplayCandidateValidator(),
                operation_guard=ConstraintOperationGuard(),
                budget=RecordingBudget(),
            ).run(RuntimeMismatchQueue(), provider, RuntimeMismatchThenPassVerifier())

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.constraints_updated, 2)
            self.assertEqual(
                provider.provisioned,
                ["runtime-candidate-1", "runtime-candidate-2"],
            )
            guard = session.reconstruct().actions["runtime-candidate-2"]["metadata"][
                "operation_guard"
            ]
            self.assertTrue(guard["accepted"])
            self.assertEqual(guard["plan"]["requirements"][0]["domain"], "runtime")
            self.assertEqual(
                guard["plan"]["requirements"][0]["allowed_operation_kinds"],
                ["runtime_configure"],
            )

    def test_subject_first_runtime_mismatch_drives_runtime_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "events.jsonl",
                root / "snapshot.json",
                {
                    "case_id": "subject-first-runtime-action-result",
                    "repository": "example/project",
                    "revision": "a" * 40,
                },
            )
            provider = RecordingProvider()
            result = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=2,
                candidate_validator=TypedReplayCandidateValidator(),
                operation_guard=ConstraintOperationGuard(),
                budget=RecordingBudget(),
            ).run(
                RuntimeMismatchQueue(),
                provider,
                SubjectFirstRuntimeMismatchThenPassVerifier(),
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.constraints_updated, 2)
            guard = session.reconstruct().actions["runtime-candidate-2"]["metadata"][
                "operation_guard"
            ]
            self.assertTrue(guard["accepted"])
            self.assertEqual(
                guard["plan"]["requirements"][0]["allowed_operation_kinds"],
                ["runtime_configure"],
            )

    def test_guard_rejects_failed_prefix_but_allows_a_change_before_failure(self) -> None:
        state = EnvironmentState(
            "failed-prefix",
            case={
                "case_id": "failed-prefix",
                "repository": "example/project",
                "revision": "a" * 40,
            },
        )
        state.verifications.append(
            {
                "verification_id": "verification-candidate-1",
                "passed": False,
                "details": {
                    "candidate_id": "candidate-1",
                    "verifier_details": {
                        "failed_candidate_action": {
                            "prefix_commands": [
                                "python -m pip install prerequisite",
                                "python -m pip install -e .",
                            ]
                        }
                    },
                },
            }
        )
        guard = ConstraintOperationGuard()

        repeated = guard.validate(
            DeploymentCandidate(
                "candidate-2",
                "python -m pip install prerequisite\n"
                "python -m pip install -e .\n"
                "python -m pip install repair-after-failure",
                "append too late",
            ),
            state,
        )
        changed = guard.validate(
            DeploymentCandidate(
                "candidate-3",
                "python -m pip install prerequisite\n"
                "python -m pip install repair-before-failure\n"
                "python -m pip install -e .",
                "change before the failed command",
            ),
            state,
        )

        self.assertFalse(repeated.accepted)
        self.assertEqual(
            repeated.details["repeated_failed_attempts"],
            [{"candidate_id": "candidate-1", "mode": "failed-prefix"}],
        )
        self.assertTrue(changed.accepted)

    def test_conflict_requires_a_new_permitted_operation_before_fresh_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "events.jsonl",
                root / "snapshot.json",
                {
                    "case_id": "operation-loop",
                    "repository": "example/project",
                    "revision": "a" * 40,
                },
            )
            budget = RecordingBudget()
            provider = RecordingProvider()
            verifier = TwoStepVerifier()
            result = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=3,
                candidate_validator=TypedReplayCandidateValidator(),
                operation_guard=ConstraintOperationGuard(),
                budget=budget,
            ).run(CandidateQueue(), provider, verifier)

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.accepted_candidate.candidate_id, "candidate-3")
            self.assertEqual(provider.provisioned, ["candidate-1", "candidate-3"])
            self.assertEqual(budget.environments, ["candidate-1", "candidate-3"])
            state = session.reconstruct()
            rejected = state.actions["candidate-2"]
            self.assertEqual(rejected["exit_code"], 251)
            self.assertIn("operation_guard", rejected["metadata"])
            self.assertEqual(
                rejected["metadata"]["operation_guard"]["details"][
                    "new_actions"
                ]["python_package_install"],
                ["python -m pip install demo-module-package"],
            )
            self.assertIn(
                "candidate-operation-reject",
                {item["category"] for item in state.failures.values()},
            )
            accepted = state.actions["candidate-3"]
            guard = accepted["metadata"]["operation_guard"]
            self.assertTrue(guard["accepted"])
            self.assertTrue(
                guard["plan"]["requirements"][0]["source_constraint_ids"]
            )
            self.assertEqual(
                guard["details"]["new_actions"]["python_package_install"],
                ["python -m pip install demo-module-package"],
            )
            self.assertEqual(
                guard["details"]["new_actions"]["system_package_install"],
                ["apt-get install -y -- demo-system-package"],
            )

    def test_hypothesis_only_failure_preserves_prior_operation_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "events.jsonl",
                root / "snapshot.json",
                {
                    "case_id": "persistent-operation-loop",
                    "repository": "example/project",
                    "revision": "a" * 40,
                },
            )
            budget = RecordingBudget()
            provider = RecordingProvider()
            verifier = HypothesisThenPassVerifier()
            result = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=4,
                candidate_validator=TypedReplayCandidateValidator(),
                operation_guard=ConstraintOperationGuard(),
                budget=budget,
            ).run(PersistentConflictQueue(), provider, verifier)

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(
                result.accepted_candidate.candidate_id,
                "persistent-candidate-4",
            )
            self.assertEqual(
                provider.provisioned,
                [
                    "persistent-candidate-1",
                    "persistent-candidate-2",
                    "persistent-candidate-4",
                ],
            )
            state = session.reconstruct()
            rejected = state.actions["persistent-candidate-3"]
            self.assertEqual(rejected["exit_code"], 251)
            self.assertTrue(
                rejected["metadata"]["operation_guard"]["plan"]["requirements"]
            )


if __name__ == "__main__":
    unittest.main()
