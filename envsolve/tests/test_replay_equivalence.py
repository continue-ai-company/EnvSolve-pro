from __future__ import annotations

import unittest

from envsolve.verification.replay_equivalence import (
    ReplayIdentity,
    ReplayObservation,
    build_snapshot,
    compare_replays,
    snapshot_from_artifact,
)


HASH = "a" * 64


def identity(**changes: str) -> ReplayIdentity:
    values = {
        "image_id": "image",
        "repository_digest": "digest",
        "platform": "linux/arm64",
        "repository": "org/repo",
        "revision": "revision",
        "git_tree": "tree",
        "bootstrap_sha256": HASH,
        "preregistration_sha256": "b" * 64,
    }
    values.update(changes)
    return ReplayIdentity(**values)


def snapshot(
    installed=(('dep', '1.0'),),
    metadata_sha256=HASH,
):
    return build_snapshot(
        {"implementation": "CPython", "version": "3.13.1"},
        {"sys_platform": "linux", "python_version": "3.13"},
        installed,
        (("sample", "1.0", metadata_sha256, "pep610-direct-url", HASH),),
    )


class ReplayEquivalenceTests(unittest.TestCase):
    def test_identical_normalized_snapshots_pass(self) -> None:
        first = snapshot(installed=(("Other_Name", "2"), ("dep", "1.0")))
        second = snapshot(installed=(("DEP", "1.0"), ("other-name", "2")))

        decision = compare_replays(
            ReplayObservation(identity(), first),
            ReplayObservation(identity(), second),
        )

        self.assertTrue(decision.passed)
        self.assertEqual(decision.first_snapshot_sha256, decision.second_snapshot_sha256)
        self.assertEqual(decision.differences, ())

    def test_installed_version_drift_fails_with_structured_delta(self) -> None:
        decision = compare_replays(
            ReplayObservation(identity(), snapshot(installed=(("dep", "1.0"),))),
            ReplayObservation(identity(), snapshot(installed=(("dep", "2.0"),))),
        )

        self.assertFalse(decision.passed)
        self.assertEqual(decision.differences[0].component, "installed_distributions")
        self.assertIn("dep==1.0", decision.differences[0].first_only[0])
        self.assertIn("dep==2.0", decision.differences[0].second_only[0])

    def test_project_metadata_drift_fails(self) -> None:
        decision = compare_replays(
            ReplayObservation(identity(), snapshot()),
            ReplayObservation(identity(), snapshot(metadata_sha256="c" * 64)),
        )

        self.assertFalse(decision.passed)
        self.assertEqual(decision.differences[0].component, "project_distributions")

    def test_missing_snapshot_is_unknown(self) -> None:
        decision = compare_replays(
            ReplayObservation(identity(), snapshot()),
            ReplayObservation(identity(), None),
        )

        self.assertIsNone(decision.passed)

    def test_identity_mismatch_is_unknown_not_state_failure(self) -> None:
        decision = compare_replays(
            ReplayObservation(identity(), snapshot()),
            ReplayObservation(identity(revision="other"), snapshot()),
        )

        self.assertIsNone(decision.passed)
        self.assertEqual(decision.differences[0].component, "identity")

    def test_snapshot_artifact_hash_is_recomputed(self) -> None:
        value = snapshot()
        artifact = {
            "sha256": value.sha256,
            "python_runtime": dict(value.python_runtime),
            "marker_environment": dict(value.marker_environment),
            "installed_distributions": [item.__dict__ for item in value.installed_distributions],
            "project_distributions": [item.__dict__ for item in value.project_distributions],
        }

        self.assertEqual(snapshot_from_artifact(artifact), value)
        artifact["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            snapshot_from_artifact(artifact)


if __name__ == "__main__":
    unittest.main()
