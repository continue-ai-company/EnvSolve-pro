from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.execution.heartbeat import analyze_heartbeat_records
from envsolve_harness.utils.provenance import sha256_file


@dataclass
class EligibilityReport:
    eligible: bool = True
    classification: str = "scientifically_eligible"
    exclusion_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def exclude(self, code: str, message: str) -> None:
        self.eligible = False
        self.classification = "scientifically_ineligible"
        self.exclusion_reasons.append(f"{code}: {message}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PRIMITIVE_BUDGETS = (
    ("max_model_requests", "requests_started", "model_requests"),
    ("max_total_tokens", "total_tokens", "total_tokens"),
    ("max_candidates", "candidates", "candidates"),
    ("max_environments", "environments", "environments"),
    ("max_commands", "commands", "commands"),
    ("max_wall_clock_seconds", "elapsed_wall_clock_seconds", "wall_clock_seconds"),
)


def _check_budget(report: EligibilityReport, ledger: dict[str, Any]) -> None:
    limits = ledger.get("limits") or {}
    usage = ledger.get("usage") or {}
    exhausted = set(ledger.get("exhausted_limits") or [])
    for limit_key, usage_key, scope in _PRIMITIVE_BUDGETS:
        if limit_key not in limits:
            continue
        observed = usage.get(usage_key)
        limit = limits[limit_key]
        valid_number = isinstance(observed, (int, float)) and isinstance(limit, (int, float))
        report.checks[f"budget_{scope}_recorded"] = valid_number
        if not valid_number:
            report.exclude("budget_schema", f"{scope} usage or limit is not numeric")
            continue
        tolerance = 1.0 if scope == "wall_clock_seconds" else 0.0
        within = float(observed) <= float(limit) + tolerance
        report.checks[f"budget_{scope}_within_limit"] = within
        if not within:
            report.exclude(
                "budget_overrun",
                f"{scope} observed {observed} exceeds frozen limit {limit}",
            )

    termination = ledger.get("termination")
    if isinstance(termination, dict) and termination.get("kind") == "budget_exhausted":
        scope = termination.get("scope")
        consistent = isinstance(scope, str) and scope in exhausted
        report.checks["budget_termination_consistent"] = consistent
        if not consistent:
            report.exclude(
                "budget_terminal_mismatch",
                "budget termination scope is absent from exhausted_limits",
            )


def assess_scientific_eligibility(run_root: Path) -> EligibilityReport:
    root = run_root.resolve()
    report = EligibilityReport()
    integrity = audit_run(root)
    report.checks["artifact_integrity_valid"] = integrity.valid
    if not integrity.valid:
        report.exclude("artifact_invalid", "; ".join(integrity.errors))
        return report

    manifest = read_json(root / "manifest.json")
    harness = manifest.get("harness") or {}
    committed = isinstance(harness.get("revision"), str) and bool(harness.get("revision"))
    clean = harness.get("dirty") is False
    report.checks["committed_source"] = committed
    report.checks["clean_source"] = clean
    if not committed or not clean:
        report.exclude(
            "unfrozen_source",
            "run was produced without a committed, clean harness revision",
        )

    ledger_path = root / "generation" / "budget_ledger.json"
    if ledger_path.is_file():
        _check_budget(report, read_json(ledger_path))

    monitor = manifest.get("runtime_monitor")
    if isinstance(monitor, dict) and monitor.get("required") is True:
        relative = Path(str(monitor.get("path", "")))
        heartbeat_path = root / relative
        try:
            heartbeat_path.resolve().relative_to(root)
            portable = bool(relative.parts) and not relative.is_absolute()
        except ValueError:
            portable = False
        exists = portable and heartbeat_path.is_file()
        report.checks["runtime_heartbeat_portable"] = portable
        report.checks["runtime_heartbeat_exists"] = exists
        if not exists:
            report.exclude("runtime_monitor_missing", "required heartbeat artifact is missing")
        else:
            expected_hash = monitor.get("sha256")
            hash_valid = isinstance(expected_hash, str) and sha256_file(heartbeat_path) == expected_hash
            report.checks["runtime_heartbeat_hash"] = hash_valid
            if not hash_valid:
                report.exclude("runtime_monitor_unfinalized", "heartbeat hash is absent or invalid")
            threshold = float(monitor.get("suspend_gap_seconds", 30.0))
            analysis = analyze_heartbeat_records(read_jsonl(heartbeat_path), threshold)
            report.checks["runtime_heartbeat_complete"] = analysis.complete
            report.checks["runtime_heartbeat_sequence"] = analysis.sequence_valid
            report.checks["host_suspension_absent"] = not analysis.suspend_suspected
            if not analysis.complete or not analysis.sequence_valid:
                report.exclude("runtime_monitor_incomplete", "heartbeat lifecycle is incomplete")
            if analysis.suspend_suspected:
                largest = max(analysis.suspicious_gaps)
                report.exclude(
                    "host_suspension_suspected",
                    f"heartbeat gap {largest:.3f}s exceeds threshold {threshold:.3f}s",
                )

    return report
