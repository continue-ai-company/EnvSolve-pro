from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from envsolve.constraints import ConstraintRole, NormalizedConstraint
from envsolve.repairs import (
    RepairConstraintEngine,
    RepairContext,
    RepairRegistry,
    TypedRepairPolicy,
    preflight_repair,
)
from envsolve.solver import (
    CommandResult,
    SolverStateSession,
    StatefulSolverLoop,
)


CASE = {
    "case_id": "synthetic/typed-repair@v1",
    "repository": "synthetic/typed-repair",
    "revision": "v1",
    "language": "python",
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


class RepairTestCase(unittest.TestCase):
    def session(self, root: Path) -> SolverStateSession:
        return SolverStateSession(
            root / "state.jsonl",
            root / "snapshot.json",
            CASE,
        )

    @staticmethod
    def evidence(
        session: SolverStateSession,
        kind: str,
        value: object,
    ) -> str:
        return session.record_evidence(kind, "synthetic-test", value)

    def runtime_conflict(
        self,
        session: SolverStateSession,
    ) -> tuple[RepairConstraintEngine, str]:
        self.evidence(session, "runtime-requirement", ">=3.8,<3.12")
        self.evidence(session, "runtime-observation", {"version": "3.13.2"})
        context_evidence = self.evidence(
            session,
            "repair-context",
            {"runtime_manager": "pyenv", "versions": ["3.10.14", "3.11.9"]},
        )
        engine = RepairConstraintEngine()
        engine.propagate(session)
        return engine, context_evidence

    def capability_conflict(
        self,
        session: SolverStateSession,
    ) -> tuple[RepairConstraintEngine, str]:
        self.evidence(
            session,
            "capability-requirement",
            {"name": "demo-config", "present": True},
        )
        self.evidence(
            session,
            "capability-observation",
            {"name": "demo-config", "present": False},
        )
        context_evidence = self.evidence(
            session,
            "repair-context",
            {"manager": "apt-get", "package": "libdemo-dev"},
        )
        engine = RepairConstraintEngine()
        engine.propagate(session)
        return engine, context_evidence

    def module_conflict(
        self,
        session: SolverStateSession,
    ) -> tuple[RepairConstraintEngine, str]:
        self.evidence(
            session,
            "module-requirement",
            {"name": "demo_plugin", "present": True},
        )
        self.evidence(
            session,
            "module-observation",
            {"name": "demo_plugin", "present": False},
        )
        context_evidence = self.evidence(
            session,
            "repair-context",
            {"module": "demo_plugin", "distribution": "demo-plugin>=1"},
        )
        engine = RepairConstraintEngine()
        engine.propagate(session)
        return engine, context_evidence


class RepairRegistryTest(RepairTestCase):
    def test_runtime_plan_is_stable_and_selects_highest_compatible_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, evidence_id = self.runtime_conflict(session)
            first = RepairContext(
                runtime_manager="pyenv",
                available_python_versions=("3.11.9", "3.10.14"),
                evidence_ids=(evidence_id,),
            )
            second = RepairContext(
                runtime_manager="pyenv",
                available_python_versions=("3.10.14", "3.11.9"),
                evidence_ids=(evidence_id,),
            )
            registry = RepairRegistry()
            plan = registry.propose(session.reconstruct(), first, engine)[0]
            reordered = registry.propose(session.reconstruct(), second, engine)[0]

            self.assertEqual(plan.repair_id, reordered.repair_id)
            self.assertEqual(plan.proposed_fact.value, "3.11.9")
            self.assertEqual(plan.mutation_command, "pyenv local 3.11.9 && hash -r")
            self.assertTrue(preflight_repair(session.reconstruct(), plan, engine).allowed)

    def test_runtime_operator_requires_an_observed_compatible_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, evidence_id = self.runtime_conflict(session)
            context = RepairContext(
                runtime_manager="pyenv",
                available_python_versions=("3.12.8", "3.13.2"),
                evidence_ids=(evidence_id,),
            )

            self.assertEqual(
                RepairRegistry().propose(session.reconstruct(), context, engine),
                (),
            )

    def test_coverage_distinguishes_operator_match_from_missing_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, _ = self.runtime_conflict(session)
            registry = RepairRegistry()

            coverage = registry.coverage(
                session.reconstruct(),
                RepairContext(),
                engine,
            )
            self.assertEqual(len(coverage), 1)
            self.assertEqual(coverage[0]["operator_kinds"], ["runtime_selection"])
            self.assertEqual(
                coverage[0]["missing_context"],
                ["available_python_versions", "evidence_ids", "runtime_manager:pyenv"],
            )
            self.assertEqual(
                registry.propose(session.reconstruct(), RepairContext(), engine),
                (),
            )

    def test_registry_rejects_context_values_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, _ = self.runtime_conflict(session)
            ungrounded = RepairContext(
                runtime_manager="pyenv",
                available_python_versions=("3.11.9",),
            )

            self.assertEqual(
                RepairRegistry().propose(session.reconstruct(), ungrounded, engine),
                (),
            )

    def test_capability_operator_does_not_guess_a_system_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, evidence_id = self.capability_conflict(session)
            registry = RepairRegistry()
            empty = RepairContext(
                system_package_manager="apt-get",
                evidence_ids=(evidence_id,),
            )
            mapped = RepairContext(
                system_package_manager="apt-get",
                capability_packages={"demo-config": ("libdemo-dev",)},
                evidence_ids=(evidence_id,),
            )

            self.assertEqual(registry.propose(session.reconstruct(), empty, engine), ())
            plan = registry.propose(session.reconstruct(), mapped, engine)[0]
            self.assertEqual(
                plan.mutation_command,
                "apt-get install -y -- libdemo-dev",
            )
            self.assertEqual(plan.probe.command, "command -v -- demo-config")

    def test_module_operator_does_not_equate_import_and_distribution_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, evidence_id = self.module_conflict(session)
            registry = RepairRegistry()
            empty = RepairContext(evidence_ids=(evidence_id,))
            mapped = RepairContext(
                module_distributions={"demo_plugin": ("demo-plugin>=1",)},
                evidence_ids=(evidence_id,),
            )

            self.assertEqual(registry.propose(session.reconstruct(), empty, engine), ())
            plan = registry.propose(session.reconstruct(), mapped, engine)[0]
            self.assertEqual(
                plan.mutation_command,
                "python -m pip install 'demo-plugin>=1'",
            )
            self.assertEqual(plan.probe.command, "python -c 'import demo_plugin'")

    def test_preflight_rejects_requirement_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, evidence_id = self.runtime_conflict(session)
            context = RepairContext(
                runtime_manager="pyenv",
                available_python_versions=("3.11.9",),
                evidence_ids=(evidence_id,),
            )
            plan = RepairRegistry().propose(session.reconstruct(), context, engine)[0]
            requirement_id = next(
                item.constraint_id
                for item in engine.typed_constraints(session.reconstruct())
                if item.role == ConstraintRole.REQUIREMENT
            )
            invalid = replace(plan, supersede_constraint_ids=(requirement_id,))

            result = preflight_repair(session.reconstruct(), invalid, engine)
            self.assertFalse(result.allowed)
            self.assertTrue(
                any("cannot supersede a requirement" in reason for reason in result.reasons)
            )

    def test_preflight_rejects_unknown_context_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, evidence_id = self.runtime_conflict(session)
            context = RepairContext(
                runtime_manager="pyenv",
                available_python_versions=("3.11.9",),
                evidence_ids=(evidence_id,),
            )
            plan = RepairRegistry().propose(session.reconstruct(), context, engine)[0]
            invalid = replace(plan, supporting_evidence_ids=("evidence-unknown",))

            result = preflight_repair(session.reconstruct(), invalid, engine)
            self.assertFalse(result.allowed)
            self.assertIn("Unknown supporting evidence", result.reasons[0])


class TypedRepairPolicyTest(RepairTestCase):
    def runtime_plan(
        self,
        session: SolverStateSession,
    ) -> tuple[RepairConstraintEngine, object]:
        engine, evidence_id = self.runtime_conflict(session)
        context = RepairContext(
            runtime_manager="pyenv",
            available_python_versions=("3.11.9",),
            evidence_ids=(evidence_id,),
        )
        plan = RepairRegistry().propose(session.reconstruct(), context, engine)[0]
        return engine, plan

    def test_verified_runtime_repair_supersedes_old_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, plan = self.runtime_plan(session)
            executor = QueueExecutor(
                [
                    CommandResult(0),
                    CommandResult(0, stdout="Python 3.11.9\n"),
                ]
            )
            policy = TypedRepairPolicy(plan, session, engine)
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=3,
                goal_id=f"goal-{plan.repair_id}",
                goal_description="Verify one typed repair",
            ).run(policy)

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.actions_executed, 2)
            state = session.reconstruct()
            self.assertTrue(
                all(
                    state.constraints[item]["status"] == "superseded"
                    for item in plan.supersede_constraint_ids
                )
            )
            report = engine.solve_state(state)
            self.assertTrue(report.satisfiable)
            self.assertEqual(set(report.statuses.values()), {"satisfied"})
            self.assertTrue(state.verifications[-1]["passed"])

    def test_mismatching_probe_preserves_old_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, plan = self.runtime_plan(session)
            executor = QueueExecutor(
                [
                    CommandResult(0),
                    CommandResult(0, stdout="Python 3.13.2\n"),
                ]
            )
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=3,
                goal_id=f"goal-{plan.repair_id}",
            ).run(TypedRepairPolicy(plan, session, engine))

            self.assertEqual(result.goal_status, "blocked")
            state = session.reconstruct()
            self.assertTrue(
                all(
                    state.constraints[item]["status"] != "superseded"
                    for item in plan.supersede_constraint_ids
                )
            )
            self.assertFalse(state.verifications[-1]["passed"])
            self.assertIn(
                "repair-verification-mismatch",
                {item["category"] for item in state.failures.values()},
            )

    def test_failed_mutation_never_runs_probe_or_changes_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, plan = self.runtime_plan(session)
            executor = QueueExecutor([CommandResult(1, stderr="runtime switch failed")])
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=2,
                goal_id=f"goal-{plan.repair_id}",
            ).run(TypedRepairPolicy(plan, session, engine))

            self.assertEqual(result.goal_status, "blocked")
            self.assertEqual(executor.commands, [plan.mutation_command])
            state = session.reconstruct()
            self.assertNotIn(plan.verification_action_id, state.actions)
            self.assertTrue(
                all(
                    state.constraints[item]["status"] != "superseded"
                    for item in plan.supersede_constraint_ids
                )
            )

    def test_failed_capability_probe_records_absence_without_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, evidence_id = self.capability_conflict(session)
            context = RepairContext(
                system_package_manager="apt-get",
                capability_packages={"demo-config": ("libdemo-dev",)},
                evidence_ids=(evidence_id,),
            )
            plan = RepairRegistry().propose(session.reconstruct(), context, engine)[0]
            executor = QueueExecutor([CommandResult(0), CommandResult(1)])
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=3,
                goal_id=f"goal-{plan.repair_id}",
            ).run(TypedRepairPolicy(plan, session, engine))

            self.assertEqual(result.goal_status, "blocked")
            state = session.reconstruct()
            self.assertIn(plan.verification_evidence_id, state.evidence)
            self.assertFalse(
                state.evidence[plan.verification_evidence_id]["value"]["present"]
            )
            self.assertTrue(
                all(
                    state.constraints[item]["status"] != "superseded"
                    for item in plan.supersede_constraint_ids
                )
            )

    def test_policy_resumes_after_both_actions_without_reexecution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine, plan = self.runtime_plan(session)
            setup_executor = QueueExecutor(
                [CommandResult(0), CommandResult(0, stdout="Python 3.11.9")]
            )
            session.execute_action(plan.mutation_action(), setup_executor)
            session.execute_action(plan.verification_action(), setup_executor)
            resume_executor = QueueExecutor([])

            result = StatefulSolverLoop(
                session,
                resume_executor,
                max_actions=1,
                goal_id=f"goal-{plan.repair_id}",
            ).run(TypedRepairPolicy(plan, session, engine))

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.actions_executed, 0)
            self.assertEqual(resume_executor.commands, [])
            self.assertTrue(
                all(
                    session.reconstruct().constraints[item]["status"] == "superseded"
                    for item in plan.supersede_constraint_ids
                )
            )


if __name__ == "__main__":
    unittest.main()
