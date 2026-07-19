from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.runtime.declarations import collect_repository_constraints
from envsolve.constraints import ConstraintEngine, InitialConstraintEvidence


class RepositoryDeclarationTests(unittest.TestCase):
    def test_pep621_admits_only_unconditional_base_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                "[project]\n"
                'name = "demo"\n'
                'requires-python = ">=3.9,<3.13"\n'
                "dependencies = [\n"
                '  "Requests>=2",\n'
                '  "uvloop; sys_platform != \'win32\'",\n'
                '  "httpx[http2]",\n'
                "]\n",
                encoding="utf-8",
            )

            inventory = collect_repository_constraints(root)

            self.assertEqual(len(inventory.evidence), 2)
            self.assertEqual(len(inventory.runtime_requirements), 1)
            values = {item.value["name"]: item.value for item in inventory.evidence}
            self.assertEqual(set(values), {"Requests", "httpx"})
            self.assertEqual(values["Requests"]["specifier"], ">=2")
            self.assertEqual(values["httpx"]["extras"], ["http2"])
            self.assertTrue(values["httpx"]["present"])
            self.assertEqual(
                [item.reason for item in inventory.diagnostics],
                ["environment-marker-unresolved"],
            )
            self.assertEqual(inventory.summary()["schema"], "envsolve-repository-declarations-v2")

            base_runtime = InitialConstraintEvidence(
                "base-runtime-test",
                "runtime-observation",
                "fresh-base-runtime:sha256:test",
                {
                    "name": "python",
                    "version": "3.13.2",
                    "image_digest": "sha256:test",
                },
            )
            self.assertEqual(inventory.admissible_evidence(None), inventory.evidence)
            with self.assertRaises(ValueError):
                inventory.admissible_evidence(
                    InitialConstraintEvidence(
                        "unbound-runtime-test",
                        "runtime-observation",
                        "unbound-observer",
                        {"name": "python", "version": "3.13.2"},
                    )
                )
            admitted = inventory.admissible_evidence(base_runtime)
            self.assertEqual(
                {item.kind for item in admitted},
                {"package-requirement", "runtime-requirement", "runtime-observation"},
            )
            self.assertEqual(len(admitted), 4)
            normalized = tuple(
                constraint
                for item in admitted
                for constraint in ConstraintEngine().normalizer.normalize(
                    item.evidence_id,
                    {
                        "kind": item.kind,
                        "value": item.value,
                        "confidence": item.confidence,
                    },
                )
            )
            runtime_conflicts = [
                conflict
                for conflict in ConstraintEngine().solve(normalized).conflicts
                if conflict.domain == "runtime"
            ]
            self.assertEqual(len(runtime_conflicts), 1)
            self.assertIn("3.13.2", runtime_conflicts[0].message)

    def test_setup_cfg_and_requirements_use_structured_pep508_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "setup.cfg").write_text(
                "[options]\n"
                "python_requires = >=3.9\n"
                "install_requires =\n"
                "    click>=8\n"
                "    importlib-metadata; python_version < '3.10'\n",
                encoding="utf-8",
            )
            (root / "requirements-test.txt").write_text(
                "pytest>=8  # test runner\n"
                "-r requirements-extra.txt\n"
                "broken requirement !!!\n",
                encoding="utf-8",
            )

            inventory = collect_repository_constraints(root)

            values = {item.value["name"]: item.value for item in inventory.evidence}
            self.assertEqual(set(values), {"click", "pytest"})
            self.assertEqual(len(inventory.runtime_requirements), 1)
            self.assertEqual(values["click"]["specifier"], ">=8")
            self.assertEqual(values["pytest"]["source_path"], "requirements-test.txt")
            self.assertEqual(
                {item.reason for item in inventory.diagnostics},
                {
                    "environment-marker-unresolved",
                    "unsupported-requirements-directive",
                    "invalid-pep508-requirement",
                },
            )
            self.assertTrue(
                all(len(item.value["source_sha256"]) == 64 for item in inventory.evidence)
            )

    def test_evidence_identity_is_deterministic_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements.txt").write_text(
                "alpha\nbeta\ngamma\n", encoding="utf-8"
            )

            first = collect_repository_constraints(root, max_declarations=2)
            second = collect_repository_constraints(root, max_declarations=2)

            self.assertEqual(first, second)
            self.assertEqual(len(first.evidence), 2)
            self.assertIn(
                "declaration-bound-exceeded",
                {item.reason for item in first.diagnostics},
            )

    def test_empty_pep621_dependencies_and_oversized_files_fail_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "demo"\n', encoding="utf-8"
            )
            (root / "requirements.txt").write_text(
                "large-dependency\n" * 20, encoding="utf-8"
            )

            inventory = collect_repository_constraints(root, max_source_bytes=80)

            self.assertFalse(inventory.evidence)
            self.assertEqual(
                [item.reason for item in inventory.diagnostics],
                ["source-byte-bound-exceeded"],
            )
            self.assertEqual(inventory.files_observed, ("pyproject.toml",))


if __name__ == "__main__":
    unittest.main()
