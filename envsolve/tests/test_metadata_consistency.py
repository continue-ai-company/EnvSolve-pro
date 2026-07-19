from __future__ import annotations

import unittest

from envsolve.verification.metadata_consistency import (
    InstalledDistributionObservation,
    ProjectMetadataEvidence,
    ResolverCheck,
    evaluate_metadata_consistency,
)


HASH = "a" * 64
ENVIRONMENT = {
    "implementation_name": "cpython",
    "implementation_version": "3.13.1",
    "os_name": "posix",
    "platform_machine": "aarch64",
    "platform_release": "test",
    "platform_system": "Linux",
    "platform_version": "test",
    "python_full_version": "3.13.1",
    "platform_python_implementation": "CPython",
    "python_version": "3.13",
    "sys_platform": "linux",
}


def project(*requirements: str) -> ProjectMetadataEvidence:
    return ProjectMetadataEvidence(
        "sample",
        "1.0",
        HASH,
        "pep610-direct-url",
        HASH,
        tuple(requirements),
    )


def resolver(exit_code: int = 0) -> ResolverCheck:
    return ResolverCheck(("python", "-m", "pip", "check"), exit_code, HASH, HASH, True)


class MetadataConsistencyTests(unittest.TestCase):
    def evaluate(
        self,
        metadata: ProjectMetadataEvidence | None = None,
        installed: tuple[InstalledDistributionObservation, ...] | None = None,
        environment: dict[str, str] | None = None,
        extras: tuple[str, ...] | None = (),
        check: ResolverCheck | None = None,
    ):
        return evaluate_metadata_consistency(
            metadata if metadata is not None else project("dep>=2"),
            installed if installed is not None else (InstalledDistributionObservation("dep", "2.1"),),
            environment if environment is not None else ENVIRONMENT,
            extras,
            check if check is not None else resolver(),
        )

    def test_consistent_metadata_and_resolver_pass(self) -> None:
        decision = self.evaluate()

        self.assertTrue(decision.passed)
        self.assertEqual(decision.active_requirements, ("dep>=2",))

    def test_missing_required_evidence_is_unknown(self) -> None:
        decision = evaluate_metadata_consistency(project(), (), ENVIRONMENT, (), None)

        self.assertIsNone(decision.passed)

    def test_inactive_platform_marker_creates_no_obligation(self) -> None:
        decision = self.evaluate(metadata=project('darwin-only; sys_platform == "darwin"'), installed=())

        self.assertTrue(decision.passed)
        self.assertEqual(decision.active_requirements, ())

    def test_extra_requirement_requires_explicit_selection(self) -> None:
        metadata = project('pytest; extra == "test"')

        without = self.evaluate(metadata=metadata, installed=())
        with_extra = self.evaluate(metadata=metadata, installed=(), extras=("test",))

        self.assertTrue(without.passed)
        self.assertFalse(with_extra.passed)
        self.assertEqual(with_extra.issues[0].kind, "missing-distribution")

    def test_missing_incompatible_and_duplicate_distributions_fail(self) -> None:
        missing = self.evaluate(installed=())
        incompatible = self.evaluate(installed=(InstalledDistributionObservation("dep", "1.0"),))
        duplicate = self.evaluate(
            installed=(
                InstalledDistributionObservation("dep", "2.0"),
                InstalledDistributionObservation("DEP", "2.1"),
            )
        )

        self.assertEqual(missing.issues[0].kind, "missing-distribution")
        self.assertEqual(incompatible.issues[0].kind, "incompatible-version")
        self.assertEqual(duplicate.issues[0].kind, "ambiguous-distribution")

    def test_invalid_installed_version_and_requirement_fail(self) -> None:
        invalid_version = self.evaluate(
            installed=(InstalledDistributionObservation("dep", "not a version"),)
        )
        invalid_requirement = self.evaluate(metadata=project("dep=>2"), installed=())

        self.assertFalse(invalid_version.passed)
        self.assertEqual(invalid_version.issues[0].kind, "invalid-installed-version")
        self.assertFalse(invalid_requirement.passed)
        self.assertEqual(invalid_requirement.issues[0].kind, "invalid-requirement")

    def test_unrelated_invalid_installed_version_does_not_fail_project(self) -> None:
        decision = self.evaluate(
            installed=(
                InstalledDistributionObservation("dep", "2.1"),
                InstalledDistributionObservation("ambient-helper", "not a version"),
            )
        )

        self.assertTrue(decision.passed)

    def test_nonzero_environment_wide_resolver_is_unknown_without_attribution(self) -> None:
        decision = evaluate_metadata_consistency(None, None, None, None, resolver(1))

        self.assertIsNone(decision.passed)

        attributed = self.evaluate(check=resolver(1))
        self.assertIsNone(attributed.passed)
        self.assertEqual(attributed.issues[0].kind, "resolver-conflict")

    def test_project_scoped_conflict_is_not_hidden_by_ambient_resolver_failure(self) -> None:
        decision = self.evaluate(installed=(), check=resolver(1))

        self.assertFalse(decision.passed)
        self.assertEqual(decision.issues[0].kind, "missing-distribution")

    def test_invalid_resolver_or_incomplete_marker_evidence_is_unknown(self) -> None:
        invalid_resolver = ResolverCheck(("pip", "check"), 0, HASH, HASH, True)
        resolver_decision = self.evaluate(check=invalid_resolver)
        environment_decision = self.evaluate(environment={"python_version": "3.13"})

        self.assertIsNone(resolver_decision.passed)
        self.assertIsNone(environment_decision.passed)

    def test_invalid_project_provenance_fails(self) -> None:
        metadata = ProjectMetadataEvidence("sample", "1.0", HASH, "guessed", HASH, ())

        decision = self.evaluate(metadata=metadata, installed=())

        self.assertFalse(decision.passed)
        self.assertEqual(decision.issues[0].kind, "invalid-project-metadata")


if __name__ == "__main__":
    unittest.main()
