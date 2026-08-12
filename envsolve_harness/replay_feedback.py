from __future__ import annotations

import json
from typing import Any


SOFT_REPLAY_FEEDBACK_SCHEMA = "envsolve-pro-soft-replay-feedback-v1"


def _decode_bounded_json(value: Any) -> Any:
    if not isinstance(value, dict) or not isinstance(value.get("json"), str):
        return None
    try:
        return json.loads(value["json"])
    except json.JSONDecodeError:
        return None


def _bounded_text(value: Any, limit: int) -> tuple[str, bool]:
    text = str(value or "")
    if len(text) <= limit:
        return text, False
    half = max(1, limit // 2)
    return (
        text[:half]
        + f"\n... {len(text) - 2 * half} characters omitted ...\n"
        + text[-half:],
        True,
    )


def _first_finding(details: Any) -> dict[str, Any] | None:
    if not isinstance(details, dict):
        return None
    candidates = [details]
    while candidates:
        current = candidates.pop(0)
        findings = current.get("findings")
        if isinstance(findings, list):
            for item in findings:
                if isinstance(item, dict) and item.get("observed") != item.get("required"):
                    return item
        for value in current.values():
            if isinstance(value, dict):
                candidates.append(value)
    return None


def _constraint_fields(
    replay: dict[str, Any],
    phase: str,
    verification: dict[str, Any],
) -> tuple[Any, Any, dict[str, Any]]:
    validation = replay.get("candidate_validation")
    if phase == "candidate-validation" and isinstance(validation, dict):
        return (
            "candidate must satisfy the minimal evaluator-integrity contract",
            validation.get("reason") or validation.get("details"),
            {"source": "candidate-validation", "policy_id": validation.get("policy_id")},
        )

    counterexamples = _decode_bounded_json(verification.get("counterexamples"))
    if isinstance(counterexamples, list) and counterexamples:
        item = counterexamples[0]
        if isinstance(item, dict):
            value = item.get("value")
            if isinstance(value, dict):
                required = value.get("required", value.get("expected", item.get("kind")))
                observed = value.get("observed", value)
            else:
                required = item.get("kind")
                observed = value
            return required, observed, {
                "source": "structured-counterexample",
                "kind": item.get("kind"),
                "confidence": item.get("confidence"),
            }

    details = _decode_bounded_json(verification.get("details"))
    finding = _first_finding(details)
    if finding is not None:
        return (
            finding.get("required"),
            finding.get("observed"),
            {
                "source": "goal-finding",
                "finding_id": finding.get("finding_id"),
                "domain": finding.get("domain"),
                "predicate": finding.get("predicate"),
            },
        )

    bootstrap = verification.get("bootstrap")
    if isinstance(bootstrap, dict) and bootstrap.get("exit_code") not in (None, 0):
        return (
            "bootstrap program and trusted public goal must exit successfully",
            {
                "exit_code": bootstrap.get("exit_code"),
                "stderr": bootstrap.get("stderr"),
            },
            {"source": "bootstrap-execution"},
        )
    return (
        "trusted public executable goal must pass in a fresh environment",
        verification.get("summary") or replay.get("status"),
        {"source": "verification-summary"},
    )


def normalize_replay_feedback(
    replay: dict[str, Any],
    *,
    raw_text_limit: int = 6_000,
) -> dict[str, Any]:
    """Expose one advisory constraint plus bounded evidence from a clean replay."""

    if raw_text_limit <= 0:
        raise ValueError("Replay feedback text bound must be positive")
    status = str(replay.get("status", "unknown"))
    raw_phase = str(replay.get("phase", "unknown"))
    verification = replay.get("verification")
    if not isinstance(verification, dict):
        verification = {}
    bootstrap = verification.get("bootstrap")
    if not isinstance(bootstrap, dict):
        bootstrap = {}

    if raw_phase == "candidate-validation":
        phase = "candidate-validation"
    elif status == "infrastructure_error":
        phase = "infrastructure"
    elif bootstrap.get("exit_code") not in (None, 0):
        phase = "bootstrap-execution"
    else:
        phase = "goal-verification"

    required, observed, provenance = _constraint_fields(
        replay,
        raw_phase,
        verification,
    )
    stdout, stdout_truncated = _bounded_text(bootstrap.get("stdout"), raw_text_limit)
    stderr, stderr_truncated = _bounded_text(bootstrap.get("stderr"), raw_text_limit)
    receipt = replay.get("environment_receipt")
    if not isinstance(receipt, dict):
        receipt = None

    return {
        "schema": SOFT_REPLAY_FEEDBACK_SCHEMA,
        "advisory_only": True,
        "status": status,
        "phase": phase,
        "soft_constraint": {
            "required_condition": required,
            "observed_state": observed,
            "provenance": provenance,
        },
        "retryability": (
            "exact_infrastructure_retry"
            if status == "infrastructure_error"
            else "none"
            if status == "pass"
            else "agent_repair"
        ),
        "environment_identity": (
            {
                key: receipt.get(key)
                for key in (
                    "environment_id",
                    "provider_id",
                    "image_digest",
                    "repository",
                    "revision",
                )
            }
            if receipt is not None
            else None
        ),
        "raw_evidence": {
            "replay_id": replay.get("replay_id"),
            "program_sha256": replay.get("program_sha256"),
            "candidate_validation": replay.get("candidate_validation"),
            "verification_summary": verification.get("summary"),
            "bootstrap": {
                "exit_code": bootstrap.get("exit_code"),
                "duration_seconds": bootstrap.get("duration_seconds"),
                "stdout": stdout,
                "stdout_truncated": bool(
                    stdout_truncated or bootstrap.get("stdout_truncated")
                ),
                "stderr": stderr,
                "stderr_truncated": bool(
                    stderr_truncated or bootstrap.get("stderr_truncated")
                ),
            },
            "counterexamples": _decode_bounded_json(
                verification.get("counterexamples")
            ),
            "infrastructure_error": replay.get("infrastructure_error"),
            "release_error": replay.get("release_error"),
            "certificate": replay.get("certificate"),
        },
    }
