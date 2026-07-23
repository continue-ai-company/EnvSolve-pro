from __future__ import annotations

import unittest

from envsolve.integrations import EnvBenchFindingCollector
from envsolve.verification import FindingDisposition, StructuredFindingAdapter
from envsolve.verification.imports import EnvironmentFacts


REPOSITORY = "example/project"
REVISION = "c" * 40
FACTS = EnvironmentFacts("linux", 3, "linux-x86_64")


def raw_result(
    *,
    exit_code: int = 0,
    issues_count: int = 0,
    diagnostics: list[dict] | None = None,
    logs: str = "",
) -> dict:
    return {
        "repo_name": REPOSITORY,
        "commit_sha": REVISION,
        "exit_code": exit_code,
        "issues_count": issues_count,
        "container_logs": logs,
        "pyright": {"generalDiagnostics": diagnostics or []},
    }


def missing(module: str, path: str = "package/main.py", line: int = 0) -> dict:
    return {
        "file": f"/data/project/{path}",
        "severity": "error",
        "message": f'Import "{module}" could not be resolved',
        "range": {"start": {"line": line, "character": 0}},
        "rule": "reportMissingImports",
    }


def non_scoring_type_error(index: int) -> dict:
    return {
        "file": f"/data/project/package/module_{index}.py",
        "severity": "error",
        "message": "Argument type is incompatible",
        "range": {"start": {"line": 0, "character": 0}},
        "rule": "reportArgumentType",
    }


class EnvBenchFindingCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = EnvBenchFindingCollector(FACTS)
        self.adapter = StructuredFindingAdapter()

    def collect(self, raw: dict, sources: dict[str, str] | None = None):
        values = sources or {}
        return self.collector.collect(
            raw,
            expected_repository=REPOSITORY,
            expected_revision=REVISION,
            environment_id="fresh-env-1",
            environment_fresh=True,
            evaluation_completed=True,
            source_loader=lambda path: values[path],
        )

    def test_direct_missing_import_becomes_active_module_finding(self) -> None:
        report = self.collect(
            raw_result(issues_count=1, diagnostics=[missing("demo_dep")]),
            {"package/main.py": "import demo_dep\n"},
        )
        outcome = self.adapter.adapt(report)

        self.assertFalse(report.goal_passed)
        self.assertEqual(report.findings[0].disposition, FindingDisposition.ACTIVE)
        self.assertEqual(len(outcome.counterexamples), 2)
        self.assertEqual(
            outcome.counterexamples[0].value["finding_provenance"]["file"],
            "package/main.py",
        )

    def test_guarded_optional_import_remains_an_official_goal_obligation(self) -> None:
        report = self.collect(
            raw_result(issues_count=1, diagnostics=[missing("optional_dep", line=1)]),
            {
                "package/main.py": (
                    "try:\n"
                    "    import optional_dep\n"
                    "except ImportError:\n"
                    "    optional_dep = None\n"
                )
            },
        )
        outcome = self.adapter.adapt(report)

        self.assertEqual(report.findings[0].disposition, FindingDisposition.ACTIVE)
        self.assertEqual(
            report.findings[0].provenance["import_disposition"],
            "guarded_optional",
        )
        self.assertFalse(outcome.passed)
        self.assertEqual(len(outcome.counterexamples), 2)

    def test_missing_source_makes_the_result_unknown(self) -> None:
        report = self.collect(
            raw_result(issues_count=1, diagnostics=[missing("demo_dep")])
        )
        outcome = self.adapter.adapt(report)

        self.assertEqual(report.findings[0].disposition, FindingDisposition.UNKNOWN)
        self.assertFalse(outcome.passed)
        self.assertEqual(len(outcome.hypotheses), 1)

    def test_diagnostic_count_mismatch_is_unknown(self) -> None:
        report = self.collect(raw_result(issues_count=1, diagnostics=[]))

        outcome = self.adapter.adapt(report)
        self.assertFalse(outcome.passed)
        self.assertEqual(len(outcome.hypotheses), 1)
        self.assertFalse(report.details["diagnostic_count_matches"])

    def test_non_scoring_pyright_errors_do_not_create_constraints(self) -> None:
        diagnostics = [non_scoring_type_error(index) for index in range(1629)]
        report = self.collect(raw_result(issues_count=0, diagnostics=diagnostics))
        outcome = self.adapter.adapt(report)

        self.assertTrue(report.goal_passed)
        self.assertTrue(outcome.passed)
        self.assertEqual(report.findings, ())
        self.assertEqual(outcome.counterexamples, ())
        self.assertEqual(report.details["non_missing_import_error_count"], 1629)

    def test_network_bootstrap_failure_is_infrastructure_unknown(self) -> None:
        report = self.collect(
            raw_result(
                exit_code=2,
                logs="ReadTimeoutError while downloading a package",
            )
        )

        self.assertIsNotNone(report.infrastructure_error)
        self.assertIsNone(self.adapter.adapt(report).passed)

    def test_generic_bootstrap_module_failure_becomes_active(self) -> None:
        report = self.collect(
            raw_result(
                exit_code=1,
                logs="ModuleNotFoundError: No module named 'build_backend'",
            )
        )
        outcome = self.adapter.adapt(report)

        self.assertEqual(report.findings[0].subject, "build_backend")
        self.assertEqual(report.findings[0].disposition, FindingDisposition.ACTIVE)
        self.assertEqual(len(outcome.counterexamples), 2)

    def test_identity_mismatch_is_unknown(self) -> None:
        raw = raw_result()
        raw["repo_name"] = "other/project"
        report = self.collect(raw)

        self.assertFalse(report.completed)
        self.assertIsNone(self.adapter.adapt(report).passed)


if __name__ == "__main__":
    unittest.main()
