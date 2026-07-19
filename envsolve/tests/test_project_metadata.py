from __future__ import annotations

import unittest

from envsolve.workspace.project_metadata import (
    MissingImportObligation,
    ProjectExtraPolicy,
)


HASH = "a" * 64


class ProjectExtraPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ProjectExtraPolicy()
        self.obligations = (
            MissingImportObligation("pytest", "/data/project/tests/test_one.py"),
            MissingImportObligation("pytest", "/data/project/tests/test_two.py"),
        )

    def test_selects_metadata_declared_test_extra_used_by_test_tool(self) -> None:
        extras = self.policy.extras_from_metadata(
            {"test": ["pytest >= 6"], "doc": ["sphinx"]},
            HASH,
            {"test"},
        )

        repair = self.policy.plan(self.obligations, extras)

        self.assertIsNotNone(repair)
        assert repair is not None
        self.assertEqual(repair.extra.name, "test")
        self.assertEqual(
            repair.install_command(),
            'python -m pip install --no-build-isolation -e ".[test]"',
        )

    def test_rejects_test_extra_not_selected_by_project_test_tool(self) -> None:
        extras = self.policy.extras_from_metadata({"test": ["pytest"]}, HASH, set())
        self.assertIsNone(self.policy.plan(self.obligations, extras))

    def test_rejects_runtime_obligation(self) -> None:
        extras = self.policy.extras_from_metadata({"test": ["pytest"]}, HASH, {"test"})
        obligations = (MissingImportObligation("requests", "/data/project/src/client.py"),)
        self.assertIsNone(self.policy.plan(obligations, extras))

    def test_rejects_ambiguous_test_extras(self) -> None:
        extras = self.policy.extras_from_metadata(
            {"test": ["pytest"], "testing": ["pytest"]},
            HASH,
            {"test", "testing"},
        )
        self.assertIsNone(self.policy.plan(self.obligations, extras))

