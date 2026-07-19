from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.context import build_repair_context
from envsolve.provenance import (
    ContextTransferLineage,
    ImageIdentity,
    transfer_context_evidence,
)
from envsolve.solver import SolverStateSession


SOURCE_CASE = {
    "case_id": "case-free-context:sha256:" + "1" * 64,
    "repository": "none",
    "revision": "sha256:" + "1" * 64,
    "language": "infrastructure",
    "split": "case-free",
    "tags": [],
}
TARGET_CASE = {
    "case_id": "recorded-result:owner/repo@abc",
    "repository": "owner/repo",
    "revision": "abc",
    "language": "python",
    "split": "development-consumed",
    "tags": [],
}


class ContextTransferTest(unittest.TestCase):
    @staticmethod
    def session(root: Path, name: str, case: dict) -> SolverStateSession:
        return SolverStateSession(
            root / f"{name}.jsonl",
            root / f"{name}.snapshot.json",
            case,
        )

    def source(self, root: Path) -> SolverStateSession:
        session = self.session(root, "source", SOURCE_CASE)
        session.record_evidence(
            "context-tool-observation",
            "synthetic",
            {"tool": "pyenv", "present": True, "path": "/usr/bin/pyenv"},
            evidence_id="evidence-context-tool-pyenv",
        )
        session.record_evidence(
            "context-runtime-root",
            "synthetic",
            {"manager": "pyenv", "root": "/root/.pyenv"},
            evidence_id="evidence-context-runtime-root-pyenv",
        )
        session.record_evidence(
            "context-runtime-inventory",
            "synthetic",
            {"manager": "pyenv", "versions": ["3.11.9"]},
            evidence_id="evidence-context-runtime-pyenv",
        )
        session.record_evidence(
            "action-result",
            "synthetic",
            {"stdout": "must not transfer", "stderr": "", "exit_code": 0},
            evidence_id="evidence-unselected-action-result",
        )
        return session

    @staticmethod
    def image(digit: str = "1") -> ImageIdentity:
        return ImageIdentity(
            "example/image:latest",
            "sha256:" + digit * 64,
            ("example/image@sha256:" + digit * 64,),
        )

    @staticmethod
    def lineage(source: SolverStateSession) -> ContextTransferLineage:
        return ContextTransferLineage(
            source_case_id=source.case_id,
            source_snapshot_hash=source.reconstruct().to_dict()["snapshot_hash"],
            source_event_log_sha256="2" * 64,
            source_summary_sha256="3" * 64,
            target_manifest_sha256="4" * 64,
            target_audit_sha256="5" * 64,
            target_raw_result_path="recorded/result.json",
            target_raw_result_sha256="6" * 64,
        )

    def test_matching_transfer_is_selected_traced_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.source(root)
            target = self.session(root, "target", TARGET_CASE)
            lineage = self.lineage(source)
            first = transfer_context_evidence(
                source.reconstruct(),
                target,
                self.image(),
                self.image(),
                lineage,
            )
            second = transfer_context_evidence(
                source.reconstruct(),
                target,
                self.image(),
                self.image(),
                lineage,
            )

            self.assertEqual(first.appended_evidence, 3)
            self.assertTrue(first.profile_appended)
            self.assertEqual(second.appended_evidence, 0)
            self.assertFalse(second.profile_appended)
            state = target.reconstruct()
            self.assertNotIn("evidence-unselected-action-result", state.evidence)
            self.assertEqual(len(state.evidence), 3)
            context = build_repair_context(state).context
            self.assertEqual(context.runtime_manager, "pyenv")
            self.assertEqual(context.available_python_versions, ("3.11.9",))

    def test_image_mismatch_rejects_before_target_append(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.source(root)
            target = self.session(root, "target", TARGET_CASE)
            event_count = len(target.store.read())

            with self.assertRaisesRegex(ValueError, "image identities do not match"):
                transfer_context_evidence(
                    source.reconstruct(),
                    target,
                    self.image("1"),
                    self.image("2"),
                    self.lineage(source),
                )
            self.assertEqual(len(target.store.read()), event_count)

    def test_source_snapshot_mismatch_rejects_before_target_append(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.source(root)
            target = self.session(root, "target", TARGET_CASE)
            lineage = self.lineage(source)
            invalid = ContextTransferLineage(
                **{
                    **lineage.to_dict(),
                    "source_snapshot_hash": "0" * 64,
                }
            )
            event_count = len(target.store.read())

            with self.assertRaisesRegex(ValueError, "snapshot hash"):
                transfer_context_evidence(
                    source.reconstruct(),
                    target,
                    self.image(),
                    self.image(),
                    invalid,
                )
            self.assertEqual(len(target.store.read()), event_count)

    def test_existing_different_profile_rejects_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.source(root)
            target = self.session(root, "target", TARGET_CASE)
            target.profile_repository({"kind": "different-profile"})
            event_count = len(target.store.read())

            with self.assertRaisesRegex(ValueError, "different repository profile"):
                transfer_context_evidence(
                    source.reconstruct(),
                    target,
                    self.image(),
                    self.image(),
                    self.lineage(source),
                )
            self.assertEqual(len(target.store.read()), event_count)


if __name__ == "__main__":
    unittest.main()
