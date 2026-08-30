from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import zlib

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.compatibility_ledger import (
    CompatibilityDeltaLedger,
    CompatibilityLedgerService,
    ScheduledCompatibilityObserver,
    _extract_projection_receipt,
    _extract_projection,
    _decode_projection,
    _probe_command,
    model_visible_scheduled_observation,
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


def test_scheduled_observer_applies_initial_periodic_and_dirty_replay_dose() -> None:
    class Service:
        def __init__(self) -> None:
            self.call_ids: list[str] = []

        def check(self, call_id: str) -> dict[str, object]:
            self.call_ids.append(call_id)
            return {
                "ok": True,
                "finding_set_complete": True,
                "goal_status": "fail",
                "candidate_ready": False,
                "current": {"obligation_count": 1},
                "delta_from_previous": {"classification": "stagnant"},
            }

        def metadata(self) -> dict[str, object]:
            return {
                "observation_count": len(self.call_ids),
                "complete_observation_count": len(self.call_ids),
            }

    service = Service()
    observer = ScheduledCompatibilityObserver(service, cadence=2)  # type: ignore[arg-type]

    initial = observer.observe_initial()
    first = observer.after_shell_operation()
    periodic = observer.after_shell_operation()
    third = observer.after_shell_operation()
    before_replay = observer.before_replay()
    repeated_replay = observer.before_replay()
    metadata = observer.metadata()

    assert initial["trigger"] == "initial"
    assert first is None
    assert periodic is not None and periodic["trigger"] == "periodic"
    assert third is None
    assert before_replay is not None and before_replay["trigger"] == "pre-replay-dirty"
    assert repeated_replay is None
    assert service.call_ids == [
        "scheduled-initial-1",
        "scheduled-periodic-2",
        "scheduled-pre-replay-dirty-3",
    ]
    assert metadata["schedule_compliant"] is True
    assert metadata["complete_observation_rate"] == 1.0
    assert metadata["optional_compatibility_tool_exposed"] is False
    assert metadata["operation_constraints_added"] is False
    assert metadata["stores_container_checkpoint"] is False


def test_model_projection_is_bounded_while_trajectory_evidence_remains_complete() -> None:
    ledger = CompatibilityDeltaLedger("envsolve-goal-report-v1")
    full_result = ledger.observe(
        _report(*(f"module_{index}" for index in range(200))),
        {"python_executable": "/usr/bin/python"},
    )
    observation = {
        "trigger": "initial",
        "observation_number": 1,
        "result": full_result,
    }

    projected = model_visible_scheduled_observation(observation)

    assert len(full_result["current"]["obligations"]) == 200
    assert len(projected["result"]["current"]["obligations"]) == 128
    assert projected["result"]["current"]["obligation_count"] == 200
    assert projected["result"]["current"]["obligation_set_sha256"] == full_result[
        "current"
    ]["obligation_set_sha256"]
    assert projected["result"]["model_projection"]["sections"]["current"] == {
        "total_count": 200,
        "visible_count": 128,
        "truncated": True,
    }
    assert projected["result"]["model_projection"][
        "complete_machine_evidence_retained_in_trajectory"
    ] is True


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
    assert "ENVSOLVE_COMPATIBILITY_LEDGER_RECEIPT_V1" in command
    assert "goal_output" in command
    assert 'unset "$ENVSOLVE_LEDGER_NAME"' in command
    assert _extract_projection(output, nonce) == projection
    assert _extract_projection(output, "different") is None


def test_probe_runs_from_project_root_without_losing_active_environment() -> None:
    with tempfile.TemporaryDirectory() as directory:
        project_root = Path(directory) / "project"
        caller_cwd = project_root / "nested" / "work"
        caller_cwd.mkdir(parents=True)
        nonce = "cwd-invariance"
        projection_path = Path(f"/tmp/envsolve-ledger-projection-{nonce}.json")
        contract = ExecutableGoalContract(
            "goal",
            "record goal execution identity",
            r'''command python - "$ENVSOLVE_GOAL_REPORT" <<'PY'
import json
import os
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(json.dumps({
    "schema": "envsolve-goal-report-v1",
    "status": "pass",
    "finding_set_complete": True,
    "findings": [],
    "details": {
        "goal_cwd": os.getcwd(),
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
    },
}))
PY''',
        )
        environment = dict(os.environ)
        environment["PATH"] = os.pathsep.join(
            (str(Path(sys.executable).parent), environment.get("PATH", ""))
        )
        environment["VIRTUAL_ENV"] = "/tmp/envsolve-active-environment"
        try:
            completed = subprocess.run(
                ["bash", "-c", _probe_command(contract, nonce, str(project_root))],
                cwd=caller_cwd,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            encoded = projection_path.read_text(encoding="ascii")
            projection = _decode_projection(encoded)
        finally:
            projection_path.unlink(missing_ok=True)

    assert completed.returncode == 0, completed.stderr
    assert projection is not None
    assert Path(projection["report"]["details"]["goal_cwd"]).resolve() == (
        project_root.resolve()
    )
    assert projection["report"]["details"]["virtual_env"] == (
        "/tmp/envsolve-active-environment"
    )
    assert Path(projection["environment"]["cwd"]).resolve() == project_root.resolve()
    assert Path(
        projection["environment"]["observation_caller_cwd"]
    ).resolve() == caller_cwd.resolve()
    assert projection["environment"]["virtual_env"] == (
        "/tmp/envsolve-active-environment"
    )


def test_projection_receipt_is_nonce_size_and_hash_bound() -> None:
    nonce = "abc123"
    digest = "a" * 64
    output = (
        f"ENVSOLVE_COMPATIBILITY_LEDGER_BEGIN_V1={nonce}\n"
        f"ENVSOLVE_COMPATIBILITY_LEDGER_RECEIPT_V1={nonce}:123:{digest}\n"
        f"ENVSOLVE_COMPATIBILITY_LEDGER_END_V1={nonce}\n"
    )

    assert _extract_projection_receipt(output, nonce) == (123, digest)
    assert _extract_projection_receipt(output, "different") is None


def test_chunked_projection_transport_reassembles_and_verifies_content() -> None:
    projection = {
        "values": [hashlib.sha256(str(index).encode()).hexdigest() for index in range(2000)]
    }
    encoded = base64.b64encode(
        zlib.compress(json.dumps(projection).encode(), level=9)
    ).decode()

    class Server:
        def handle(self, request: dict[str, object]) -> dict[str, object]:
            params = request["params"]
            arguments = params["arguments"]  # type: ignore[index]
            command = arguments["command"]  # type: ignore[index]
            words = shlex.split(command)  # type: ignore[arg-type]
            offset, count = map(int, words[-2:])
            return {
                "result": {
                    "structuredContent": {
                        "output": encoded[offset : offset + count] + "\n",
                        "exit_code": 0,
                        "timed_out": False,
                        "output_truncated": False,
                        "infrastructure_error": None,
                    }
                }
            }

    service = CompatibilityLedgerService(
        ExecutableGoalContract("goal", "test goal", "true"),
        Server(),  # type: ignore[arg-type]
    )

    restored = service._read_projection(
        "/tmp/projection",
        len(encoded),
        hashlib.sha256(encoded.encode()).hexdigest(),
        "call",
    )
    rejected = service._read_projection(
        "/tmp/projection",
        len(encoded),
        "0" * 64,
        "call",
    )

    assert len(encoded) > 12_000
    assert restored == projection
    assert rejected is None
