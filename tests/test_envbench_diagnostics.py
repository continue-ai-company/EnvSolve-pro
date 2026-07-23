from __future__ import annotations

import unittest

from envsolve_harness.adapters.envbench_diagnostics import (
    build_envbench_diagnostic_evidence,
)


class EnvBenchDiagnosticEvidenceTest(unittest.TestCase):
    def test_preserves_non_scoring_diagnostic_structure(self) -> None:
        evidence = build_envbench_diagnostic_evidence(
            {
                "exit_code": 0,
                "pyright": {
                    "version": "1.2.3",
                    "summary": {
                        "errorCount": 3,
                        "warningCount": 1,
                        "informationCount": 0,
                        "filesAnalyzed": 10,
                    },
                    "generalDiagnostics": [
                        {
                            "severity": "error",
                            "rule": "reportMissingImports",
                            "message": 'Import "missing.package" could not be resolved',
                        },
                        {
                            "severity": "error",
                            "rule": "reportPrivateImportUsage",
                            "message": "private import",
                        },
                        {
                            "severity": "error",
                            "rule": "reportPrivateImportUsage",
                            "message": "another private import",
                        },
                    ],
                },
            },
            completed=True,
            artifact_path="evaluation/json/results.jsonl",
        )

        self.assertEqual([item.channel for item in evidence], ["diagnostic"] * 2)
        self.assertTrue(evidence[0].passed)
        self.assertIsNone(evidence[1].passed)
        metrics = evidence[1].metrics
        self.assertEqual(metrics["objective_role"], "non_scoring")
        self.assertEqual(metrics["missing_import_modules"], ["missing.package"])
        self.assertEqual(metrics["non_missing_import_error_count"], 2)
        self.assertEqual(metrics["rule_counts"]["reportPrivateImportUsage"], 2)

    def test_incomplete_evaluation_has_unknown_diagnostic_passes(self) -> None:
        evidence = build_envbench_diagnostic_evidence(
            {}, completed=False, artifact_path=None
        )

        self.assertEqual([item.passed for item in evidence], [None, None])


if __name__ == "__main__":
    unittest.main()
