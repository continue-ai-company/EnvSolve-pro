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


def _obligation_map(result: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    current = result.get("current")
    obligations = current.get("obligations") if isinstance(current, dict) else None
    if not isinstance(obligations, list):
        return None
    values: dict[str, dict[str, Any]] = {}
    for obligation in obligations:
        if not isinstance(obligation, dict) or any(
            field not in obligation for field in _OBLIGATION_FIELDS[:3]
        ):
            return None
        values[_obligation_key(obligation)] = obligation
    return values


def evaluate_constraint_hypothesis(
    *,
    provider: dict[str, Any],
    expected_effect: str,
    target_subjects: list[str],
    operation: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Classify one Agent-proposed operation by its exact executable-goal effect."""

    declared_subjects = set(target_subjects)
    before_map = _obligation_map(before)
    after_map = _obligation_map(after)
    if before.get("ok") is not True or before_map is None:
        classification = "inconclusive_before_measurement"
        active_targets: set[str] = set()
        resolved_targets: set[str] = set()
        introduced: set[str] = set()
        missing_subjects: set[str] = set()
    elif after.get("ok") is not True or after_map is None:
        classification = "inconclusive_after_measurement"
        active_targets = {
            key
            for key, obligation in before_map.items()
            if obligation.get("subject") in declared_subjects
        }
        resolved_targets = set()
        introduced = set()
        missing_subjects = declared_subjects - {
            str(before_map[key].get("subject")) for key in active_targets
        }
    else:
        active_targets = {
            key
            for key, obligation in before_map.items()
            if obligation.get("subject") in declared_subjects
        }
        active_subjects = {
            str(before_map[key].get("subject")) for key in active_targets
        }
        missing_subjects = declared_subjects - active_subjects
        after_set = set(after_map)
        resolved_targets = active_targets - after_set
        introduced = after_set - set(before_map)
        if missing_subjects:
            classification = "invalid_target"
        elif resolved_targets == active_targets and not introduced:
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
            "target_subjects": sorted(declared_subjects),
            "bound_target_obligations": decode(active_targets),
        },
        "effect_evidence": {
            "declared_target_subject_count": len(declared_subjects),
            "missing_target_subjects": sorted(missing_subjects),
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
