from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.solver import (
    CandidateValidation,
    CommandResult,
    DeploymentCandidate,
    EnvironmentReceipt,
    ExecutableVerification,
    FeedbackChannel,
    ProvisionedEnvironment,
)
from envsolve.state import EventStore, audit_state_artifacts
from envsolve_harness.core.io import read_json
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.envsolve import EnvSolveEpisodeRunner
from envsolve_harness.storage.artifacts import RunArtifacts


class OneCandidatePolicy:
    def propose(self, state):
        return DeploymentCandidate(
            "candidate-1",
            "python -m pip install -e .\n",
            "Install the project",
        )


class AcceptingValidator:
    def validate(self, candidate):
        return CandidateValidation(True, "test-complete-candidate", candidate.script)


class RecordingBudget:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def reserve_candidate(self, candidate_id: str) -> None:
        self.events.append(("candidate", candidate_id))

    def reserve_environment(self, candidate_id: str) -> None:
        self.events.append(("environment", candidate_id))

    def reserve_command(self, candidate_id: str) -> None:
        self.events.append(("command", candidate_id))

    def finalize(self) -> None:
        self.events.append(("finalize", ""))


class FreshProvider:
    def __init__(self, case: Case) -> None:
        self.case = case
        self.released = False

    def provision(self, candidate):
        return ProvisionedEnvironment(
            EnvironmentReceipt(
                "environment-1",
                "test-provider",
                "sha256:test-image",
                self.case.repository,
                self.case.revision,
                "2026-07-16T00:00:00+00:00",
            )
        )

    def release(self, environment) -> None:
        self.released = True


class PassingVerifier:
    def verify(self, candidate, environment):
        return ExecutableVerification(
            verifier="test-internal-verifier",
            check_profile="test-goal-check-v1",
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=True,
            bootstrap=CommandResult(0, stdout="ready\n"),
            summary="Internal goal checks passed",
        )


class EnvSolveEpisodeRunnerTest(unittest.TestCase):
    def test_writes_replayable_script_and_immutable_episode_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("envsolve-run", "envsolve-full", "test-model", 7)
            artifacts = RunArtifacts.create(
                Path(directory), run_spec.run_id, case.case_id
            )
            provider = FreshProvider(case)
            budget = RecordingBudget()
            runner = EnvSolveEpisodeRunner(
                policy=OneCandidatePolicy(),
                environment_provider=provider,
                verifier=PassingVerifier(),
                candidate_validator=AcceptingValidator(),
                budget=budget,
                max_candidates=2,
            )

            result = runner.run(case, artifacts, run_spec)

            self.assertTrue(result.generation_completed)
            self.assertEqual(
                artifacts.generated_script.read_text(encoding="utf-8"),
                "python -m pip install -e .\n",
            )
            self.assertEqual(
                budget.events,
                [
                    ("candidate", "candidate-1"),
                    ("environment", "candidate-1"),
                    ("command", "candidate-1"),
                    ("finalize", ""),
                ],
            )
            self.assertTrue(provider.released)
            self.assertTrue(artifacts.episode_snapshot.is_file())
            self.assertTrue(any(artifacts.raw_artifacts.rglob("*.sh")))
            self.assertTrue(any(artifacts.raw_artifacts.rglob("*.txt")))
            self.assertEqual(read_json(artifacts.status)["state"], "generated")
            persisted = read_json(artifacts.solver_result)
            self.assertEqual(
                persisted["metadata"]["official_evaluator_access"],
                "post-episode-only",
            )
            events = EventStore(artifacts.episode_event_log, case.case_id).read()
            self.assertTrue(
                all(
                    event.payload["trace"]["run_id"] == run_spec.run_id
                    for event in events
                )
            )
            self.assertTrue(
                audit_state_artifacts(
                    artifacts.episode_event_log,
                    artifacts.episode_snapshot,
                    case.case_id,
                ).valid
            )


if __name__ == "__main__":
    unittest.main()
