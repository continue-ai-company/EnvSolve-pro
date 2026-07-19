from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest

from envsolve.integrations import ingest_shell_command_trace
from envsolve.solver import (
    ActionSpec,
    CommandResult,
    SolverStateSession,
    StatefulSolverLoop,
    StopDecision,
)
from envsolve.state import audit_state_artifacts


CASE = {
    "case_id": "owner/repo@abc",
    "repository": "owner/repo",
    "revision": "abc",
    "language": "python",
    "split": "synthetic",
    "tags": [],
}


class QueueExecutor:
    def __init__(self, results: list[CommandResult | Exception]) -> None:
        self.results = list(results)
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class ScriptedPolicy:
    def __init__(self, decisions: list[ActionSpec | StopDecision | Exception]) -> None:
        self.decisions = list(decisions)

    def next_step(self, state):
        decision = self.decisions.pop(0)
        if isinstance(decision, Exception):
            raise decision
        return decision


@dataclass(frozen=True)
class FakeTraceAction:
    kind: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind}


@dataclass(frozen=True)
class FakeTraceAnalysis:
    actions: tuple[FakeTraceAction, ...] = ()
    dropped: bool = False
    unsupported_reason: str | None = None


def analyze_trace(command: str, project_directory: str | None = None) -> FakeTraceAnalysis:
    del project_directory
    if command == "ls -la":
        return FakeTraceAnalysis(dropped=True)
    if "pip install" in command:
        return FakeTraceAnalysis((FakeTraceAction("python_package_install"),))
    return FakeTraceAnalysis(unsupported_reason="unsupported by synthetic analyzer")


class SolverStateSessionTest(unittest.TestCase):
    def _session(self, root: Path) -> SolverStateSession:
        return SolverStateSession(
            root / "state.jsonl",
            root / "snapshot.json",
            CASE,
        )

    def test_live_action_lifecycle_is_reconstructable_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = self._session(root)
            session.profile_repository({"packaging": ["pyproject.toml"]})
            evidence_id = session.record_evidence(
                kind="runtime-requirement",
                source="pyproject.toml",
                value={"python": ">=3.10"},
            )
            session.upsert_constraint(
                "python-runtime",
                "runtime",
                "python>=3.10",
                "active",
                [evidence_id],
            )
            session.upsert_goal("environment-ready", "Build a usable environment", "in_progress")
            executor = QueueExecutor(
                [
                    CommandResult(0, stdout="installed", duration_seconds=1.5),
                    CommandResult(2, stderr="missing system library"),
                ]
            )
            session.execute_action(
                ActionSpec(
                    "python_package_install",
                    "python -m pip install -e .",
                    "Install project metadata",
                    ("python-runtime",),
                ),
                executor,
            )
            session.execute_action(
                ActionSpec(
                    "verification",
                    "python -m pytest",
                    "Check the installed environment",
                ),
                executor,
            )
            session.record_verification(
                "V2",
                "synthetic-import-check",
                False,
                {"missing": ["native_dependency"]},
            )

            state = session.reconstruct()
            self.assertEqual(
                [action["status"] for action in state.actions.values()],
                ["succeeded", "failed"],
            )
            self.assertEqual(len(state.failures), 1)
            self.assertEqual(len(state.evidence), 3)
            self.assertEqual(len(state.verifications), 1)
            report = audit_state_artifacts(
                root / "state.jsonl",
                root / "snapshot.json",
                CASE["case_id"],
            )
            self.assertTrue(report.valid, report.errors)
            self.assertEqual(
                json.loads((root / "snapshot.json").read_text()),
                state.to_dict(),
            )

    def test_executor_exception_is_terminal_and_secrets_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = self._session(root)
            secret = "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz123456"
            executor = QueueExecutor([RuntimeError(f"provider rejected {secret}")])
            result = session.execute_action(
                ActionSpec(
                    "provider-probe",
                    f"client --key {secret}",
                    "Exercise exception recording",
                ),
                executor,
            )
            session.record_evidence(
                "provider-output",
                "synthetic",
                {"nested": [f"response contained {secret}"]},
            )

            self.assertEqual(result.exit_code, 255)
            snapshot = (root / "snapshot.json").read_text()
            self.assertNotIn(secret, snapshot)
            self.assertIn("[REDACTED]", snapshot)
            state = session.reconstruct()
            self.assertEqual(next(iter(state.actions.values()))["status"], "failed")
            self.assertEqual(next(iter(state.failures.values()))["category"], "executor-exception")

    def test_complete_outputs_are_content_addressed_and_events_are_episode_traced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "state.jsonl",
                root / "snapshot.json",
                CASE,
                run_id="run-test",
                episode_id="episode-test",
            )
            output = "x" * 20_000
            session.record_action_result(
                ActionSpec("probe", "python -m pip install demo", "Synthetic action"),
                CommandResult(1, stdout=output),
            )

            state = session.reconstruct()
            action = next(iter(state.actions.values()))
            self.assertIn("truncated", action["observation"]["stdout"])
            artifact = action["observation"]["stdout_artifact"]
            stored = root / "raw-artifacts" / artifact["path"]
            self.assertEqual(stored.read_text(encoding="utf-8"), output)
            self.assertEqual(artifact["size_bytes"], len(output))
            for event in session.store.read():
                self.assertEqual(event.payload["trace"]["run_id"], "run-test")
                self.assertEqual(event.payload["trace"]["episode_id"], "episode-test")
                self.assertTrue(event.payload["trace"]["step_id"].startswith("step-"))

    def test_session_resume_does_not_append_a_second_run_started(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = self._session(root)
            first_count = len(session.store.read())
            resumed = self._session(root)
            self.assertEqual(len(resumed.store.read()), first_count)

    def test_session_cache_observes_events_appended_by_another_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._session(root)
            second = self._session(root)
            first.record_evidence("first", "synthetic", {"value": 1})
            second.record_evidence("second", "synthetic", {"value": 2})

            state = first.reconstruct()

            self.assertEqual(
                {item["kind"] for item in state.evidence.values()},
                {"first", "second"},
            )

    def test_state_audit_rejects_a_tampered_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._session(root)
            snapshot_path = root / "snapshot.json"
            snapshot = json.loads(snapshot_path.read_text())
            snapshot["case"]["revision"] = "tampered"
            snapshot_path.write_text(json.dumps(snapshot) + "\n")

            report = audit_state_artifacts(
                root / "state.jsonl",
                snapshot_path,
                CASE["case_id"],
            )
            self.assertFalse(report.valid)
            self.assertIn(
                "Persisted state snapshot does not match event reconstruction",
                report.errors,
            )


class StatefulSolverLoopTest(unittest.TestCase):
    def test_policy_can_only_advance_through_recorded_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "state.jsonl",
                root / "snapshot.json",
                CASE,
            )
            executor = QueueExecutor(
                [
                    CommandResult(0, stdout="installed"),
                    CommandResult(1, stderr="verification failed"),
                ]
            )
            policy = ScriptedPolicy(
                [
                    ActionSpec("install", "pip install -e .", "Install project"),
                    ActionSpec("verify", "python -m pytest", "Verify project"),
                    StopDecision("No further safe action", "satisfied"),
                ]
            )
            result = StatefulSolverLoop(session, executor, max_actions=3).run(policy)

            self.assertEqual(result.actions_executed, 2)
            self.assertEqual(result.actions_succeeded, 1)
            self.assertEqual(result.actions_failed, 1)
            state = session.reconstruct()
            self.assertEqual(state.goals["environment-ready"]["status"], "satisfied")
            self.assertEqual(len(state.actions), 2)
            self.assertEqual(len(state.evidence), 2)
            self.assertEqual(len(state.failures), 1)
            self.assertTrue(
                audit_state_artifacts(
                    root / "state.jsonl",
                    root / "snapshot.json",
                    CASE["case_id"],
                ).valid
            )

    def test_action_budget_becomes_a_blocked_goal_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "state.jsonl",
                root / "snapshot.json",
                CASE,
            )
            executor = QueueExecutor([CommandResult(0)])
            policy = ScriptedPolicy(
                [ActionSpec("probe", "python --version", "Inspect runtime")]
            )
            result = StatefulSolverLoop(session, executor, max_actions=1).run(policy)

            self.assertEqual(result.goal_status, "blocked")
            self.assertEqual(result.stop_reason, "action budget exhausted")
            state = session.reconstruct()
            self.assertEqual(state.goals["environment-ready"]["status"], "blocked")
            self.assertEqual(
                [failure["category"] for failure in state.failures.values()],
                ["action-budget"],
            )
            self.assertTrue(
                audit_state_artifacts(
                    root / "state.jsonl",
                    root / "snapshot.json",
                    CASE["case_id"],
                ).valid
            )


class ShellTraceIntegrationTest(unittest.TestCase):
    def test_every_shell_interaction_becomes_an_action_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "state.jsonl",
                root / "snapshot.json",
                CASE,
            )
            summary = ingest_shell_command_trace(
                session,
                [
                    {"command": "ls -la", "exit_code": 0},
                    {"command": "python -m pip install broken", "exit_code": 1},
                    {"command": "python -m pip install -e .", "exit_code": 0},
                    {"command": "touch arbitrary-file", "exit_code": 0},
                ],
                source="synthetic-trajectory",
                analyzer=analyze_trace,
            )

            self.assertEqual(
                summary.to_dict(),
                {
                    "commands": 4,
                    "typed_actions": 2,
                    "observations": 1,
                    "unsupported": 1,
                    "failed": 1,
                },
            )
            state = session.reconstruct()
            self.assertEqual(len(state.actions), 4)
            self.assertEqual(len(state.evidence), 4)
            self.assertEqual(len(state.failures), 1)
            self.assertTrue(
                audit_state_artifacts(
                    root / "state.jsonl",
                    root / "snapshot.json",
                    CASE["case_id"],
                ).valid
            )


if __name__ == "__main__":
    unittest.main()
