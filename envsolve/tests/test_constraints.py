from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from envsolve.constraints import (
    ConstraintCheckedPolicy,
    ConstraintDomain,
    ConstraintEngine,
    ConstraintPredicate,
    ConstraintRole,
    NormalizedConstraint,
    PreflightDisposition,
    preflight_action,
)
from envsolve.solver import (
    ActionSpec,
    CommandResult,
    SolverStateSession,
    StatefulSolverLoop,
    StopDecision,
)


CASE = {
    "case_id": "synthetic/constraints@v1",
    "repository": "synthetic/constraints",
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


class ScriptedPolicy:
    def __init__(self, decisions: list[ActionSpec | StopDecision]) -> None:
        self.decisions = list(decisions)

    def next_step(self, state):
        return self.decisions.pop(0)


class ConstraintTestCase(unittest.TestCase):
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
        confidence: float = 1.0,
    ) -> str:
        return session.record_evidence(
            kind=kind,
            source="synthetic-test",
            value=value,
            confidence=confidence,
        )


class NormalizationAndPropagationTest(ConstraintTestCase):
    def test_new_observation_supersedes_only_the_same_scoped_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            engine = ConstraintEngine()
            first_evidence = self.evidence(
                session,
                "module-observation",
                {"name": "dependency_a", "present": False},
            )
            first_ids = engine.ingest_evidence(
                session,
                first_evidence,
                fact_scope="candidate-1",
            )
            prior_fact_ids = engine.fact_constraint_ids(session.reconstruct())
            second_evidence = self.evidence(
                session,
                "module-observation",
                {"name": "dependency_a", "present": True},
            )
            second_ids = engine.ingest_evidence(
                session,
                second_evidence,
                fact_scope="candidate-2",
            )
            replacement_fact_ids = engine.fact_constraint_ids(
                session.reconstruct(),
                second_ids,
            )

            superseded = engine.supersede_replaced_facts(
                session,
                prior_fact_ids,
                replacement_fact_ids,
            )

            state = session.reconstruct()
            self.assertEqual(superseded, first_ids)
            self.assertEqual(state.constraints[first_ids[0]]["status"], "superseded")
            self.assertEqual(state.constraints[second_ids[0]]["status"], "active")

    def test_semantic_identifier_is_stable_and_evidence_is_merged(self) -> None:
        first = NormalizedConstraint(
            ConstraintDomain.PACKAGE,
            "Demo_Package",
            ConstraintPredicate.VERSION,
            ">=1",
            ConstraintRole.REQUIREMENT,
            ("evidence-2",),
            0.8,
        )
        second = NormalizedConstraint(
            ConstraintDomain.PACKAGE,
            "demo-package",
            ConstraintPredicate.VERSION,
            ">=1",
            ConstraintRole.REQUIREMENT,
            ("evidence-1",),
            1.0,
        )

        self.assertEqual(first.constraint_id, second.constraint_id)
        merged = first.with_evidence(second.evidence_ids, second.confidence)
        self.assertEqual(merged.subject, "demo-package")
        self.assertEqual(merged.evidence_ids, ("evidence-1", "evidence-2"))
        self.assertEqual(merged.confidence, 1.0)
        reordered = NormalizedConstraint(
            ConstraintDomain.RUNTIME,
            "python",
            ConstraintPredicate.VERSION,
            ">=3.8,<3.12",
            ConstraintRole.REQUIREMENT,
            ("evidence-3",),
        )
        canonical = NormalizedConstraint(
            ConstraintDomain.RUNTIME,
            "python",
            ConstraintPredicate.VERSION,
            "<3.12,>=3.8",
            ConstraintRole.REQUIREMENT,
            ("evidence-4",),
        )
        self.assertEqual(reordered.constraint_id, canonical.constraint_id)

    def test_case_sensitive_module_subjects_are_not_merged(self) -> None:
        upper = NormalizedConstraint(
            ConstraintDomain.MODULE,
            "DemoModule",
            ConstraintPredicate.PRESENT,
            True,
            ConstraintRole.REQUIREMENT,
            ("evidence-1",),
        )
        lower = NormalizedConstraint(
            ConstraintDomain.MODULE,
            "demomodule",
            ConstraintPredicate.PRESENT,
            True,
            ConstraintRole.REQUIREMENT,
            ("evidence-2",),
        )

        self.assertNotEqual(upper.constraint_id, lower.constraint_id)

    def test_compatible_runtime_evidence_becomes_satisfied_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(session, "runtime-requirement", ">=3.10,<3.13")
            self.evidence(
                session,
                "runtime-observation",
                {"name": "python", "version": "3.11.9"},
            )
            engine = ConstraintEngine()
            report = engine.propagate(session)
            event_count = len(session.store.read())

            self.assertTrue(report.satisfiable)
            self.assertEqual(set(report.statuses.values()), {"satisfied"})
            self.assertEqual(len(engine.propagate(session).statuses), 2)
            self.assertEqual(len(session.store.read()), event_count)

    def test_python_mismatch_output_produces_traced_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            evidence_id = self.evidence(
                session,
                "action-result",
                {
                    "exit_code": 1,
                    "deterministic_counterexample": True,
                    "stdout": "",
                    "stderr": (
                        "Package requires a different Python: 3.13.2 not in "
                        "'>=3.8,<3.12'"
                    ),
                },
            )
            report = ConstraintEngine().propagate(session)

            self.assertFalse(report.satisfiable)
            self.assertEqual(len(report.conflicts), 1)
            self.assertEqual(report.conflicts[0].evidence_ids, (evidence_id,))
            self.assertEqual(set(report.statuses.values()), {"violated"})

    def test_missing_executable_output_produces_capability_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(
                session,
                "action-result",
                {
                    "exit_code": 1,
                    "deterministic_counterexample": True,
                    "stdout": "",
                    "stderr": "Error: pg_config executable not found",
                },
            )
            report = ConstraintEngine().propagate(session)

            self.assertFalse(report.satisfiable)
            conflict = report.conflicts[0]
            self.assertEqual(conflict.domain, "capability")
            self.assertEqual(conflict.subject, "pg_config")

    def test_missing_module_output_produces_module_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(
                session,
                "action-result",
                {
                    "exit_code": 1,
                    "deterministic_counterexample": True,
                    "stdout": "",
                    "stderr": "ModuleNotFoundError: No module named 'demo_module'",
                },
            )
            report = ConstraintEngine().propagate(session)

            self.assertFalse(report.satisfiable)
            self.assertEqual(report.conflicts[0].domain, "module")
            self.assertEqual(report.conflicts[0].subject, "demo_module")

    def test_unverified_log_pattern_cannot_become_a_hard_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(
                session,
                "action-result",
                {
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "ModuleNotFoundError: No module named 'quoted_noise'",
                },
            )
            report = ConstraintEngine().propagate(session)

            self.assertTrue(report.satisfiable)
            self.assertEqual(len(report.provisional_constraints), 2)

    def test_package_version_requirement_is_an_exact_pin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(
                session,
                "package-requirement",
                {"name": "Demo_Package", "version": "1.2.3"},
            )
            ConstraintEngine().propagate(session)
            record = next(iter(session.reconstruct().constraints.values()))

            self.assertEqual(json.loads(record["expression"])["value"], "==1.2.3")

    def test_incompatible_exact_package_pins_are_rejected(self) -> None:
        requirements = tuple(
            NormalizedConstraint(
                ConstraintDomain.PACKAGE,
                "demo",
                ConstraintPredicate.VERSION,
                version,
                ConstraintRole.REQUIREMENT,
                (f"evidence-{index}",),
            )
            for index, version in enumerate(("==1.0", "==2.0"), start=1)
        )
        report = ConstraintEngine().solve(requirements)

        self.assertFalse(report.satisfiable)
        self.assertEqual(set(report.statuses.values()), {"violated"})

    def test_disjoint_version_ranges_are_rejected_without_exact_pins(self) -> None:
        requirements = tuple(
            NormalizedConstraint(
                ConstraintDomain.RUNTIME,
                "python",
                ConstraintPredicate.VERSION,
                specifier,
                ConstraintRole.REQUIREMENT,
                (f"evidence-{index}",),
            )
            for index, specifier in enumerate(("<3", ">=4"), start=1)
        )

        report = ConstraintEngine().solve(requirements)

        self.assertFalse(report.satisfiable)
        self.assertEqual(set(report.statuses.values()), {"violated"})

    def test_overlapping_open_version_ranges_remain_satisfiable(self) -> None:
        requirements = tuple(
            NormalizedConstraint(
                ConstraintDomain.RUNTIME,
                "python",
                ConstraintPredicate.VERSION,
                specifier,
                ConstraintRole.REQUIREMENT,
                (f"evidence-{index}",),
            )
            for index, specifier in enumerate((">3", "<4"), start=1)
        )

        self.assertTrue(ConstraintEngine().solve(requirements).satisfiable)

    def test_superseded_constraints_are_ignored_by_the_base_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(session, "runtime-requirement", "<3.12")
            self.evidence(
                session,
                "runtime-observation",
                {"name": "python", "version": "3.13"},
            )
            engine = ConstraintEngine()
            self.assertFalse(engine.propagate(session).satisfiable)
            state = session.reconstruct()
            fact_id = next(
                item.constraint_id
                for item in engine.typed_constraints(state)
                if item.role == ConstraintRole.FACT
            )
            record = state.constraints[fact_id]
            session.upsert_constraint(
                fact_id,
                str(record["kind"]),
                str(record["expression"]),
                "superseded",
                list(record["evidence_ids"]),
            )

            report = engine.solve_state(session.reconstruct())

            self.assertTrue(report.satisfiable)
            self.assertNotIn(fact_id, report.statuses)

    def test_low_confidence_fact_cannot_create_a_hard_rejection(self) -> None:
        requirement = NormalizedConstraint(
            ConstraintDomain.RUNTIME,
            "python",
            ConstraintPredicate.VERSION,
            "<3.12",
            ConstraintRole.REQUIREMENT,
            ("evidence-1",),
        )
        uncertain_fact = NormalizedConstraint(
            ConstraintDomain.RUNTIME,
            "python",
            ConstraintPredicate.VERSION,
            "3.13",
            ConstraintRole.FACT,
            ("evidence-2",),
            0.5,
        )
        report = ConstraintEngine().solve((requirement, uncertain_fact))

        self.assertTrue(report.satisfiable)
        self.assertEqual(
            report.provisional_constraints,
            (uncertain_fact.constraint_id,),
        )
        self.assertEqual(report.statuses[requirement.constraint_id], "active")

    def test_confidence_is_persisted_inside_canonical_expression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(
                session,
                "module-observation",
                {"name": "demo", "present": False},
                confidence=0.4,
            )
            engine = ConstraintEngine()
            report = engine.propagate(session)
            record = next(iter(session.reconstruct().constraints.values()))

            self.assertEqual(json.loads(record["expression"])["confidence"], 0.4)
            self.assertEqual(len(report.provisional_constraints), 1)


class PreflightTest(ConstraintTestCase):
    def _runtime_requirement(self, session: SolverStateSession) -> str:
        self.evidence(session, "runtime-requirement", ">=3.10,<3.13")
        engine = ConstraintEngine()
        engine.propagate(session)
        return next(iter(session.reconstruct().constraints))

    def test_compatible_declared_effect_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self._runtime_requirement(session)
            action = ActionSpec(
                "runtime-select",
                "select-python 3.11",
                "Select a compatible runtime",
                metadata={
                    "proposed_facts": [
                        {
                            "domain": "runtime",
                            "subject": "python",
                            "predicate": "version",
                            "value": "3.11",
                        }
                    ]
                },
            )

            result = preflight_action(
                session.reconstruct(),
                action,
                ConstraintEngine(),
            )
            self.assertEqual(result.disposition, PreflightDisposition.ALLOW)

    def test_incompatible_declared_effect_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self._runtime_requirement(session)
            action = ActionSpec(
                "runtime-select",
                "select-python 3.13",
                "Select a runtime",
                metadata={
                    "proposed_facts": [
                        {
                            "domain": "runtime",
                            "subject": "python",
                            "predicate": "version",
                            "value": "3.13",
                        }
                    ]
                },
            )

            result = preflight_action(
                session.reconstruct(),
                action,
                ConstraintEngine(),
            )
            self.assertEqual(result.disposition, PreflightDisposition.REJECT)
            self.assertEqual(len(result.conflicts), 1)

    def test_unresolved_precondition_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            constraint_id = self._runtime_requirement(session)
            action = ActionSpec(
                "verification",
                "python --version",
                "Observe runtime",
                preconditions=(constraint_id,),
            )

            result = preflight_action(
                session.reconstruct(),
                action,
                ConstraintEngine(),
            )
            self.assertEqual(
                result.disposition,
                PreflightDisposition.REQUIRE_EVIDENCE,
            )

    def test_mutation_without_declared_effect_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            result = preflight_action(
                session.reconstruct(),
                ActionSpec("install", "pip install demo", "Install a package"),
                ConstraintEngine(),
            )

            self.assertEqual(
                result.disposition,
                PreflightDisposition.REQUIRE_EVIDENCE,
            )

    def test_low_confidence_declared_effect_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            action = ActionSpec(
                "install",
                "pip install demo",
                "Install a package",
                metadata={
                    "proposed_facts": [
                        {
                            "domain": "package",
                            "subject": "demo",
                            "predicate": "present",
                            "value": True,
                            "confidence": 0.5,
                        }
                    ]
                },
            )
            result = preflight_action(
                session.reconstruct(),
                action,
                ConstraintEngine(),
            )

            self.assertEqual(
                result.disposition,
                PreflightDisposition.REQUIRE_EVIDENCE,
            )

    def test_malformed_declared_effect_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            action = ActionSpec(
                "install",
                "pip install demo",
                "Install a package",
                metadata={"proposed_facts": "package demo is present"},
            )
            result = preflight_action(
                session.reconstruct(),
                action,
                ConstraintEngine(),
            )

            self.assertEqual(result.disposition, PreflightDisposition.REJECT)

    def test_read_only_probe_is_allowed_during_existing_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(session, "runtime-requirement", "<3.12")
            self.evidence(
                session,
                "runtime-observation",
                {"version": "3.13"},
            )
            engine = ConstraintEngine()
            engine.propagate(session)

            result = preflight_action(
                session.reconstruct(),
                ActionSpec("probe", "python --version", "Collect new evidence"),
                engine,
            )
            self.assertEqual(result.disposition, PreflightDisposition.ALLOW)


class ConstraintCheckedPolicyTest(ConstraintTestCase):
    def test_read_only_evidence_probe_is_not_blocked_by_active_precondition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(session, "runtime-requirement", ">=3.10")
            engine = ConstraintEngine()
            engine.propagate(session)
            constraint_id = next(iter(session.reconstruct().constraints))
            probe = ActionSpec(
                "probe",
                "python --version",
                "Observe the active runtime requirement",
                preconditions=(constraint_id,),
            )
            executor = QueueExecutor([CommandResult(0, stdout="Python 3.11.9")])

            result = StatefulSolverLoop(session, executor, max_actions=1).run(
                ConstraintCheckedPolicy(ScriptedPolicy([probe]), session, engine)
            )

            self.assertEqual(result.actions_executed, 1)
            self.assertEqual(executor.commands, ["python --version"])
            self.assertIn(
                "constraint-preflight",
                {item["kind"] for item in session.reconstruct().evidence.values()},
            )

    def test_conflicting_action_is_blocked_before_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(session, "runtime-requirement", "<3.12")
            action = ActionSpec(
                "runtime-select",
                "select-python 3.13",
                "Select runtime",
                metadata={
                    "proposed_facts": [
                        {
                            "domain": "runtime",
                            "subject": "python",
                            "predicate": "version",
                            "value": "3.13",
                        }
                    ]
                },
            )
            executor = QueueExecutor([CommandResult(0)])
            policy = ConstraintCheckedPolicy(
                ScriptedPolicy([action]),
                session,
            )

            result = StatefulSolverLoop(session, executor, max_actions=1).run(policy)
            state = session.reconstruct()

            self.assertEqual(result.goal_status, "blocked")
            self.assertEqual(result.actions_executed, 0)
            self.assertEqual(executor.commands, [])
            self.assertEqual(state.actions, {})
            self.assertIn(
                "constraint-preflight-reject",
                {failure["category"] for failure in state.failures.values()},
            )
            self.assertIn(
                "constraint-preflight",
                {evidence["kind"] for evidence in state.evidence.values()},
            )


if __name__ == "__main__":
    unittest.main()
