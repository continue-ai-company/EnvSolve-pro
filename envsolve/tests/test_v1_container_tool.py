from __future__ import annotations

from dataclasses import dataclass
import unittest

from envsolve.tools.run_p5_v1_in_container import (
    aggregate_decisions,
    collect_installed_observations,
    collect_project_evidence,
)
from envsolve.verification.metadata_consistency import (
    ConsistencyIssue,
    MetadataConsistencyDecision,
)
from envsolve.verification.project_provenance import ProjectDistributionMatch


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    value: str
    group: str


class FakeDistribution:
    entry_points = ()

    def __init__(
        self,
        name: str = "sample",
        version: str = "1.2",
        metadata_text: str | None = None,
    ) -> None:
        self.metadata = {"Name": name}
        self.version = version
        self.files = {
            "METADATA": metadata_text
            or f"Name: {name}\nVersion: {version}\nRequires-Dist: dep>=2\n",
            "top_level.txt": "sample\n",
            "entry_points.txt": "",
        }

    def read_text(self, filename: str) -> str | None:
        return self.files.get(filename)


class V1ContainerToolTests(unittest.TestCase):
    def test_project_evidence_uses_content_addressed_installed_metadata(self) -> None:
        match = ProjectDistributionMatch(
            FakeDistribution(), "pep610-direct-url", "a" * 64
        )

        evidence, source = collect_project_evidence(match)

        self.assertEqual(source, "METADATA")
        self.assertEqual(evidence.name, "sample")
        self.assertEqual(evidence.version, "1.2")
        self.assertEqual(evidence.requires_dist, ("dep>=2",))
        self.assertEqual(len(evidence.metadata_sha256), 64)
        self.assertEqual(evidence.provenance_kind, "pep610-direct-url")

    def test_project_evidence_rejects_internal_name_or_version_mismatch(self) -> None:
        name_mismatch = FakeDistribution(
            name="other", metadata_text="Name: sample\nVersion: 1.2\n"
        )
        version_mismatch = FakeDistribution(
            version="2.0", metadata_text="Name: sample\nVersion: 1.2\n"
        )

        for distribution in (name_mismatch, version_mismatch):
            with self.subTest(distribution=distribution), self.assertRaises(ValueError):
                collect_project_evidence(
                    ProjectDistributionMatch(distribution, "pep610-direct-url", "a" * 64)
                )

    def test_installed_observations_preserve_invalid_versions_for_v1_policy(self) -> None:
        invalid = FakeDistribution("ambient", "not a version")
        missing_name = FakeDistribution()
        missing_name.metadata = {}

        observations, errors = collect_installed_observations(
            (FakeDistribution(), invalid, missing_name)
        )

        self.assertEqual(
            [(item.name, item.version) for item in observations],
            [("ambient", "not a version"), ("sample", "1.2")],
        )
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["kind"], "installed-distribution-unreadable")

    def test_aggregate_is_fail_closed_and_failure_dominates_collection_error(self) -> None:
        passed = MetadataConsistencyDecision(True, "ok", ("dep>=2",), ())
        failed = MetadataConsistencyDecision(
            False,
            "bad",
            ("missing",),
            (ConsistencyIssue("missing-distribution", "missing", "missing"),),
        )
        unknown = MetadataConsistencyDecision(None, "unknown", (), ())

        self.assertTrue(aggregate_decisions((passed,)).passed)
        self.assertFalse(aggregate_decisions((passed, failed), 1).passed)
        self.assertIsNone(aggregate_decisions((passed,), 1).passed)
        self.assertIsNone(aggregate_decisions((passed, unknown)).passed)
        self.assertIsNone(aggregate_decisions(()).passed)


if __name__ == "__main__":
    unittest.main()
