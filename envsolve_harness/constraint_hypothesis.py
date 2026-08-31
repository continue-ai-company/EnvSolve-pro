from __future__ import annotations

import json
from typing import Any


HYPOTHESIS_SCHEMA = "envsolve-executable-constraint-hypothesis-v1"
_OBLIGATION_FIELDS = ("domain", "subject", "predicate", "required")


def _obligation_key(value: dict[str, Any]) -> str:
    return json.dumps(
        {field: value.get(field) for field in _OBLIGATION_FIELDS},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _obligation_set(result: dict[str, Any]) -> set[str] | None:
    current = result.get("current")
    obligations = current.get("obligations") if isinstance(current, dict) else None
    if not isinstance(obligations, list):
        return None
    values: set[str] = set()
    for obligation in obligations:
        if not isinstance(obligation, dict) or any(
            field not in obligation for field in _OBLIGATION_FIELDS[:3]
        ):
            return None
        values.add(_obligation_key(obligation))
    return values


def evaluate_constraint_hypothesis(
    *,
    provider: dict[str, Any],
    expected_effect: str,
    target_obligations: list[dict[str, Any]],
    operation: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Classify one Agent-proposed operation by its exact executable-goal effect."""

    declared_targets = {_obligation_key(item) for item in target_obligations}
    before_set = _obligation_set(before)
    after_set = _obligation_set(after)
    if before.get("ok") is not True or before_set is None:
        classification = "inconclusive_before_measurement"
        active_targets: set[str] = set()
        resolved_targets: set[str] = set()
        introduced: set[str] = set()
    elif after.get("ok") is not True or after_set is None:
        classification = "inconclusive_after_measurement"
        active_targets = declared_targets & before_set
        resolved_targets = set()
        introduced = set()
    else:
        active_targets = declared_targets & before_set
        resolved_targets = active_targets - after_set
        introduced = after_set - before_set
        if active_targets != declared_targets:
            classification = "invalid_target"
        elif resolved_targets == declared_targets and not introduced:
            classification = "supported"
        elif resolved_targets:
            classification = "partially_supported"
        else:
            classification = "refuted"

    def decode(values: set[str]) -> list[dict[str, Any]]:
        return [json.loads(value) for value in sorted(values)]

    return {
        "schema": HYPOTHESIS_SCHEMA,
        "advisory_only": True,
        "operation_constraints_added": False,
        "classification": classification,
        "hypothesis": {
            "provider": provider,
            "provider_identity_evidence": "agent-declared-not-independently-verified",
            "expected_effect": expected_effect,
            "target_obligations": decode(declared_targets),
        },
        "effect_evidence": {
            "declared_target_count": len(declared_targets),
            "active_target_count_before": len(active_targets),
            "resolved_target_count": len(resolved_targets),
            "resolved_targets": decode(resolved_targets),
            "introduced_obligation_count": len(introduced),
            "introduced_obligations": decode(introduced),
            "goal_status_before": before.get("goal_status"),
            "goal_status_after": after.get("goal_status"),
            "candidate_ready_after": after.get("candidate_ready") is True,
        },
        "operation": operation,
        "before": before,
        "after": after,
    }
