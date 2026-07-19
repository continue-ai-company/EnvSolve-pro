from pathlib import Path
import tempfile
import unittest

from envsolve.constraints import ConstraintEngine
from envsolve.operations import OperationKind
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


if __name__ == "__main__":
    unittest.main()
