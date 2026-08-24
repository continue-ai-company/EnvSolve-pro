from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import shlex
from typing import Any
import uuid
import zlib

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.codex.container_mcp import ContainerMcpServer


LEDGER_SCHEMA = "envsolve-compatibility-delta-ledger-v1"
SCHEDULED_OBSERVATION_SCHEMA = "envsolve-scheduled-compatibility-observation-v1"
DEFAULT_SHELL_OBSERVATION_CADENCE = 16
_MAX_PROJECTION_BYTES = 2_000_000
_MAX_PROJECTION_TRANSPORT_BYTES = 3_000_000
_PROJECTION_CHUNK_CHARS = 12_000
_MAX_MODEL_VISIBLE_OBLIGATIONS = 128


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


def _obligation_key(value: dict[str, Any]) -> str:
    return _canonical_json(
        {
            "domain": value["domain"],
            "subject": value["subject"],
            "predicate": value["predicate"],
            "required": value.get("required"),
        }
    )


def _obligation_from_key(value: str) -> dict[str, Any]:
    result = json.loads(value)
    if not isinstance(result, dict):
        raise ValueError("Obligation key must decode to an object")
    return result


def _set_sha256(values: frozenset[str]) -> str:
    return hashlib.sha256(_canonical_json(sorted(values)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _LedgerAnchor:
    observation_index: int
    obligations: frozenset[str]
    environment: dict[str, Any]

    def summary(self, *, include_obligations: bool = False) -> dict[str, Any]:
        result = {
            "observation_index": self.observation_index,
            "obligation_count": len(self.obligations),
            "obligation_set_sha256": _set_sha256(self.obligations),
            "environment": self.environment,
        }
        if include_obligations:
            result["obligations"] = [
                _obligation_from_key(item) for item in sorted(self.obligations)
            ]
        return result


class CompatibilityDeltaLedger:
    """Retain monotonic compatibility evidence without constraining operations."""

    def __init__(self, report_schema: str) -> None:
        self.report_schema = report_schema
        self.observation_count = 0
        self.complete_observation_count = 0
        self.goal_pass_observation_count = 0
        self.previous: frozenset[str] | None = None
        self.frontier: list[_LedgerAnchor] = []
        self.transition_counts: Counter[str] = Counter()

    def observe(
        self,
        report: dict[str, Any],
        environment: dict[str, Any],
    ) -> dict[str, Any]:
        self.observation_count += 1
        status = report.get("status")
        complete = report.get("finding_set_complete")
        findings = report.get("findings")
        valid = (
            report.get("schema") == self.report_schema
            and status in {"pass", "fail", "unknown"}
            and isinstance(complete, bool)
            and isinstance(findings, list)
        )
        if not valid:
            return self._unknown("invalid goal-report schema", environment)

        obligation_values: dict[str, dict[str, Any]] = {}
        try:
            for finding in findings:
                if not isinstance(finding, dict):
                    raise ValueError("finding is not an object")
                if finding.get("observed") == finding.get("required"):
                    continue
                key = _obligation_key(finding)
                obligation_values[key] = _obligation_from_key(key)
        except (KeyError, TypeError, ValueError) as exc:
            return self._unknown(f"invalid finding: {exc}", environment)

        current = frozenset(obligation_values)
        if not complete:
            return self._unknown("goal finding set is incomplete", environment)
        if status == "unknown":
            return self._unknown("goal status is unknown", environment)
        if status == "pass" and current:
            return self._unknown("passing report has active obligations", environment)
        if status == "fail" and not current:
            return self._unknown("failing report has no active obligations", environment)

        self.complete_observation_count += 1
        if status == "pass":
            self.goal_pass_observation_count += 1
        previous = self.previous
        resolved = previous - current if previous is not None else frozenset()
        introduced = current - previous if previous is not None else frozenset()
        if previous is None:
            transition = "initial"
        elif current == previous:
            transition = "stagnant"
        elif current < previous:
            transition = "improved"
        elif previous < current:
            transition = "regressed"
        else:
            transition = "mixed"
        self.transition_counts[transition] += 1

        dominated = any(anchor.obligations <= current for anchor in self.frontier)
        frontier_changed = False
        if not dominated:
            self.frontier = [
                anchor
                for anchor in self.frontier
                if not current < anchor.obligations
            ]
            self.frontier.append(
                _LedgerAnchor(self.observation_count, current, dict(environment))
            )
            frontier_changed = True
        self.previous = current
        best = min(
            self.frontier,
            key=lambda anchor: (len(anchor.obligations), anchor.observation_index),
        )
        return {
            "schema": LEDGER_SCHEMA,
            "ok": True,
            "advisory_only": True,
            "operation_constraints_added": False,
            "observation_index": self.observation_count,
            "goal_status": status,
            "finding_set_complete": True,
            "candidate_ready": status == "pass" and not current,
            "environment": environment,
            "current": {
                "obligation_count": len(current),
                "obligation_set_sha256": _set_sha256(current),
                "obligations": [obligation_values[item] for item in sorted(current)],
            },
            "measurement": {
                "raw_finding_count": report.get("raw_finding_count"),
                "unique_obligation_count": len(current),
            },
            "delta_from_previous": {
                "classification": transition,
                "resolved": [_obligation_from_key(item) for item in sorted(resolved)],
                "introduced": [
                    _obligation_from_key(item) for item in sorted(introduced)
                ],
            },
            "frontier": {
                "changed": frontier_changed,
                "current_is_dominated": dominated,
                "size": len(self.frontier),
                "anchors": [anchor.summary() for anchor in self.frontier],
                "best_anchor": best.summary(),
            },
        }

    def _unknown(self, reason: str, environment: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": LEDGER_SCHEMA,
            "ok": False,
            "advisory_only": True,
            "operation_constraints_added": False,
            "observation_index": self.observation_count,
            "goal_status": "unknown",
            "finding_set_complete": False,
            "candidate_ready": False,
            "environment": environment,
            "reason": reason,
            "ledger_updated": False,
        }

    def observe_unknown(self, reason: str) -> dict[str, Any]:
        self.observation_count += 1
        return self._unknown(reason, {})

    def metadata(self) -> dict[str, Any]:
        best = (
            min(
                self.frontier,
                key=lambda anchor: (len(anchor.obligations), anchor.observation_index),
            )
            if self.frontier
            else None
        )
        return {
            "schema": LEDGER_SCHEMA,
            "observation_count": self.observation_count,
            "complete_observation_count": self.complete_observation_count,
            "goal_pass_observation_count": self.goal_pass_observation_count,
            "transition_counts": dict(sorted(self.transition_counts.items())),
            "frontier_size": len(self.frontier),
            "best_anchor": best.summary() if best is not None else None,
            "stores_container_checkpoint": False,
            "operation_constraints_added": False,
        }


def _probe_command(
    contract: ExecutableGoalContract,
    nonce: str,
    project_root: str = "/data/project",
) -> str:
    report_path = f"/tmp/envsolve-ledger-report-{nonce}.json"
    fingerprint_path = f"/tmp/envsolve-ledger-environment-{nonce}.json"
    projection_path = f"/tmp/envsolve-ledger-projection-{nonce}.json"
    stdout_path = f"/tmp/envsolve-ledger-goal-stdout-{nonce}.txt"
    stderr_path = f"/tmp/envsolve-ledger-goal-stderr-{nonce}.txt"
    begin = f"ENVSOLVE_COMPATIBILITY_LEDGER_BEGIN_V1={nonce}"
    end = f"ENVSOLVE_COMPATIBILITY_LEDGER_END_V1={nonce}"
    protected = " ".join(shlex.quote(item) for item in contract.protected_environment_prefixes)
    unset_protected = (
        f"for ENVSOLVE_LEDGER_PREFIX in {protected}; do "
        "while IFS='=' read -r ENVSOLVE_LEDGER_NAME _; do "
        'case "$ENVSOLVE_LEDGER_NAME" in "$ENVSOLVE_LEDGER_PREFIX"*) '
        'unset "$ENVSOLVE_LEDGER_NAME" ;; esac; '
        "done < <(/usr/bin/env); done"
        if protected
        else ":"
    )
    projection_program = r"""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import zlib

report_path, fingerprint_path, projection_path, stdout_path, stderr_path = map(
    Path, sys.argv[1:6]
)
goal_exit_code = int(sys.argv[6])
report_schema = sys.argv[7]

def bounded_output(path, limit=4096):
    try:
        data = path.read_bytes()
    except Exception as exc:
        return {"read_error": f"{type(exc).__name__}: {exc}"}
    return {
        "byte_count": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "tail": data[-limit:].decode("utf-8", errors="replace"),
        "truncated": len(data) > limit,
    }
try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    report = {
        "schema": report_schema,
        "status": "unknown",
        "finding_set_complete": False,
        "findings": [],
        "details": {"report_error": f"{type(exc).__name__}: {exc}"},
    }
try:
    environment = json.loads(fingerprint_path.read_text(encoding="utf-8"))
except Exception as exc:
    environment = {"fingerprint_error": f"{type(exc).__name__}: {exc}"}
compact_findings = []
raw_finding_count = None
if isinstance(report, dict) and isinstance(report.get("findings"), list):
    raw_finding_count = len(report["findings"])
    seen = set()
    for finding in report["findings"]:
        if not isinstance(finding, dict):
            compact_findings.append(finding)
            continue
        compact = {
            key: finding.get(key)
            for key in ("domain", "subject", "predicate", "required", "observed")
        }
        encoded = json.dumps(compact, ensure_ascii=True, sort_keys=True)
        if encoded not in seen:
            seen.add(encoded)
            compact_findings.append(compact)
projection = {
    "goal_exit_code": goal_exit_code,
    "goal_output": {
        "stdout": bounded_output(stdout_path),
        "stderr": bounded_output(stderr_path),
    },
    "environment": environment,
    "report": {
        "schema": report.get("schema") if isinstance(report, dict) else None,
        "status": report.get("status") if isinstance(report, dict) else "unknown",
        "finding_set_complete": (
            report.get("finding_set_complete", False)
            if isinstance(report, dict)
            else False
        ),
        "findings": compact_findings,
        "raw_finding_count": raw_finding_count,
        "details": report.get("details", {}) if isinstance(report, dict) else {},
    },
}
encoded = json.dumps(
    projection, ensure_ascii=True, separators=(",", ":"), sort_keys=True
).encode("utf-8")
projection_path.write_text(
    base64.b64encode(zlib.compress(encoded, level=9)).decode("ascii"),
    encoding="ascii",
)
""".strip()
    receipt_program = r"""
import hashlib
from pathlib import Path
import sys

path = Path(sys.argv[1])
nonce = sys.argv[2]
data = path.read_bytes()
print(
    f"ENVSOLVE_COMPATIBILITY_LEDGER_RECEIPT_V1={nonce}:"
    f"{len(data)}:{hashlib.sha256(data).hexdigest()}"
)
""".strip()
    fingerprint_program = r"""
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import sys

distributions = sorted(
    f"{(item.metadata.get('Name') or 'unknown').lower()}=={item.version}"
    for item in metadata.distributions()
)
python_path = [str(item) for item in sys.path]
Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "python_prefix": sys.prefix,
            "python_base_prefix": sys.base_prefix,
            "virtual_env": os.environ.get("VIRTUAL_ENV"),
            "conda_prefix": os.environ.get("CONDA_PREFIX"),
            "observation_caller_cwd": os.environ.get(
                "ENVSOLVE_LEDGER_CALLER_CWD"
            ),
            "cwd": os.getcwd(),
            "python_distribution_count": len(distributions),
            "python_distributions_sha256": hashlib.sha256(
                "\0".join(distributions).encode("utf-8")
            ).hexdigest(),
            "python_path_sha256": hashlib.sha256(
                "\0".join(python_path).encode("utf-8")
            ).hexdigest(),
            "path_sha256": hashlib.sha256(
                os.environ.get("PATH", "").encode("utf-8")
            ).hexdigest(),
        },
        ensure_ascii=True,
        sort_keys=True,
    ),
    encoding="utf-8",
)
""".strip()
    lines = [
        "if (",
        "set +e",
        'export ENVSOLVE_LEDGER_CALLER_CWD="$PWD"',
        f"builtin cd -- {shlex.quote(project_root)} || exit 125",
        "rm -f "
        f"{shlex.quote(report_path)} "
        f"{shlex.quote(fingerprint_path)} "
        f"{shlex.quote(projection_path)} "
        f"{shlex.quote(stdout_path)} "
        f"{shlex.quote(stderr_path)}",
        "if (",
        "set -e",
        unset_protected,
        "export ENVSOLVE_PROJECT_ROOT=/data/project",
        f"export ENVSOLVE_GOAL_REPORT={shlex.quote(report_path)}",
        'rm -f "$ENVSOLVE_GOAL_REPORT"',
        contract.program.rstrip(),
        (
            f") >{shlex.quote(stdout_path)} 2>{shlex.quote(stderr_path)}; "
            "then ENVSOLVE_LEDGER_GOAL_RC=0; else ENVSOLVE_LEDGER_GOAL_RC=$?; fi"
        ),
        f"command python - {shlex.quote(fingerprint_path)} <<'ENVSOLVE_LEDGER_FINGERPRINT_PY'",
        fingerprint_program,
        "ENVSOLVE_LEDGER_FINGERPRINT_PY",
        (
            f"command python - {shlex.quote(report_path)} {shlex.quote(fingerprint_path)} "
            f"{shlex.quote(projection_path)} {shlex.quote(stdout_path)} "
            f"{shlex.quote(stderr_path)} \"$ENVSOLVE_LEDGER_GOAL_RC\" "
            f"{shlex.quote(contract.report_schema)} <<'ENVSOLVE_LEDGER_PROJECTION_PY'"
        ),
        projection_program,
        "ENVSOLVE_LEDGER_PROJECTION_PY",
        f"printf '%s\\n' {shlex.quote(begin)}",
        (
            f"command python - {shlex.quote(projection_path)} {shlex.quote(nonce)} "
            "<<'ENVSOLVE_LEDGER_RECEIPT_PY'"
        ),
        receipt_program,
        "ENVSOLVE_LEDGER_RECEIPT_PY",
        f"printf '\\n%s\\n' {shlex.quote(end)}",
        "rm -f "
        f"{shlex.quote(report_path)} "
        f"{shlex.quote(fingerprint_path)} "
        f"{shlex.quote(stdout_path)} "
        f"{shlex.quote(stderr_path)}",
        "true",
        "); then :; else :; fi",
    ]
    return "\n".join(lines)


def _decode_projection(encoded: str) -> dict[str, Any] | None:
    try:
        compressed = base64.b64decode(encoded, validate=True)
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(compressed, _MAX_PROJECTION_BYTES + 1)
        if len(decoded) > _MAX_PROJECTION_BYTES or not decompressor.eof:
            return None
        value = json.loads(decoded)
    except (ValueError, zlib.error, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _extract_projection(output: str, nonce: str) -> dict[str, Any] | None:
    begin = f"ENVSOLVE_COMPATIBILITY_LEDGER_BEGIN_V1={nonce}\n"
    end = f"\nENVSOLVE_COMPATIBILITY_LEDGER_END_V1={nonce}"
    if output.count(begin) != 1 or output.count(end) != 1:
        return None
    encoded = output.split(begin, 1)[1].split(end, 1)[0].strip()
    return _decode_projection(encoded)


def _extract_projection_receipt(
    output: str,
    nonce: str,
) -> tuple[int, str] | None:
    begin = f"ENVSOLVE_COMPATIBILITY_LEDGER_BEGIN_V1={nonce}\n"
    end = f"\nENVSOLVE_COMPATIBILITY_LEDGER_END_V1={nonce}"
    if output.count(begin) != 1 or output.count(end) != 1:
        return None
    payload = output.split(begin, 1)[1].split(end, 1)[0].strip()
    prefix = f"ENVSOLVE_COMPATIBILITY_LEDGER_RECEIPT_V1={nonce}:"
    if not payload.startswith(prefix):
        return None
    fields = payload[len(prefix) :].split(":")
    if len(fields) != 2:
        return None
    try:
        size = int(fields[0])
    except ValueError:
        return None
    digest = fields[1]
    if (
        size <= 0
        or size > _MAX_PROJECTION_TRANSPORT_BYTES
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        return None
    return size, digest


class CompatibilityLedgerService:
    def __init__(
        self,
        contract: ExecutableGoalContract,
        terminal_server: ContainerMcpServer,
        project_root: str = "/data/project",
    ) -> None:
        if not project_root.startswith("/"):
            raise ValueError("Compatibility project root must be absolute")
        self.contract = contract
        self.terminal_server = terminal_server
        self.project_root = project_root
        self.ledger = CompatibilityDeltaLedger(contract.report_schema)

    def _execute_shell(self, call_id: str, command: str) -> dict[str, Any] | None:
        response = self.terminal_server.handle(
            {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {
                    "name": "envbench_shell",
                    "arguments": {"command": command},
                },
            }
        )
        if isinstance(response, dict):
            result = response.get("result")
            if isinstance(result, dict):
                structured = result.get("structuredContent")
                if isinstance(structured, dict):
                    return structured
        return None

    def _read_projection(
        self,
        projection_path: str,
        size: int,
        digest: str,
        call_id: str,
    ) -> dict[str, Any] | None:
        read_program = (
            "from pathlib import Path; import sys; "
            "data=Path(sys.argv[1]).read_text(encoding='ascii'); "
            "start=int(sys.argv[2]); count=int(sys.argv[3]); "
            "sys.stdout.write(data[start:start+count])"
        )
        chunks: list[str] = []
        for index, offset in enumerate(range(0, size, _PROJECTION_CHUNK_CHARS), start=1):
            count = min(_PROJECTION_CHUNK_CHARS, size - offset)
            command = (
                f"command python -c {shlex.quote(read_program)} "
                f"{shlex.quote(projection_path)} {offset} {count}"
            )
            structured = self._execute_shell(f"{call_id}-chunk-{index}", command)
            if (
                not isinstance(structured, dict)
                or structured.get("infrastructure_error") is not None
                or structured.get("timed_out")
                or structured.get("output_truncated")
                or not isinstance(structured.get("output"), str)
            ):
                return None
            chunk = structured["output"]
            if len(chunk) == count + 1 and chunk.endswith("\n"):
                chunk = chunk[:-1]
            if len(chunk) != count:
                return None
            chunks.append(chunk)
        encoded = "".join(chunks)
        if len(encoded) != size:
            return None
        if hashlib.sha256(encoded.encode("ascii")).hexdigest() != digest:
            return None
        return _decode_projection(encoded)

    def check(self, call_id: str) -> dict[str, Any]:
        nonce = uuid.uuid4().hex
        projection_path = f"/tmp/envsolve-ledger-projection-{nonce}.json"
        structured = self._execute_shell(
            call_id,
            _probe_command(self.contract, nonce, self.project_root),
        )
        try:
            if not isinstance(structured, dict):
                return self._unknown("container bridge returned no structured result")
            if structured.get("infrastructure_error") is not None:
                return self._unknown("container bridge infrastructure error", structured)
            if structured.get("timed_out"):
                return self._unknown("compatibility probe timed out", structured)
            output = structured.get("output")
            projection = None
            if isinstance(output, str):
                receipt = _extract_projection_receipt(output, nonce)
                if receipt is not None:
                    projection = self._read_projection(
                        projection_path,
                        receipt[0],
                        receipt[1],
                        call_id,
                    )
                else:
                    projection = _extract_projection(output, nonce)
            if projection is None:
                return self._unknown(
                    "compatibility probe produced no valid projection",
                    structured,
                )
            report = projection.get("report")
            environment = projection.get("environment")
            if not isinstance(report, dict) or not isinstance(environment, dict):
                return self._unknown("compatibility projection is incomplete", structured)
            if projection.get("goal_exit_code") != 0:
                report = {
                    **report,
                    "status": "unknown",
                    "finding_set_complete": False,
                }
            result = self.ledger.observe(report, environment)
            goal_output = projection.get("goal_output")
            if isinstance(goal_output, dict):
                result["goal_output"] = goal_output
            return result
        finally:
            self._execute_shell(
                f"{call_id}-projection-cleanup",
                f"rm -f {shlex.quote(projection_path)}",
            )

    def _unknown(
        self,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.ledger.observe_unknown(reason)
        if evidence is not None:
            result["execution"] = {
                key: evidence.get(key)
                for key in (
                    "exit_code",
                    "duration_seconds",
                    "timed_out",
                    "output_truncated",
                    "infrastructure_error",
                )
            }
        return result

    def metadata(self) -> dict[str, Any]:
        return {
            **self.ledger.metadata(),
            "probe_execution": {
                "scope": "persistent-construction-shell-subshell",
                "filesystem_effects_persist": True,
                "shell_variable_effects_persist": False,
                "goal_instrumentation_may_modify_environment": True,
                "environment_fingerprint_timing": "after-goal-execution",
                "goal_working_directory": self.project_root,
                "caller_working_directory_recorded": True,
                "projection_transport": "zlib-base64-json-chunked-v2",
                "max_projection_bytes": _MAX_PROJECTION_BYTES,
                "max_projection_transport_bytes": _MAX_PROJECTION_TRANSPORT_BYTES,
                "projection_chunk_chars": _PROJECTION_CHUNK_CHARS,
            },
        }


def model_visible_scheduled_observation(
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Project complete machine evidence into a bounded same-session message."""

    result = observation.get("result")
    if not isinstance(result, dict):
        return dict(observation)
    projected_result = dict(result)
    truncated_sections: dict[str, dict[str, int | bool]] = {}

    current = result.get("current")
    if isinstance(current, dict):
        projected_current = dict(current)
        obligations = current.get("obligations")
        if isinstance(obligations, list):
            projected_current["obligations"] = obligations[
                :_MAX_MODEL_VISIBLE_OBLIGATIONS
            ]
            truncated_sections["current"] = {
                "total_count": len(obligations),
                "visible_count": min(
                    len(obligations), _MAX_MODEL_VISIBLE_OBLIGATIONS
                ),
                "truncated": len(obligations) > _MAX_MODEL_VISIBLE_OBLIGATIONS,
            }
        projected_result["current"] = projected_current

    delta = result.get("delta_from_previous")
    if isinstance(delta, dict):
        projected_delta = dict(delta)
        for name in ("resolved", "introduced"):
            obligations = delta.get(name)
            if not isinstance(obligations, list):
                continue
            projected_delta[name] = obligations[:_MAX_MODEL_VISIBLE_OBLIGATIONS]
            truncated_sections[name] = {
                "total_count": len(obligations),
                "visible_count": min(
                    len(obligations), _MAX_MODEL_VISIBLE_OBLIGATIONS
                ),
                "truncated": len(obligations) > _MAX_MODEL_VISIBLE_OBLIGATIONS,
            }
        projected_result["delta_from_previous"] = projected_delta

    projected_result["model_projection"] = {
        "complete_machine_evidence_retained_in_trajectory": True,
        "max_visible_obligations_per_section": _MAX_MODEL_VISIBLE_OBLIGATIONS,
        "sections": truncated_sections,
    }
    projected = {
        key: value for key, value in observation.items() if key != "result"
    }
    projected["result"] = projected_result
    return projected


class ScheduledCompatibilityObserver:
    """Apply a fixed observation dose without constraining Agent operations."""

    def __init__(
        self,
        service: CompatibilityLedgerService,
        cadence: int = DEFAULT_SHELL_OBSERVATION_CADENCE,
    ) -> None:
        if cadence <= 0:
            raise ValueError("Scheduled observation cadence must be positive")
        self.service = service
        self.cadence = cadence
        self.shell_operations_completed = 0
        self.replay_requests = 0
        self.pre_replay_observations_required = 0
        self.construction_dirty = False
        self.trigger_counts: Counter[str] = Counter()
        self.observations: list[dict[str, Any]] = []

    def _observe(self, trigger: str) -> dict[str, Any]:
        observation_number = len(self.observations) + 1
        result = self.service.check(f"scheduled-{trigger}-{observation_number}")
        record = {
            "schema": SCHEDULED_OBSERVATION_SCHEMA,
            "observation_number": observation_number,
            "trigger": trigger,
            "shell_operations_completed": self.shell_operations_completed,
            "advisory_only": True,
            "operation_constraints_added": False,
            "feedback_delivery": "same-active-model-session",
            "result": result,
        }
        self.trigger_counts[trigger] += 1
        self.observations.append(record)
        self.construction_dirty = False
        return record

    def observe_initial(self) -> dict[str, Any]:
        if self.trigger_counts["initial"]:
            raise RuntimeError("Initial compatibility observation already executed")
        return self._observe("initial")

    def after_shell_operation(self) -> dict[str, Any] | None:
        self.shell_operations_completed += 1
        self.construction_dirty = True
        if self.shell_operations_completed % self.cadence == 0:
            return self._observe("periodic")
        return None

    def before_replay(self) -> dict[str, Any] | None:
        self.replay_requests += 1
        if not self.construction_dirty:
            return None
        self.pre_replay_observations_required += 1
        return self._observe("pre-replay-dirty")

    def metadata(self) -> dict[str, Any]:
        ledger = self.service.metadata()
        observation_count = int(ledger["observation_count"])
        complete_count = int(ledger["complete_observation_count"])
        expected_periodic = self.shell_operations_completed // self.cadence
        schedule_compliant = (
            self.trigger_counts["initial"] == 1
            and self.trigger_counts["periodic"] == expected_periodic
            and self.trigger_counts["pre-replay-dirty"]
            == self.pre_replay_observations_required
            and observation_count == len(self.observations)
        )
        return {
            "schema": SCHEDULED_OBSERVATION_SCHEMA,
            "cadence_shell_operations": self.cadence,
            "shell_operations_completed": self.shell_operations_completed,
            "replay_requests": self.replay_requests,
            "trigger_counts": dict(sorted(self.trigger_counts.items())),
            "expected_periodic_observation_count": expected_periodic,
            "pre_replay_observations_required": self.pre_replay_observations_required,
            "observation_count": observation_count,
            "complete_observation_count": complete_count,
            "complete_observation_rate": (
                complete_count / observation_count if observation_count else None
            ),
            "schedule_compliant": schedule_compliant,
            "feedback_delivery": "same-active-model-session",
            "optional_compatibility_tool_exposed": False,
            "operation_constraints_added": False,
            "stores_container_checkpoint": False,
            "observation_summaries": [
                {
                    "observation_number": item["observation_number"],
                    "trigger": item["trigger"],
                    "shell_operations_completed": item["shell_operations_completed"],
                    "ok": item["result"].get("ok"),
                    "finding_set_complete": item["result"].get(
                        "finding_set_complete"
                    ),
                    "goal_status": item["result"].get("goal_status"),
                    "candidate_ready": item["result"].get("candidate_ready"),
                    "obligation_count": item["result"].get("current", {}).get(
                        "obligation_count"
                    ),
                    "transition": item["result"].get(
                        "delta_from_previous", {}
                    ).get("classification"),
                }
                for item in self.observations
            ],
        }
