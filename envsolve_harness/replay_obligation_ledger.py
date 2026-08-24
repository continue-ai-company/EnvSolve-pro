from __future__ import annotations

import json
from typing import Any

from envsolve.solver import ExecutableVerification
from envsolve_harness.codex.minimal_b_mcp import CleanReplayService


REPLAY_OBLIGATION_SNAPSHOT_SCHEMA = "envsolve-replay-obligation-snapshot-v1"
REPLAY_OBLIGATION_LEDGER_SCHEMA = "envsolve-replay-obligation-ledger-v1"
_MODEL_VISIBLE_OBLIGATIONS = 128


class ObligationSnapshotCleanReplayService(CleanReplayService):
    """Add replay-obligation evidence without modifying frozen Minimal B."""

    def _verification(self, outcome: ExecutableVerification) -> dict[str, Any]:
        return {
            **super()._verification(outcome),
            "obligation_snapshot": verification_obligation_snapshot(outcome),
        }


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _bounded_text(value: str, limit: int = 4_000) -> str:
    if len(value) <= limit:
        return value
    half = limit // 2
    return value[:half] + "\n... replay evidence omitted ...\n" + value[-half:]


def _obligation(
    domain: str,
    subject: str,
    predicate: str,
    required: Any,
    observed: Any,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "domain": domain,
        "subject": subject,
        "predicate": predicate,
        "required": required,
        "observed": observed,
        "evidence": evidence,
    }


def _obligation_key(item: dict[str, Any]) -> str:
    return _canonical(
        {
            key: item.get(key)
            for key in ("domain", "subject", "predicate", "required")
        }
    )


def _structured_obligations(
    outcome: ExecutableVerification,
) -> list[dict[str, Any]]:
    observations: dict[tuple[str, str], Any] = {}
    for item in outcome.counterexamples:
        if not item.kind.endswith("-observation") or not isinstance(item.value, dict):
            continue
        finding_id = item.value.get("finding_id")
        if isinstance(finding_id, str):
            observations[(item.kind.removesuffix("-observation"), finding_id)] = (
                item.value
            )

    obligations: list[dict[str, Any]] = []
    for item in outcome.counterexamples:
        value = item.value
        if item.kind.endswith("-requirement") and isinstance(value, dict):
            domain = item.kind.removesuffix("-requirement")
            finding_id = value.get("finding_id")
            observation = (
                observations.get((domain, finding_id), {})
                if isinstance(finding_id, str)
                else {}
            )
            if "present" in value:
                predicate = "present"
                required = value.get("present")
                observed = observation.get("present")
            elif "specifier" in value:
                predicate = "version"
                required = value.get("specifier")
                observed = observation.get("version")
            else:
                predicate = "equals"
                required = value.get("value")
                observed = observation.get("value")
            subject = value.get("name")
            if isinstance(subject, str) and subject:
                obligations.append(
                    _obligation(
                        domain,
                        subject,
                        predicate,
                        required,
                        observed,
                        {
                            "source": "structured-goal-finding",
                            "finding_id": finding_id,
                            "confidence": item.confidence,
                        },
                    )
                )
            continue

        if item.kind == "import-provider-provenance" and isinstance(value, dict):
            violations = value.get("violations")
            if isinstance(violations, list):
                for violation in violations:
                    if not isinstance(violation, dict):
                        continue
                    module = violation.get("module")
                    if isinstance(module, str) and module:
                        obligations.append(
                            _obligation(
                                "integrity",
                                module,
                                "installed_distribution_owned",
                                True,
                                False,
                                {
                                    "source": item.kind,
                                    "violation": violation,
                                },
                            )
                        )
                continue

        if not item.kind.endswith("-observation"):
            obligations.append(
                _obligation(
                    "replay",
                    item.kind,
                    "satisfied",
                    True,
                    False,
                    {
                        "source": "structured-counterexample",
                        "value": value,
                        "confidence": item.confidence,
                    },
                )
            )
    return obligations


def verification_obligation_snapshot(
    outcome: ExecutableVerification,
) -> dict[str, Any]:
    complete_findings = outcome.details.get("finding_set_complete") is True
    if outcome.passed is True:
        coverage = "complete-pass"
    elif (
        outcome.passed is False
        and outcome.bootstrap.exit_code == 0
        and complete_findings
    ):
        coverage = "complete-goal-failure"
    elif outcome.passed is None:
        coverage = "unknown"
    else:
        coverage = "partial-failure"

    obligations = _structured_obligations(outcome)
    if outcome.bootstrap.exit_code not in (None, 0):
        obligations.append(
            _obligation(
                "operation",
                "complete-bootstrap-program",
                "exit_code",
                0,
                outcome.bootstrap.exit_code,
                {
                    "source": "bootstrap-execution",
                    "stderr": _bounded_text(outcome.bootstrap.stderr),
                },
            )
        )
    unique = {_obligation_key(item): item for item in obligations}
    return {
        "schema": REPLAY_OBLIGATION_SNAPSHOT_SCHEMA,
        "coverage": coverage,
        "verification_passed": outcome.passed,
        "finding_set_complete": complete_findings,
        "obligations": [unique[key] for key in sorted(unique)],
    }


class ReplayObligationLedger:
    """Preserve replay obligations until complete evidence can retire them."""

    def __init__(self) -> None:
        self.replay_count = 0
        self.active: dict[str, dict[str, Any]] = {}
        self.coverage_counts: dict[str, int] = {}
        self.introduced_count = 0
        self.resolved_count = 0

    @staticmethod
    def _fallback_snapshot(replay: dict[str, Any]) -> dict[str, Any]:
        phase = replay.get("phase")
        validation = replay.get("candidate_validation")
        obligations: list[dict[str, Any]] = []
        coverage = "unknown"
        if phase == "candidate-validation" and isinstance(validation, dict):
            coverage = "partial-failure"
            obligations.append(
                _obligation(
                    "integrity",
                    str(validation.get("policy_id") or "candidate-validation"),
                    "accepted",
                    True,
                    False,
                    {
                        "source": "candidate-validation",
                        "reason": validation.get("reason"),
                        "details": validation.get("details"),
                    },
                )
            )
        return {
            "schema": REPLAY_OBLIGATION_SNAPSHOT_SCHEMA,
            "coverage": coverage,
            "verification_passed": None,
            "finding_set_complete": False,
            "obligations": obligations,
        }

    def update(self, replay: dict[str, Any]) -> dict[str, Any]:
        self.replay_count += 1
        verification = replay.get("verification")
        snapshot = (
            verification.get("obligation_snapshot")
            if isinstance(verification, dict)
            else None
        )
        if not isinstance(snapshot, dict):
            snapshot = self._fallback_snapshot(replay)
        if snapshot.get("schema") != REPLAY_OBLIGATION_SNAPSHOT_SCHEMA:
            raise ValueError("Replay obligation snapshot has an invalid schema")
        coverage = snapshot.get("coverage")
        obligations = snapshot.get("obligations")
        if coverage not in {
            "complete-pass",
            "complete-goal-failure",
            "partial-failure",
            "unknown",
        } or not isinstance(obligations, list):
            raise ValueError("Replay obligation snapshot is malformed")
        self.coverage_counts[coverage] = self.coverage_counts.get(coverage, 0) + 1

        observed: dict[str, dict[str, Any]] = {}
        for item in obligations:
            if not isinstance(item, dict):
                raise ValueError("Replay obligation is malformed")
            key = _obligation_key(item)
            observed[key] = item

        previous_keys = set(self.active)
        previous_active = dict(self.active)
        current_keys = set(observed)
        complete = coverage in {"complete-pass", "complete-goal-failure"}
        resolved_keys = previous_keys - current_keys if complete else set()
        introduced_keys = current_keys - previous_keys
        repeated_keys = current_keys & previous_keys
        preserved_keys = previous_keys - current_keys if not complete else set()

        if complete:
            self.active = {
                key: {
                    "obligation": item,
                    "first_seen_replay": self.active.get(key, {}).get(
                        "first_seen_replay", self.replay_count
                    ),
                    "last_seen_replay": self.replay_count,
                }
                for key, item in observed.items()
            }
        else:
            for key, item in observed.items():
                record = self.active.get(key)
                self.active[key] = {
                    "obligation": item,
                    "first_seen_replay": (
                        record["first_seen_replay"]
                        if record is not None
                        else self.replay_count
                    ),
                    "last_seen_replay": self.replay_count,
                }

        self.introduced_count += len(introduced_keys)
        self.resolved_count += len(resolved_keys)

        def records(
            keys: set[str],
            source: dict[str, dict[str, Any]],
        ) -> list[dict[str, Any]]:
            return [source[key] for key in sorted(keys) if key in source]

        def projected(items: list[dict[str, Any]]) -> dict[str, Any]:
            visible = items[:_MODEL_VISIBLE_OBLIGATIONS]
            return {
                "count": len(items),
                "items": visible,
                "truncated": len(items) > len(visible),
            }

        active_records = [self.active[key] for key in sorted(self.active)]
        visible = active_records[:_MODEL_VISIBLE_OBLIGATIONS]
        return {
            "schema": REPLAY_OBLIGATION_LEDGER_SCHEMA,
            "advisory_only": True,
            "operation_constraints_added": False,
            "replay_index": self.replay_count,
            "evidence_coverage": coverage,
            "update_semantics": (
                "replace-under-complete-evidence"
                if complete
                else "preserve-under-partial-observability"
            ),
            "active_obligation_count": len(active_records),
            "active_obligations": visible,
            "active_obligations_truncated": len(active_records) > len(visible),
            "delta": {
                "introduced": projected(records(introduced_keys, self.active)),
                "resolved": projected(records(resolved_keys, previous_active)),
                "observed_again": projected(records(repeated_keys, self.active)),
                "preserved_unobserved": projected(
                    records(preserved_keys, self.active)
                ),
            },
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "schema": REPLAY_OBLIGATION_LEDGER_SCHEMA,
            "replay_count": self.replay_count,
            "active_obligation_count": len(self.active),
            "coverage_counts": dict(sorted(self.coverage_counts.items())),
            "introduced_count": self.introduced_count,
            "resolved_count": self.resolved_count,
            "cross_case_memory": False,
            "operation_constraints_added": False,
            "stores_container_checkpoint": False,
        }
