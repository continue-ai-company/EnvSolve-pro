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
_MAX_PROJECTION_BYTES = 2_000_000


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
                "best_anchor": best.summary(include_obligations=True),
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


def _probe_command(contract: ExecutableGoalContract, nonce: str) -> str:
    report_path = f"/tmp/envsolve-ledger-report-{nonce}.json"
    fingerprint_path = f"/tmp/envsolve-ledger-environment-{nonce}.json"
    projection_path = f"/tmp/envsolve-ledger-projection-{nonce}.json"
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
import json
import os
from pathlib import Path
import sys
import zlib

report_path, fingerprint_path, projection_path = map(Path, sys.argv[1:4])
goal_exit_code = int(sys.argv[4])
report_schema = sys.argv[5]
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
        "rm -f "
        f"{shlex.quote(report_path)} "
        f"{shlex.quote(fingerprint_path)} "
        f"{shlex.quote(projection_path)}",
        "if (",
        "set -e",
        unset_protected,
        "export ENVSOLVE_PROJECT_ROOT=/data/project",
        f"export ENVSOLVE_GOAL_REPORT={shlex.quote(report_path)}",
        'rm -f "$ENVSOLVE_GOAL_REPORT"',
        contract.program.rstrip(),
        "); then ENVSOLVE_LEDGER_GOAL_RC=0; else ENVSOLVE_LEDGER_GOAL_RC=$?; fi",
        f"command python - {shlex.quote(fingerprint_path)} <<'ENVSOLVE_LEDGER_FINGERPRINT_PY'",
        fingerprint_program,
        "ENVSOLVE_LEDGER_FINGERPRINT_PY",
        (
            f"command python - {shlex.quote(report_path)} {shlex.quote(fingerprint_path)} "
            f"{shlex.quote(projection_path)} \"$ENVSOLVE_LEDGER_GOAL_RC\" "
            f"{shlex.quote(contract.report_schema)} <<'ENVSOLVE_LEDGER_PROJECTION_PY'"
        ),
        projection_program,
        "ENVSOLVE_LEDGER_PROJECTION_PY",
        f"printf '%s\\n' {shlex.quote(begin)}",
        f"cat {shlex.quote(projection_path)} 2>/dev/null || true",
        f"printf '\\n%s\\n' {shlex.quote(end)}",
        "rm -f "
        f"{shlex.quote(report_path)} "
        f"{shlex.quote(fingerprint_path)} "
        f"{shlex.quote(projection_path)}",
        "true",
        "); then :; else :; fi",
    ]
    return "\n".join(lines)


def _extract_projection(output: str, nonce: str) -> dict[str, Any] | None:
    begin = f"ENVSOLVE_COMPATIBILITY_LEDGER_BEGIN_V1={nonce}\n"
    end = f"\nENVSOLVE_COMPATIBILITY_LEDGER_END_V1={nonce}"
    if output.count(begin) != 1 or output.count(end) != 1:
        return None
    encoded = output.split(begin, 1)[1].split(end, 1)[0].strip()
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


class CompatibilityLedgerService:
    def __init__(
        self,
        contract: ExecutableGoalContract,
        terminal_server: ContainerMcpServer,
    ) -> None:
        self.contract = contract
        self.terminal_server = terminal_server
        self.ledger = CompatibilityDeltaLedger(contract.report_schema)

    def check(self, call_id: str) -> dict[str, Any]:
        nonce = uuid.uuid4().hex
        response = self.terminal_server.handle(
            {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {
                    "name": "envbench_shell",
                    "arguments": {"command": _probe_command(self.contract, nonce)},
                },
            }
        )
        structured = None
        if isinstance(response, dict):
            result = response.get("result")
            if isinstance(result, dict):
                structured = result.get("structuredContent")
        if not isinstance(structured, dict):
            return self._unknown("container bridge returned no structured result")
        if structured.get("infrastructure_error") is not None:
            return self._unknown("container bridge infrastructure error", structured)
        if structured.get("timed_out"):
            return self._unknown("compatibility probe timed out", structured)
        output = structured.get("output")
        projection = _extract_projection(output, nonce) if isinstance(output, str) else None
        if projection is None:
            return self._unknown("compatibility probe produced no valid projection", structured)
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
        return self.ledger.observe(report, environment)

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
                "projection_transport": "zlib-base64-json-v1",
                "max_projection_bytes": _MAX_PROJECTION_BYTES,
            },
        }
