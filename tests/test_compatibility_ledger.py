from __future__ import annotations

import base64
import json
import zlib

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.compatibility_ledger import (
    CompatibilityDeltaLedger,
    _extract_projection,
    _probe_command,
)


def _report(*subjects: str, complete: bool = True) -> dict[str, object]:
    return {
        "schema": "envsolve-goal-report-v1",
        "status": "fail" if subjects else "pass",
        "finding_set_complete": complete,
        "findings": [
            {
                "domain": "module",
                "subject": subject,
                "predicate": "present",
                "required": True,
                "observed": False,
            }
            for subject in subjects
        ],
    }


def test_ledger_retains_nondominated_evidence_without_blocking_regression() -> None:
    ledger = CompatibilityDeltaLedger("envsolve-goal-report-v1")
    environment = {"python_executable": "/venv/bin/python"}

    initial = ledger.observe(_report("a", "b", "c"), environment)
    improved = ledger.observe(_report("b", "c"), environment)
    mixed = ledger.observe(_report("b", "d"), environment)
    regressed = ledger.observe(_report("b", "c", "d"), environment)
    passed = ledger.observe(_report(), environment)

    assert initial["delta_from_previous"]["classification"] == "initial"
    assert improved["delta_from_previous"] == {
        "classification": "improved",
        "resolved": [
            {
                "domain": "module",
                "predicate": "present",
                "required": True,
                "subject": "a",
            }
        ],
        "introduced": [],
    }
    assert mixed["delta_from_previous"]["classification"] == "mixed"
    assert mixed["frontier"]["size"] == 2
    assert regressed["delta_from_previous"]["classification"] == "regressed"
    assert regressed["frontier"]["changed"] is False
    assert regressed["frontier"]["current_is_dominated"] is True
    assert regressed["operation_constraints_added"] is False
    assert passed["candidate_ready"] is True
    assert passed["frontier"]["size"] == 1
    assert passed["frontier"]["best_anchor"]["obligation_count"] == 0
    assert ledger.metadata()["transition_counts"] == {
        "improved": 2,
        "initial": 1,
        "mixed": 1,
        "regressed": 1,
    }


def test_incomplete_observation_does_not_mutate_compatibility_frontier() -> None:
    ledger = CompatibilityDeltaLedger("envsolve-goal-report-v1")
    environment = {"python_executable": "/usr/bin/python"}
    ledger.observe(_report("a"), environment)

    unknown = ledger.observe(_report("b", complete=False), environment)
    after = ledger.observe(_report("a"), environment)

    assert unknown["ok"] is False
    assert unknown["ledger_updated"] is False
    assert after["delta_from_previous"]["classification"] == "stagnant"
    assert ledger.metadata()["complete_observation_count"] == 2
    assert ledger.metadata()["frontier_size"] == 1


def test_unknown_status_does_not_mutate_compatibility_frontier() -> None:
    ledger = CompatibilityDeltaLedger("envsolve-goal-report-v1")
    environment = {"python_executable": "/usr/bin/python"}
    ledger.observe(_report("a"), environment)
    report = _report()
    report["status"] = "unknown"

    unknown = ledger.observe(report, environment)
    after = ledger.observe(_report("a"), environment)

    assert unknown["ok"] is False
    assert unknown["reason"] == "goal status is unknown"
    assert unknown["ledger_updated"] is False
    assert after["delta_from_previous"]["classification"] == "stagnant"
    assert ledger.metadata()["complete_observation_count"] == 2
    assert ledger.metadata()["frontier_size"] == 1


def test_probe_command_and_projection_are_nonce_bound() -> None:
    contract = ExecutableGoalContract(
        "goal",
        "test goal",
        'printf \'{"schema":"envsolve-goal-report-v1","status":"pass",'
        '"finding_set_complete":true,"findings":[]}\' > "$ENVSOLVE_GOAL_REPORT"',
        protected_environment_prefixes=("PYRIGHT_",),
    )
    nonce = "abc123"
    command = _probe_command(contract, nonce)
    projection = {
        "goal_exit_code": 0,
        "environment": {"python_executable": "/usr/bin/python"},
        "report": _report(),
    }
    output = (
        "setup output\n"
        f"ENVSOLVE_COMPATIBILITY_LEDGER_BEGIN_V1={nonce}\n"
        f"{base64.b64encode(zlib.compress(json.dumps(projection).encode())).decode()}\n"
        f"ENVSOLVE_COMPATIBILITY_LEDGER_END_V1={nonce}\n"
    )

    assert contract.program in command
    assert command.index(contract.program) < command.index(
        "ENVSOLVE_LEDGER_FINGERPRINT_PY"
    )
    assert "python_distributions_sha256" in command
    assert "zlib.compress" in command
    assert 'unset "$ENVSOLVE_LEDGER_NAME"' in command
    assert _extract_projection(output, nonce) == projection
    assert _extract_projection(output, "different") is None
