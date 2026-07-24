from __future__ import annotations

from textwrap import dedent

from envsolve.runtime import ExecutableGoalContract


_PYRIGHT_MISSING_IMPORT_GOAL = dedent(
    r"""
    write_missing_capability() {
        python - "$1" "$ENVSOLVE_GOAL_REPORT" <<'PY'
    import json
    from pathlib import Path
    import sys

    capability, report_path = sys.argv[1], Path(sys.argv[2])
    report_path.write_text(
        json.dumps(
            {
                "schema": "envsolve-goal-report-v1",
                "status": "fail",
                "findings": [
                    {
                        "finding_id": f"missing-capability-{capability}",
                        "domain": "capability",
                        "subject": capability,
                        "predicate": "present",
                        "required": True,
                        "observed": False,
                        "provenance": {
                            "criterion": "official bootstrap command availability"
                        },
                    }
                ],
                "details": {
                    "criterion": "official EnvBench Python bootstrap must complete"
                },
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    PY
    }

    if ! command -v jq >/dev/null 2>&1; then
        write_missing_capability "jq"
        exit 0
    fi

    PYRIGHT_OUTPUT=$(mktemp)
    PYRIGHT_VERSION=$(mktemp)
    cleanup_envsolve_goal() {
        rm -f "$PYRIGHT_OUTPUT" "$PYRIGHT_VERSION"
    }
    trap cleanup_envsolve_goal EXIT

    python -m pip install --quiet pyright
    if ! command -v pyright >/dev/null 2>&1; then
        write_missing_capability "pyright-cli"
        exit 0
    fi
    python -m pyright --version > "$PYRIGHT_VERSION"
    python -m pyright "$ENVSOLVE_PROJECT_ROOT" \
        --level error --outputjson > "$PYRIGHT_OUTPUT" || true

    python - "$PYRIGHT_OUTPUT" "$PYRIGHT_VERSION" "$ENVSOLVE_GOAL_REPORT" <<'PY'
    import hashlib
    import json
    from pathlib import Path
    import re
    import sys

    output_path, version_path, report_path = map(Path, sys.argv[1:])
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    diagnostics = payload.get("generalDiagnostics")
    if not isinstance(diagnostics, list):
        raise ValueError("Pyright output has no generalDiagnostics array")

    findings = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            raise ValueError("Pyright diagnostic is not an object")
        if diagnostic.get("rule") != "reportMissingImports":
            continue
        message = str(diagnostic.get("message", ""))
        match = re.search(r'Import "([^"]+)"', message)
        subject = match.group(1) if match else "unparsed-import"
        provenance = {
            "file": diagnostic.get("file"),
            "range": diagnostic.get("range"),
            "message": message,
            "rule": "reportMissingImports",
            "severity": diagnostic.get("severity"),
        }
        identity = json.dumps(
            {"subject": subject, "provenance": provenance},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        findings.append(
            {
                "finding_id": (
                    "pyright-missing-import-"
                    + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
                ),
                "domain": "module",
                "subject": subject,
                "predicate": "present",
                "required": True,
                "observed": False,
                "provenance": provenance,
            }
        )

    report = {
        "schema": "envsolve-goal-report-v1",
        "status": "fail" if findings else "pass",
        "findings": findings,
        "details": {
            "criterion": "count(reportMissingImports) == 0",
            "issues_count": len(findings),
            "pyright_version": version_path.read_text(encoding="utf-8").strip(),
        },
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    PY
    """
).strip()


def envbench_python_goal_contract() -> ExecutableGoalContract:
    return ExecutableGoalContract(
        contract_id="envbench-python-reportMissingImports-v1",
        description=(
            "After the candidate configures the environment, run Pyright over "
            "the repository and require zero reportMissingImports diagnostics. "
            "All other Pyright diagnostic rules are outside this goal."
        ),
        program=_PYRIGHT_MISSING_IMPORT_GOAL,
    )
