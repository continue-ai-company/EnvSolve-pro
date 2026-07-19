from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve.workspace.artifacts import ArtifactOwnership, WorkspaceArtifactPolicy


DIAGNOSTIC = (
    "error: Multiple top-level packages discovered in a flat-layout: "
    "['inflect', 'build_output']."
)
HASH = "a" * 64


class WorkspaceArtifactPolicyTests(unittest.TestCase):
    def test_normalizes_only_proven_verifier_owned_path(self) -> None:
        conflict = WorkspaceArtifactPolicy().normalize(
            DIAGNOSTIC,
            [
                ArtifactOwnership(
                    path="build_output",
                    producer="external-verifier",
                    producer_sha256=HASH,
                    content_sha256="b" * 64,
                    created_before_bootstrap=True,
                    repository_tracked=False,
                ),
                ArtifactOwnership(
                    path="inflect",
                    producer="repository",
                    producer_sha256=HASH,
                    content_sha256="c" * 64,
                    created_before_bootstrap=False,
                    repository_tracked=True,
                ),
            ],
        )

        self.assertIsNotNone(conflict)
        assert conflict is not None
        self.assertEqual(conflict.discovered_paths, ("build_output", "inflect"))
        self.assertEqual(tuple(item.path for item in conflict.owned_paths), ("build_output",))

    def test_rejects_missing_or_unsafe_ownership(self) -> None:
        unsafe = ArtifactOwnership(
            path="../build_output",
            producer="external-verifier",
            producer_sha256=HASH,
            content_sha256="b" * 64,
            created_before_bootstrap=True,
            repository_tracked=False,
        )
        self.assertIsNone(WorkspaceArtifactPolicy().normalize(DIAGNOSTIC, [unsafe]))

    def test_repair_relocates_and_restores_without_deleting(self) -> None:
        ownership = ArtifactOwnership(
            path="build_output",
            producer="external-verifier",
            producer_sha256=HASH,
            content_sha256="b" * 64,
            created_before_bootstrap=True,
            repository_tracked=False,
        )
        policy = WorkspaceArtifactPolicy()
        conflict = policy.normalize(DIAGNOSTIC, [ownership])
        assert conflict is not None

        script = policy.plan(conflict).render_shell("python -m pip install -e .")

        self.assertIn("mktemp -d", script)
        self.assertEqual(script.count('mv --'), 2)
        self.assertIn("trap envsolve_restore_artifacts EXIT", script)
        self.assertNotIn("rm -rf", script)
        self.assertIn("python -m pip install -e .", script)

    def test_repair_supports_multiple_owned_artifacts(self) -> None:
        diagnostic = (
            "Multiple top-level packages discovered in a flat-layout: "
            "['pkg', 'build_output', 'coverage_output']"
        )
        ownership = [
            ArtifactOwnership(
                path=path,
                producer="external-verifier",
                producer_sha256=HASH,
                content_sha256=character * 64,
                created_before_bootstrap=True,
                repository_tracked=False,
            )
            for path, character in (("build_output", "b"), ("coverage_output", "c"))
        ]
        conflict = WorkspaceArtifactPolicy().normalize(diagnostic, ownership)
        assert conflict is not None

        script = WorkspaceArtifactPolicy().plan(conflict).render_shell("pip install -e .")

        self.assertEqual(script.count("mv --"), 4)
        self.assertIn("build_output", script)
        self.assertIn("coverage_output", script)

    def test_rejects_multiline_install_command(self) -> None:
        ownership = ArtifactOwnership(
            path="build_output",
            producer="external-verifier",
            producer_sha256=HASH,
            content_sha256="b" * 64,
            created_before_bootstrap=True,
            repository_tracked=False,
        )
        policy = WorkspaceArtifactPolicy()
        conflict = policy.normalize(DIAGNOSTIC, [ownership])
        assert conflict is not None
        with self.assertRaises(ValueError):
            policy.plan(conflict).render_shell("pip install -e .\necho unsafe")

    def test_failed_install_restores_artifact_via_exit_trap(self) -> None:
        ownership = ArtifactOwnership(
            path="build_output",
            producer="external-verifier",
            producer_sha256=HASH,
            content_sha256="b" * 64,
            created_before_bootstrap=True,
            repository_tracked=False,
        )
        conflict = WorkspaceArtifactPolicy().normalize(DIAGNOSTIC, [ownership])
        assert conflict is not None
        script = WorkspaceArtifactPolicy().plan(conflict).render_shell("false")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "build_output"
            artifact.mkdir()
            (artifact / "marker").write_text("retained\n", encoding="utf-8")

            result = subprocess.run(
                ["bash", "-c", "set -e\n" + script],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((artifact / "marker").read_text(), "retained\n")
