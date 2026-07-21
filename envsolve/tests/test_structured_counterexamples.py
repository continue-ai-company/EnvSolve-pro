from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.constraints import ConstraintDomain, ConstraintPredicate
from envsolve.solver import (
    CandidateAssessment,
    CandidateValidation,
    CommandResult,
    CounterexampleGuidedDeploymentLoop,
    DeploymentCandidate,
    EnvironmentReceipt,
    FeedbackChannel,
    ProvisionedEnvironment,
    SolverStateSession,
)
from envsolve.verification import (
    FindingDisposition,
    StructuredFindingAdapter,
    StructuredVerifierFinding,
    StructuredVerifierReport,
)


def finding(
    disposition: FindingDisposition,
    *,
    identifier: str = "finding-1",
    observed: bool = False,
) -> StructuredVerifierFinding:
    return StructuredVerifierFinding(
        finding_id=identifier,
        domain=ConstraintDomain.MODULE,
        subject="example_dependency",
        predicate=ConstraintPredicate.PRESENT,
        required=True,
        observed=observed,
        disposition=disposition,
        provenance={"collector": "synthetic"},
    )


def report(
    *findings: StructuredVerifierFinding,
    completed: bool = True,
    exit_code: int = 0,
    infrastructure_error: str | None = None,
    environment_id: str = "fresh-environment-1",
    goal_passed: bool | None = False,
) -> StructuredVerifierReport:
    return StructuredVerifierReport(
        verifier="synthetic-structured-verifier",
        check_profile="synthetic-structured-checks",
        channel=FeedbackChannel.INTERNAL_EXECUTION,
        environment_id=environment_id,
        environment_fresh=True,
        bootstrap=CommandResult(exit_code),
        completed=completed,
        goal_passed=goal_passed,
        findings=tuple(findings),
        infrastructure_error=infrastructure_error,
    )


class StructuredFindingAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = StructuredFindingAdapter()

    def test_active_module_finding_becomes_requirement_and_observation(self) -> None:
        outcome = self.adapter.adapt(report(finding(FindingDisposition.ACTIVE)))

        self.assertFalse(outcome.passed)
        self.assertEqual(
            [item.kind for item in outcome.counterexamples],
            ["module-requirement", "module-observation"],
        )
        self.assertEqual(outcome.counterexamples[0].value["name"], "example_dependency")
        self.assertTrue(outcome.counterexamples[0].value["present"])
        self.assertFalse(outcome.counterexamples[1].value["present"])
        self.assertEqual(outcome.counterexamples[0].value["finding_id"], "finding-1")
        self.assertEqual(
            outcome.counterexamples[0].value["finding_provenance"],
            {"collector": "synthetic"},
        )
        self.assertTrue(outcome.candidate_assessment.admissible)
        self.assertEqual(outcome.candidate_assessment.unresolved_constraints, 1)

    def test_admissible_assessment_requires_residual_constraints(self) -> None:
        with self.assertRaisesRegex(ValueError, "residual constraint"):
            CandidateAssessment(True, 0, 3, 0, "invalid admissible candidate")

    def test_inactive_findings_do_not_block_a_completed_bootstrap(self) -> None:
        outcome = self.adapter.adapt(
            report(finding(FindingDisposition.INACTIVE), goal_passed=True)
        )

        self.assertTrue(outcome.passed)
        self.assertFalse(outcome.counterexamples)

    def test_satisfied_finding_becomes_positive_observation_only(self) -> None:
        outcome = self.adapter.adapt(
            report(
                finding(FindingDisposition.SATISFIED, observed=True),
                goal_passed=True,
            )
        )

        self.assertTrue(outcome.passed)
        self.assertFalse(outcome.counterexamples)
        self.assertEqual(len(outcome.observations), 1)
        self.assertEqual(outcome.observations[0].kind, "module-observation")
        self.assertTrue(outcome.observations[0].value["present"])

    def test_unknown_report_does_not_admit_partial_positive_observations(self) -> None:
        outcome = self.adapter.adapt(
            report(
                finding(FindingDisposition.SATISFIED, observed=True),
                finding(FindingDisposition.UNKNOWN, identifier="finding-2"),
                goal_passed=True,
            )
        )

        self.assertIsNone(outcome.passed)
        self.assertFalse(outcome.observations)
        self.assertFalse(outcome.candidate_assessment.admissible)
        self.assertEqual(outcome.candidate_assessment.unknown_constraints, 1)

    def test_inactive_findings_do_not_override_a_goal_failure(self) -> None:
        outcome = self.adapter.adapt(
            report(finding(FindingDisposition.INACTIVE), goal_passed=False)
        )

        self.assertFalse(outcome.passed)
        self.assertFalse(outcome.counterexamples)
        self.assertFalse(outcome.candidate_assessment.admissible)

    def test_unknown_finding_becomes_hypothesis_without_hiding_active_failure(self) -> None:
        outcome = self.adapter.adapt(
            report(
                finding(FindingDisposition.ACTIVE),
                finding(FindingDisposition.UNKNOWN, identifier="finding-2"),
            )
        )

        self.assertFalse(outcome.passed)
        self.assertEqual(len(outcome.counterexamples), 2)
        self.assertEqual(len(outcome.hypotheses), 1)

    def test_active_finding_does_not_silently_override_reported_pass(self) -> None:
        outcome = self.adapter.adapt(
            report(finding(FindingDisposition.ACTIVE), goal_passed=True)
        )

        self.assertTrue(outcome.passed)
        self.assertEqual(len(outcome.counterexamples), 2)

    def test_infrastructure_and_incomplete_reports_are_unknown(self) -> None:
        infrastructure = self.adapter.adapt(
            report(infrastructure_error="package download timeout")
        )
        incomplete = self.adapter.adapt(report(completed=False))

        self.assertIsNone(infrastructure.passed)
        self.assertIsNone(incomplete.passed)

    def test_unexplained_bootstrap_failure_remains_unnormalized(self) -> None:
        outcome = self.adapter.adapt(report(exit_code=2, goal_passed=False))

        self.assertFalse(outcome.passed)
        self.assertFalse(outcome.counterexamples)

    def test_package_version_finding_uses_existing_evidence_schema(self) -> None:
        item = StructuredVerifierFinding(
            finding_id="package-version",
            domain=ConstraintDomain.PACKAGE,
            subject="Demo_Package",
            predicate=ConstraintPredicate.VERSION,
            required=">=2",
            observed="1.5",
            disposition=FindingDisposition.ACTIVE,
        )

        outcome = self.adapter.adapt(report(item))

        self.assertEqual(outcome.counterexamples[0].kind, "package-requirement")
        self.assertEqual(outcome.counterexamples[0].value["name"], "Demo_Package")
        self.assertEqual(outcome.counterexamples[0].value["specifier"], ">=2")
        self.assertEqual(outcome.counterexamples[1].kind, "package-observation")

    def test_unsupported_domain_predicate_pair_fails_closed(self) -> None:
        item = StructuredVerifierFinding(
            finding_id="bad-combination",
            domain=ConstraintDomain.CAPABILITY,
            subject="compiler",
            predicate=ConstraintPredicate.VERSION,
            required=">=1",
            observed="0",
            disposition=FindingDisposition.ACTIVE,
        )

        with self.assertRaisesRegex(ValueError, "Version findings support"):
            self.adapter.adapt(report(item))

    def test_adapter_and_loop_form_an_end_to_end_feedback_cycle(self) -> None:
        class Validator:
            def validate(self, candidate):
                return CandidateValidation(True, "synthetic-validator", candidate.script)

        class Budget:
            def reserve_candidate(self, candidate_id):
                pass

            def reserve_environment(self, candidate_id):
                pass

            def reserve_command(self, candidate_id):
                pass

        class Provider:
            def __init__(self):
                self.round = 0

            def provision(self, candidate):
                self.round += 1
                return ProvisionedEnvironment(
                    EnvironmentReceipt(
                        f"fresh-environment-{self.round}",
                        "synthetic-provider",
                        "sha256:synthetic",
                        "example/project",
                        "b" * 40,
                        f"2026-01-01T00:00:0{self.round}+00:00",
                    )
                )

            def release(self, environment):
                pass

        class Policy:
            def __init__(self) -> None:
                self.round = 0
                self.constraint_counts: list[int] = []

            def propose(self, state):
                self.round += 1
                self.constraint_counts.append(len(state.constraints))
                return DeploymentCandidate(
                    f"candidate-{self.round}",
                    f"install candidate-{self.round}",
                    "Synthetic candidate",
                )

        class Verifier:
            def __init__(self, adapter: StructuredFindingAdapter) -> None:
                self.adapter = adapter
                self.round = 0

            def verify(self, candidate, environment):
                self.round += 1
                findings = (
                    (finding(FindingDisposition.ACTIVE),)
                    if self.round == 1
                    else ()
                )
                return self.adapter.adapt(
                    report(
                        *findings,
                        environment_id=f"fresh-environment-{self.round}",
                        goal_passed=self.round == 2,
                    )
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(
                root / "state.jsonl",
                root / "snapshot.json",
                {
                    "case_id": "structured-adapter-integration",
                    "repository": "example/project",
                    "revision": "b" * 40,
                },
            )
            policy = Policy()

            result = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=2,
                candidate_validator=Validator(),
                budget=Budget(),
            ).run(policy, Provider(), Verifier(self.adapter))

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(policy.constraint_counts, [0, 2])
            final_state = session.reconstruct()
            self.assertNotIn(
                "violated",
                {item["status"] for item in final_state.constraints.values()},
            )
            self.assertEqual(result.accepted_candidate.candidate_id, "candidate-2")


if __name__ == "__main__":
    unittest.main()
