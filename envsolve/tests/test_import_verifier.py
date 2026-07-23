from __future__ import annotations

import unittest

from envsolve.verification.imports import (
    EnvironmentFacts,
    ExclusionRule,
    ImportContextAnalyzer,
    ImportDisposition,
    MissingImportFinding,
    SourceRole,
    exclusion_rules_from_pyproject,
    source_role,
)


FACTS = EnvironmentFacts(sys_platform="linux", python_major=3, platform_name="linux")
HASH = "a" * 64


class ImportContextAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = ImportContextAnalyzer()

    def finding(self, module: str, file: str, line: int) -> MissingImportFinding:
        return MissingImportFinding(module, file, line, f'Import "{module}" could not be resolved')

    def test_source_role_is_descriptive(self) -> None:
        self.assertEqual(source_role("tests/fixtures/setup.py"), SourceRole.FIXTURE)
        self.assertEqual(source_role("docs/conf.py"), SourceRole.DOCUMENTATION)
        assessment = self.analyzer.assess(
            self.finding("pytest", "tests/test_core.py", 0),
            "import pytest\n",
            FACTS,
        )
        self.assertEqual(assessment.disposition, ImportDisposition.ACTIVE_OBLIGATION)

    def test_importerror_fallback_is_guarded_optional(self) -> None:
        source = "try:\n    import speedup\nexcept ImportError:\n    speedup = None\n"
        assessment = self.analyzer.assess(
            self.finding("speedup", "src/pkg.py", 1), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.GUARDED_OPTIONAL)

    def test_type_checking_branch_is_static_only(self) -> None:
        source = (
            "from typing import TYPE_CHECKING as TC\n"
            "if TC:\n"
            "    import typed_dependency\n"
        )
        assessment = self.analyzer.assess(
            self.finding("typed_dependency", "src/pkg.py", 2), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.STATIC_ONLY)

    def test_scanned_documentation_import_remains_a_repair_obligation(self) -> None:
        assessment = self.analyzer.assess(
            self.finding("sphinx", "docs/conf.py", 0),
            "import sphinx\n",
            FACTS,
        )

        self.assertEqual(assessment.disposition, ImportDisposition.DOCUMENTATION_SCOPE)
        self.assertTrue(assessment.active_repair_obligation)

    def test_unknown_exception_does_not_waive_import(self) -> None:
        source = "try:\n    import speedup\nexcept ValueError:\n    pass\n"
        assessment = self.analyzer.assess(
            self.finding("speedup", "src/pkg.py", 1), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.ACTIVE_OBLIGATION)

    def test_inactive_platform_branch_is_detected(self) -> None:
        source = 'import sys\nif sys.platform == "darwin":\n    import xattr\n'
        assessment = self.analyzer.assess(
            self.finding("xattr", "src/pkg.py", 2), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.INACTIVE_PLATFORM)

    def test_true_skipif_makes_function_import_inactive(self) -> None:
        source = (
            "import sys\n"
            "import pytest\n"
            '@pytest.mark.skipif(sys.platform != "darwin", reason="darwin")\n'
            "def test_xattr():\n"
            "    import xattr\n"
        )
        assessment = self.analyzer.assess(
            self.finding("xattr", "tests/test_env.py", 4), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.INACTIVE_PLATFORM)

    def test_python_major_compatibility_branch_is_detected(self) -> None:
        source = (
            "import sys\n"
            "PY3 = sys.version_info[0] == 3\n"
            "if PY3:\n"
            "    import io\n"
            "else:\n"
            "    import StringIO\n"
        )
        assessment = self.analyzer.assess(
            self.finding("StringIO", "src/vendor/six.py", 5), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.INACTIVE_PLATFORM)

    def test_python_version_tuple_guard_is_evaluated(self) -> None:
        source = (
            "import sys\n"
            "if sys.version_info < (3, 11):\n"
            "    import tomli\n"
        )
        finding = self.finding("tomli", "src/compat.py", 2)

        inactive = self.analyzer.assess(
            finding,
            source,
            EnvironmentFacts("linux", 3, "linux", (3, 13, 2)),
        )
        active = self.analyzer.assess(
            finding,
            source,
            EnvironmentFacts("linux", 3, "linux", (3, 10, 14)),
        )

        self.assertEqual(inactive.disposition, ImportDisposition.INACTIVE_PLATFORM)
        self.assertEqual(active.disposition, ImportDisposition.ACTIVE_OBLIGATION)

    def test_default_false_optional_branch_is_detected(self) -> None:
        source = "def profile(enabled=False):\n    if enabled:\n        import yappi\n"
        assessment = self.analyzer.assess(
            self.finding("yappi", "tests/profile.py", 2), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.GUARDED_OPTIONAL)

    def test_none_default_does_not_prove_runtime_argument(self) -> None:
        source = (
            "def connect(port=None):\n"
            "    if port is not None:\n"
            "        import usb\n"
        )
        assessment = self.analyzer.assess(
            self.finding("usb", "src/transport.py", 2), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.ACTIVE_OBLIGATION)

    def test_default_true_branch_remains_active(self) -> None:
        source = "def profile(enabled=True):\n    if enabled:\n        import yappi\n"
        assessment = self.analyzer.assess(
            self.finding("yappi", "src/profile.py", 2), source, FACTS
        )
        self.assertEqual(assessment.disposition, ImportDisposition.ACTIVE_OBLIGATION)

    def test_fixture_requires_proven_project_exclusion(self) -> None:
        finding = self.finding("legacy", "tests/fixtures/legacy/setup.py", 0)
        without = self.analyzer.assess(finding, "import legacy\n", FACTS)
        with_rule = self.analyzer.assess(
            finding,
            "import legacy\n",
            FACTS,
            [ExclusionRule("mypy", "tests/fixtures", HASH, "prefix")],
        )
        self.assertEqual(without.disposition, ImportDisposition.UNRESOLVED)
        self.assertEqual(with_rule.disposition, ImportDisposition.PROJECT_EXCLUDED_FIXTURE)

    def test_invalid_exclusion_provenance_fails_closed(self) -> None:
        finding = self.finding("legacy", "tests/fixtures/legacy/setup.py", 0)
        assessment = self.analyzer.assess(
            finding,
            "import legacy\n",
            FACTS,
            [ExclusionRule("mypy", "tests/fixtures", "short", "prefix")],
        )
        self.assertEqual(assessment.disposition, ImportDisposition.UNRESOLVED)

    def test_extracts_only_grounded_project_exclusions(self) -> None:
        rules = exclusion_rules_from_pyproject(
            {
                "tool": {
                    "mypy": {"exclude": ["tests/fixtures", "^(generated|vendor)/"]},
                    "ruff": {"extend-exclude": ["docs/*"]},
                }
            },
            HASH,
        )
        self.assertEqual(
            [(item.tool, item.pattern, item.syntax) for item in rules],
            [("mypy", "tests/fixtures", "prefix"), ("ruff", "docs/*", "glob")],
        )
