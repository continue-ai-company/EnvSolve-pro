from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.repairs import RepairConstraintEngine, RepairContext, RepairRegistry
from envsolve.solver import CommandResult, SolverStateSession, StatefulSolverLoop
from envsolve.verification import SemanticCapabilityRepairPolicy


CASE = {
    "case_id": "synthetic:semantic-capability",
    "repository": "owner/repo",
    "revision": "abc",
    "language": "infrastructure",
    "split": "synthetic",
    "tags": [],
}


class QueueExecutor:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = list(results)
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        return self.results.pop(0)


class SemanticCapabilityPolicyTest(unittest.TestCase):
    @staticmethod
    def plan(session: SolverStateSession):
        session.record_evidence(
            "capability-requirement",
            "synthetic",
            {"name": "demo-config", "present": True},
        )
        session.record_evidence(
            "capability-observation",
            "synthetic",
            {"name": "demo-config", "present": False},
        )
        context_id = session.record_evidence(
            "repair-context",
            "synthetic",
            {"package": "libdemo-dev"},
        )
        engine = RepairConstraintEngine()
        engine.propagate(session)
        context = RepairContext(
            system_package_manager="apt-get",
            capability_packages={"demo-config": ("libdemo-dev",)},
            evidence_ids=(context_id,),
        )
        return engine, RepairRegistry().propose(session.reconstruct(), context, engine)[0]

    def test_v2_success_commits_fact_after_three_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(root / "state.jsonl", root / "snapshot.json", CASE)
            engine, plan = self.plan(session)
            executor = QueueExecutor(
                [
                    CommandResult(0),
                    CommandResult(0, stdout="/usr/bin/demo-config\n"),
                    CommandResult(0, stdout="demo 1.0\n"),
                ]
            )
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=4,
                goal_id="goal-v2",
            ).run(
                SemanticCapabilityRepairPolicy(
                    plan,
                    session,
                    "demo-config --version",
                    engine,
                )
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.actions_executed, 3)
            self.assertTrue(engine.solve_state(session.reconstruct()).satisfiable)
            self.assertTrue(session.reconstruct().verifications[-1]["passed"])

    def test_v2_failure_preserves_old_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(root / "state.jsonl", root / "snapshot.json", CASE)
            engine, plan = self.plan(session)
            executor = QueueExecutor(
                [
                    CommandResult(0),
                    CommandResult(0, stdout="/usr/bin/demo-config\n"),
                    CommandResult(1, stderr="backend missing\n"),
                ]
            )
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=4,
                goal_id="goal-v2",
            ).run(
                SemanticCapabilityRepairPolicy(
                    plan,
                    session,
                    "demo-config self-test",
                    engine,
                )
            )

            self.assertEqual(result.goal_status, "blocked")
            self.assertFalse(engine.solve_state(session.reconstruct()).satisfiable)
            self.assertTrue(
                all(
                    session.reconstruct().constraints[item]["status"] != "superseded"
                    for item in plan.supersede_constraint_ids
                )
            )
            self.assertFalse(session.reconstruct().verifications[-1]["passed"])


if __name__ == "__main__":
    unittest.main()
