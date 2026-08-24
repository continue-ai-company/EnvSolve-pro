from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from envsolve_harness.core.io import read_json
from envsolve_harness.adapters.infrastructure import (
    envbench_evaluation_infrastructure_signature,
)
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.utils.provenance import sha256_file


@dataclass
class AuditReport:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _official_primary_advisory_submission_valid(
    solver_metadata: dict[str, Any], manifest: dict[str, Any]
) -> bool:
    if (
        solver_metadata.get("runner")
        != "codex-cli-boundary-v5-official-primary-remote-docker"
    ):
        return False
    primary = solver_metadata.get("official_primary_submission")
    candidate = solver_metadata.get("candidate_validation")
    construction = solver_metadata.get("construction_workspace_integrity")
    qualification = solver_metadata.get("submission_qualification")
    integrity = solver_metadata.get("repository_integrity")
    script = manifest.get("script")
    if not all(
        isinstance(item, dict)
        for item in (
            primary,
            candidate,
            construction,
            qualification,
            integrity,
            script,
        )
    ):
        return False
    violations = integrity.get("violations")
    return (
        primary.get("eligible") is True
        and primary.get("qualification_is_advisory") is True
        and primary.get("qualification_feedback_returned_to_agent") is False
        and primary.get("program_sha256") == script.get("sha256")
        and candidate.get("accepted") is True
        and (candidate.get("details") or {}).get(
            "protected_configuration_history"
        )
        == "no-write-observed"
        and construction.get("valid") is True
        and qualification.get("certified") is False
        and qualification.get("status") == "fail"
        and qualification.get("feedback_returned_to_agent") is False
        and integrity.get("valid") is False
        and isinstance(violations, list)
        and len(violations) == 1
        and isinstance(violations[0], dict)
        and violations[0].get("kind")
        == "submitted_program_qualification_failed"
    )


def audit_run(run_root: Path) -> AuditReport:
    root = run_root.resolve()
    report = AuditReport()
    always_required = {
        "manifest": root / "manifest.json",
        "status": root / "status.json",
        "case": root / "inputs" / "case.json",
    }
    for name, path in always_required.items():
        exists = path.is_file()
        report.checks[f"{name}_exists"] = exists
        if not exists:
            report.error(f"Missing required artifact: {path.relative_to(root)}")
    if not report.valid:
        return report

    try:
        manifest = read_json(always_required["manifest"])
        status = read_json(always_required["status"])
        case = read_json(always_required["case"])
    except (OSError, ValueError, TypeError) as exc:
        report.error(f"Unable to parse run artifacts: {type(exc).__name__}: {exc}")
        return report

    required_manifest_fields = {
        "protocol", "run", "case", "host", "harness", "solver", "script", "evaluator", "result"
    }
    missing_fields = required_manifest_fields - manifest.keys()
    report.checks["manifest_schema"] = not missing_fields
    if missing_fields:
        report.error(f"Manifest is missing fields: {sorted(missing_fields)}")
        return report

    report.checks["case_matches_manifest"] = case == manifest["case"]
    if not report.checks["case_matches_manifest"]:
        report.error("inputs/case.json does not match manifest case")

    runtime_monitor = manifest.get("runtime_monitor")
    if isinstance(runtime_monitor, dict) and runtime_monitor.get("state") == "completed":
        relative_heartbeat = Path(str(runtime_monitor.get("path", "")))
        heartbeat_path = root / relative_heartbeat
        heartbeat_portable = (
            bool(relative_heartbeat.parts)
            and not relative_heartbeat.is_absolute()
            and _inside(root, heartbeat_path)
        )
        report.checks["runtime_heartbeat_portable"] = heartbeat_portable
        heartbeat_exists = heartbeat_portable and heartbeat_path.is_file()
        report.checks["runtime_heartbeat_exists"] = heartbeat_exists
        heartbeat_hash = (
            heartbeat_exists
            and isinstance(runtime_monitor.get("sha256"), str)
            and sha256_file(heartbeat_path) == runtime_monitor.get("sha256")
        )
        report.checks["runtime_heartbeat_hash"] = bool(heartbeat_hash)
        if not heartbeat_portable:
            report.error("Runtime heartbeat path is absolute or escapes the run directory")
        elif not heartbeat_exists:
            report.error("Completed runtime monitor heartbeat is missing")
        elif not heartbeat_hash:
            report.error("Runtime heartbeat SHA256 does not match manifest")

    solver = manifest.get("solver")
    solver_metadata = solver.get("metadata", {}) if isinstance(solver, dict) else {}
    audit_requirements = solver_metadata.get("audit_requirements", {})
    if not isinstance(audit_requirements, dict):
        audit_requirements = {}
    requires_repository_integrity = audit_requirements.get("repository_integrity") is True
    if requires_repository_integrity and solver.get("generation_completed") is True:
        integrity = solver_metadata.get("repository_integrity")
        integrity_valid = isinstance(integrity, dict) and integrity.get("valid") is True
        report.checks["repository_integrity"] = integrity_valid
        advisory_valid = _official_primary_advisory_submission_valid(
            solver_metadata, manifest
        )
        report.checks["official_primary_advisory_submission"] = advisory_valid
        if not integrity_valid and not advisory_valid:
            report.error("Successful solver result lacks a valid repository integrity report")

    if audit_requirements.get("evaluation_retry") is True:
        retry_path = root / "inputs" / "evaluation_retry.json"
        raw_source_path = root / "inputs" / "source_raw_result.json"
        retry_files_exist = retry_path.is_file() and raw_source_path.is_file()
        report.checks["evaluation_retry_inputs_exist"] = retry_files_exist
        if not retry_files_exist:
            report.error("Evaluation retry lacks frozen source evidence")
        else:
            try:
                retry = read_json(retry_path)
                source_raw = read_json(raw_source_path)
            except (OSError, TypeError, ValueError) as exc:
                report.error(
                    f"Unable to parse evaluation retry evidence: {type(exc).__name__}: {exc}"
                )
            else:
                retry_matches = retry == solver_metadata.get("evaluation_retry")
                report.checks["evaluation_retry_metadata_matches"] = retry_matches
                if not retry_matches:
                    report.error("Evaluation retry metadata does not match its input record")
                signature = envbench_evaluation_infrastructure_signature(source_raw)
                eligible = (
                    retry.get("policy") == "single-exact-script-infrastructure-retry-v1"
                    and retry.get("max_retries") == 1
                    and retry.get("model_reexecuted") is False
                    and signature is not None
                    and retry.get("infrastructure_signature") == signature
                )
                report.checks["evaluation_retry_eligible"] = eligible
                if not eligible:
                    report.error("Evaluation retry does not satisfy the frozen eligibility rule")

    budget_path = root / "generation" / "budget_ledger.json"
    recorded_budget = solver_metadata.get("online_budget")
    has_online_budget_evidence = budget_path.is_file() or isinstance(
        recorded_budget, dict
    )
    requires_online_budget = (
        audit_requirements.get("online_budget") is True
        and (
            solver.get("generation_completed") is True
            or has_online_budget_evidence
        )
    )
    if requires_online_budget:
        budget_exists = budget_path.is_file()
        report.checks["online_budget_exists"] = budget_exists
        if not budget_exists:
            report.error("Solver result lacks a required online budget ledger")
        else:
            try:
                persisted_budget = read_json(budget_path)
            except (OSError, TypeError, ValueError) as exc:
                report.error(f"Unable to parse online budget ledger: {type(exc).__name__}: {exc}")
            else:
                budget_matches = persisted_budget == recorded_budget
                report.checks["online_budget_matches_solver"] = budget_matches
                if not budget_matches:
                    report.error("Online budget ledger does not match solver metadata")
                manifest_budget = manifest.get("resource_budget") or {}
                limits = persisted_budget.get("limits") or {}
                expected_limits = {
                    "max_model_requests": manifest_budget.get("model_max_requests"),
                    "max_total_tokens": manifest_budget.get("model_max_total_tokens"),
                    "max_estimated_cost_usd": manifest_budget.get(
                        "model_max_estimated_cost_usd"
                    ),
                }
                optional_limits = {
                    "max_candidates": manifest_budget.get("envsolve_max_candidates"),
                    "max_environments": manifest_budget.get(
                        "envsolve_max_environments",
                        manifest_budget.get("envsolve_max_candidates"),
                    ),
                    "max_commands": manifest_budget.get(
                        "envsolve_max_commands",
                        manifest_budget.get("envsolve_max_candidates"),
                    ),
                    "max_wall_clock_seconds": manifest_budget.get(
                        "generation_wall_clock_seconds"
                    ),
                }
                expected_limits.update(
                    {
                        key: value
                        for key, value in optional_limits.items()
                        if key in limits
                    }
                )
                limits_match = limits == expected_limits
                report.checks["online_budget_limits_match_manifest"] = limits_match
                if not limits_match:
                    report.error("Online budget limits do not match the run manifest")
                pricing_match = persisted_budget.get("pricing") == manifest_budget.get(
                    "model_pricing"
                )
                report.checks["online_budget_pricing_matches_manifest"] = pricing_match
                if not pricing_match:
                    report.error("Online budget pricing does not match the run manifest")
                launcher = solver_metadata.get("launcher")
                envsolve_model_backed = (
                    (
                        isinstance(launcher, dict)
                        and launcher.get("runner") == "envsolve-p6"
                    )
                    or solver_metadata.get("runner") in {
                        "envsolve-p6",
                        "envsolve-episode",
                    }
                )
                if envsolve_model_backed:
                    usage = persisted_budget.get("usage") or {}
                    provider_attempts = persisted_budget.get(
                        "provider_attempts"
                    )
                    attempt_trace_required = (
                        persisted_budget.get("schema_version") == "1.1.0"
                    )
                    attempt_trace_valid = (
                        isinstance(provider_attempts, list)
                        and len(provider_attempts)
                        >= int(usage.get("requests_started", 0))
                    )
                    report.checks["provider_attempt_trace_valid"] = (
                        attempt_trace_valid
                        if attempt_trace_required
                        else True
                    )
                    if attempt_trace_required and not attempt_trace_valid:
                        report.error(
                            "Model-backed EnvSolve run lacks a complete provider "
                            "attempt trace"
                        )
                    in_progress_attempts = (
                        sum(
                            isinstance(item, dict)
                            and item.get("outcome") == "in_progress"
                            for item in provider_attempts
                        )
                        if isinstance(provider_attempts, list)
                        else 0
                    )
                    completed_or_failed_attempt = (
                        int(usage.get("responses_completed", 0))
                        + int(usage.get("request_errors", 0))
                    ) >= 1
                    model_usage_present = (
                        int(usage.get("requests_started", 0)) >= 1
                        and (
                            completed_or_failed_attempt
                            or in_progress_attempts >= 1
                        )
                        and (
                            solver.get("generation_completed") is not True
                            or (
                                int(usage.get("responses_completed", 0)) >= 1
                                and int(usage.get("total_tokens", 0)) > 0
                            )
                        )
                    )
                    report.checks["envsolve_model_usage_present"] = model_usage_present
                    if not model_usage_present:
                        report.error(
                            "Model-backed EnvSolve run has no auditable model usage"
                        )
                    requires_finalized_budget = (
                        solver.get("generation_completed") is True
                    )
                    if requires_finalized_budget:
                        finalized = isinstance(
                            persisted_budget.get("finalized_at"), str
                        )
                        report.checks["online_budget_finalized"] = finalized
                        if not finalized:
                            report.error("EnvSolve episode budget ledger is not finalized")

    if manifest["result"] is None:
        recorded_interruption = (
            status.get("state") == "interrupted"
            and isinstance(status.get("reason"), str)
            and bool(status["reason"])
            and isinstance(status.get("cleaned_container_ids"), list)
            and isinstance(status.get("updated_at"), str)
        )
        report.checks["interruption_recorded"] = recorded_interruption
        if recorded_interruption:
            return report
        recorded_solver_failure = (
            isinstance(solver, dict)
            and solver.get("generation_completed") is False
            and status.get("state") == "failed"
        )
        report.checks["solver_failure_recorded"] = recorded_solver_failure
        if not recorded_solver_failure:
            report.error("Run has no evaluation result and is not a recorded solver failure")
        return report

    if manifest.get("schema_version") == "0.6.0":
        claim_path = root / "evaluation" / "official_attempt.json"
        claim_exists = claim_path.is_file()
        report.checks["official_evaluation_claim_exists"] = claim_exists
        if not claim_exists:
            report.error("Completed run lacks an atomic official evaluation claim")
        else:
            try:
                claim = read_json(claim_path)
            except (OSError, ValueError, TypeError) as exc:
                report.error(
                    f"Unable to parse official evaluation claim: {type(exc).__name__}: {exc}"
                )
            else:
                claim_valid = (
                    claim.get("channel") == "official"
                    and claim.get("benchmark") == manifest["protocol"].get("benchmark")
                    and claim.get("run_id") == manifest["run"].get("run_id")
                    and claim.get("case_id") == case.get("case_id")
                    and isinstance(claim.get("claimed_at"), str)
                )
                report.checks["official_evaluation_claim_matches"] = claim_valid
                if not claim_valid:
                    report.error("Official evaluation claim does not match the run")

    result_path = root / "evaluation" / "result.json"
    script_path = root / "scripts" / "bootstrap.sh"
    for name, path in {"result": result_path, "script": script_path}.items():
        exists = path.is_file()
        report.checks[f"{name}_exists"] = exists
        if not exists:
            report.error(f"Missing required artifact: {path.relative_to(root)}")
    if not report.valid:
        return report

    try:
        result = read_json(result_path)
    except (OSError, ValueError, TypeError) as exc:
        report.error(f"Unable to parse evaluation result: {type(exc).__name__}: {exc}")
        return report

    report.checks["result_matches_manifest"] = result == manifest["result"]
    if not report.checks["result_matches_manifest"]:
        report.error("evaluation/result.json does not match manifest result")

    expected_script_hash = manifest["script"].get("sha256")
    actual_script_hash = sha256_file(script_path)
    report.checks["script_hash"] = actual_script_hash == expected_script_hash
    if not report.checks["script_hash"]:
        report.error("Bootstrap script SHA256 does not match manifest")
    if audit_requirements.get("evaluation_retry") is True:
        retry = solver_metadata.get("evaluation_retry") or {}
        exact_retry_script = actual_script_hash == retry.get("source_script_sha256")
        report.checks["evaluation_retry_exact_script"] = exact_retry_script
        if not exact_retry_script:
            report.error("Evaluation retry did not use the exact frozen source script")

    expected_state = "completed" if result.get("evaluation_completed") else "failed"
    report.checks["lifecycle_state"] = status.get("state") == expected_state
    if not report.checks["lifecycle_state"]:
        report.error(f"Lifecycle state is {status.get('state')!r}; expected {expected_state!r}")

    raw_result_path = result.get("raw_result_path")
    if raw_result_path:
        relative_raw = Path(raw_result_path)
        raw_path = root / relative_raw
        portable = not relative_raw.is_absolute() and _inside(root, raw_path)
        report.checks["raw_result_path_portable"] = portable
        report.checks["raw_result_exists"] = portable and raw_path.is_file()
        if not portable:
            report.error("Raw result path is absolute or escapes the run directory")
        elif not raw_path.is_file():
            report.error(f"Raw result is missing: {raw_result_path}")
    elif result.get("evaluation_completed"):
        report.error("Completed evaluation does not reference a raw result")

    try:
        protocol = ExperimentProtocol.from_dict(manifest["protocol"])
    except (KeyError, TypeError, ValueError) as exc:
        report.error(f"Unable to validate protocol: {type(exc).__name__}: {exc}")
        return report
    metrics = result.get("raw_metrics")
    metrics_valid = isinstance(metrics, dict)
    report.checks["raw_metrics_schema"] = metrics_valid
    if not metrics_valid:
        report.error("Evaluation result raw_metrics must be an object")
        metrics = {}
    report.checks["benchmark_matches_protocol"] = result.get("benchmark") == protocol.benchmark
    if not report.checks["benchmark_matches_protocol"]:
        report.error("Evaluation benchmark does not match the protocol")
    report.checks["result_case_identity"] = result.get("case_id") == case.get("case_id")
    if not report.checks["result_case_identity"]:
        report.error("Evaluation result case_id does not match the case artifact")

    evidence = result.get("evidence")
    official_evidence = (
        [item for item in evidence if isinstance(item, dict) and item.get("channel") == "official"]
        if isinstance(evidence, list)
        else []
    )
    evidence_valid = bool(official_evidence) if result.get("evaluation_completed") else isinstance(evidence, list)
    report.checks["official_evidence"] = evidence_valid
    if not evidence_valid:
        report.error("Evaluation result lacks official verification evidence")
    report.checks["official_evidence_unique"] = len(official_evidence) == 1
    if len(official_evidence) != 1:
        report.error("Evaluation result must contain exactly one official evidence record")

    diagnostic_evidence = (
        [
            item
            for item in evidence
            if isinstance(item, dict) and item.get("channel") == "diagnostic"
        ]
        if isinstance(evidence, list)
        else []
    )
    diagnostics_valid = all(
        isinstance(item.get("verifier_id"), str)
        and isinstance(item.get("summary"), str)
        and isinstance(item.get("metrics"), dict)
        and (item.get("passed") is None or isinstance(item.get("passed"), bool))
        for item in diagnostic_evidence
    )
    report.checks["diagnostic_evidence_schema"] = diagnostics_valid
    if not diagnostics_valid:
        report.error("Diagnostic evidence has an invalid schema")

    recomputed_pass = (
        result.get("evaluation_completed") is True
        and metrics_valid
        and protocol.is_official_pass(metrics)
    )
    report.checks["official_pass_recomputed"] = result.get("official_pass") == recomputed_pass
    if not report.checks["official_pass_recomputed"]:
        report.error("Official pass does not match the generic protocol criteria")

    return report
