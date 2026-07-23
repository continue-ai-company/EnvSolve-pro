from __future__ import annotations

from collections import Counter
import re
from typing import Any

from envsolve_harness.core.models import VerificationEvidence


MISSING_IMPORT_PATTERN = re.compile(r'Import "([^"]+)" could not be resolved')


def build_envbench_diagnostic_evidence(
    raw: dict[str, Any],
    completed: bool,
    artifact_path: str | None,
) -> tuple[VerificationEvidence, ...]:
    exit_code = raw.get("exit_code")
    bootstrap_passed = exit_code == 0 if completed else None
    bootstrap = VerificationEvidence(
        verifier_id="envbench-bootstrap-diagnostic",
        channel="diagnostic",
        passed=bootstrap_passed,
        summary=(
            "Non-scoring bootstrap completed"
            if bootstrap_passed
            else "Non-scoring bootstrap did not complete"
        ),
        metrics={"exit_code": exit_code},
        artifact_path=artifact_path,
    )

    pyright = raw.get("pyright") if isinstance(raw.get("pyright"), dict) else {}
    summary = pyright.get("summary") if isinstance(pyright.get("summary"), dict) else {}
    diagnostics = pyright.get("generalDiagnostics")
    if not isinstance(diagnostics, list):
        diagnostics = []
    valid_diagnostics = [item for item in diagnostics if isinstance(item, dict)]
    severity_counts = Counter(
        str(item.get("severity", "unknown")) for item in valid_diagnostics
    )
    rule_counts = Counter(str(item.get("rule", "unknown")) for item in valid_diagnostics)
    missing_import_modules = sorted(
        {
            match.group(1)
            for item in valid_diagnostics
            if item.get("rule") == "reportMissingImports"
            for match in [MISSING_IMPORT_PATTERN.search(str(item.get("message", "")))]
            if match is not None
        }
    )
    error_count = summary.get("errorCount")
    pyright_executed = completed and isinstance(error_count, int)
    pyright_evidence = VerificationEvidence(
        verifier_id="envbench-pyright-diagnostic",
        channel="diagnostic",
        passed=None,
        summary=(
            "Non-scoring Pyright diagnostics recorded"
            if pyright_executed
            else "Non-scoring Pyright diagnostics unavailable"
        ),
        metrics={
            "objective_role": "non_scoring",
            "diagnostic_count": len(valid_diagnostics),
            "error_count": error_count,
            "warning_count": summary.get("warningCount"),
            "information_count": summary.get("informationCount"),
            "files_analyzed": summary.get("filesAnalyzed"),
            "severity_counts": dict(sorted(severity_counts.items())),
            "rule_counts": dict(sorted(rule_counts.items())),
            "missing_import_count": len(missing_import_modules),
            "missing_import_modules": missing_import_modules,
            "non_missing_import_error_count": sum(
                item.get("severity") == "error"
                and item.get("rule") != "reportMissingImports"
                for item in valid_diagnostics
            ),
            "pyright_version": pyright.get("version"),
        },
        artifact_path=artifact_path,
    )
    return bootstrap, pyright_evidence
