from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from envsolve.verification.native_project import (
    NativeOutcome,
    NativeProbeKind,
    NativeProjectPlanner,
    evaluate_native_outcome,
)


class NativeProjectTests(unittest.TestCase):
    def plan(self, files: dict[str, str]):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name, content in files.items():
            (root / name).write_text(content, encoding="utf-8")
        return NativeProjectPlanner().plan(root, "/env/python", root / "wheels")

    def test_pytest_ini_selects_non_shell_collection(self) -> None:
        plan = self.plan({"pytest.ini": "[pytest]\ntestpaths = tests\n", "setup.py": ""})

        self.assertEqual(plan.probe.kind, NativeProbeKind.PYTEST_COLLECTION)
        self.assertEqual(
            plan.probe.argv,
            (
                "/env/python",
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
            ),
        )
        self.assertEqual(plan.probe.config_evidence[0].path, "pytest.ini")
        self.assertEqual(
            plan.probe.config_evidence[0].sha256,
            hashlib.sha256(b"[pytest]\ntestpaths = tests\n").hexdigest(),
        )

    def test_structured_pyproject_and_setup_cfg_pytest_detection(self) -> None:
        pyproject = self.plan(
            {"pyproject.toml": "[tool.pytest.ini_options]\naddopts = '-ra'\n"}
        )
        setup_cfg = self.plan({"setup.cfg": "[tool:pytest]\naddopts = -ra\n"})

        self.assertEqual(pyproject.probe.kind, NativeProbeKind.PYTEST_COLLECTION)
        self.assertEqual(setup_cfg.probe.kind, NativeProbeKind.PYTEST_COLLECTION)

    def test_non_table_pytest_configuration_does_not_crash_planner(self) -> None:
        plan = self.plan({"pyproject.toml": "tool = 'not-a-table'\n"})

        self.assertEqual(plan.probe.kind, NativeProbeKind.WHEEL_BUILD)

    def test_build_metadata_falls_back_to_isolated_wheel_output(self) -> None:
        plan = self.plan(
            {"pyproject.toml": "[build-system]\nrequires = ['setuptools']\n"}
        )

        self.assertEqual(plan.probe.kind, NativeProbeKind.WHEEL_BUILD)
        self.assertEqual(plan.probe.argv[:4], ("/env/python", "-m", "pip", "wheel"))
        self.assertIn("--no-build-isolation", plan.probe.argv)
        self.assertEqual(plan.probe.argv[-1], ".")

    def test_missing_declaration_is_unknown(self) -> None:
        plan = self.plan({"README.md": "sample"})

        self.assertIsNone(plan.probe)
        self.assertIsNone(evaluate_native_outcome(plan, None).passed)

    def test_collection_and_build_decisions_are_three_valued(self) -> None:
        collection = self.plan({"pytest.ini": "[pytest]\n"})
        build = self.plan({"setup.py": "from setuptools import setup\nsetup()\n"})

        self.assertTrue(
            evaluate_native_outcome(collection, NativeOutcome(0, False)).passed
        )
        self.assertIsNone(
            evaluate_native_outcome(collection, NativeOutcome(5, False)).passed
        )
        self.assertFalse(
            evaluate_native_outcome(collection, NativeOutcome(2, False)).passed
        )
        self.assertFalse(
            evaluate_native_outcome(collection, NativeOutcome(None, True)).passed
        )
        self.assertFalse(
            evaluate_native_outcome(build, NativeOutcome(0, False)).passed
        )
        self.assertTrue(
            evaluate_native_outcome(
                build, NativeOutcome(0, False, ("sample.whl",))
            ).passed
        )


if __name__ == "__main__":
    unittest.main()
