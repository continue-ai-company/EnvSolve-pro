from pathlib import Path
import tempfile
import unittest

from envsolve.constraints import ConstraintEngine
from envsolve.operations import OperationKind, OperationTrigger
from envsolve.operations.planner import ConstraintOperationPlanner
from envsolve.solver import SolverStateSession


class ConstraintOperationPlannerTest(unittest.TestCase):
    def test_module_conflict_becomes_provenance_bearing_operation_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "events.jsonl",
                root / "snapshot.json",
                {
                    "case_id": "operation-plan",
                    "repository": "example/project",
                    "revision": "a" * 40,
                },
            )
            requirement = session.record_evidence(
                "module-requirement",
                "synthetic-verifier",
                {"name": "demo_module", "present": True},
            )
            observation = session.record_evidence(
                "module-observation",
                "synthetic-verifier",
                {"name": "demo_module", "present": False},
            )
            engine = ConstraintEngine()
            engine.ingest_evidence(session, requirement)
            engine.ingest_evidence(session, observation, fact_scope="candidate-1")
            report = engine.propagate_constraints(session)

            plan = ConstraintOperationPlanner(engine).plan(session.reconstruct())

            self.assertEqual(len(report.conflicts), 1)
            self.assertEqual(len(plan.requirements), 1)
            operation = plan.requirements[0]
            self.assertEqual(operation.trigger, OperationTrigger.CONFLICT)
            self.assertEqual(operation.domain, "module")
            self.assertEqual(operation.subject, "demo_module")
            self.assertEqual(
                set(operation.allowed_operation_kinds),
                {
                    OperationKind.PYTHON_PACKAGE_INSTALL,
                    OperationKind.SYSTEM_PACKAGE_INSTALL,
                },
            )
            self.assertEqual(
                set(operation.source_constraint_ids),
                set(report.conflicts[0].constraint_ids),
            )
            self.assertEqual(plan.to_dict()["plan_id"], plan.plan_id)

    def test_unresolved_requirement_becomes_pre_action_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "events.jsonl",
                root / "snapshot.json",
                {
                    "case_id": "pre-action-plan",
                    "repository": "example/project",
                    "revision": "a" * 40,
                },
            )
            evidence_id = session.record_evidence(
                "package-requirement",
                "repository-metadata",
                {"name": "demo-project", "present": True},
            )
            engine = ConstraintEngine()
            engine.ingest_evidence(session, evidence_id)
            report = engine.propagate_constraints(session)

            plan = ConstraintOperationPlanner(engine).plan(session.reconstruct())

            self.assertFalse(report.conflicts)
            self.assertEqual(len(plan.requirements), 1)
            operation = plan.requirements[0]
            self.assertEqual(
                operation.trigger,
                OperationTrigger.UNRESOLVED_REQUIREMENT,
            )
            self.assertEqual(operation.domain, "package")
            self.assertEqual(operation.subject, "demo-project")
            self.assertEqual(
                operation.allowed_operation_kinds,
                (OperationKind.PYTHON_PACKAGE_INSTALL,),
            )
            self.assertFalse(operation.source_conflict_ids)
            self.assertEqual(
                operation.source_constraint_ids,
                (next(iter(report.statuses)),),
            )


if __name__ == "__main__":
    unittest.main()
