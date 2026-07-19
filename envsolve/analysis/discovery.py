from __future__ import annotations

from collections import Counter
from typing import Any


def observable_outcome(
    solver: dict[str, Any],
    evaluation: dict[str, Any] | None,
) -> str:
    if solver.get("generation_completed") is not True:
        metadata = solver.get("metadata")
        completion = metadata.get("v0_completion") if isinstance(metadata, dict) else None
        if isinstance(completion, dict) and completion.get("passed") is False:
            return "verifier_rejection"
        error = str(solver.get("error", "")).lower()
        if "unsupported command" in error or "unreplayable" in error:
            return "unsafe_or_unreplayable_action"
        return "solver_error"
    if not isinstance(evaluation, dict) or evaluation.get("evaluation_completed") is not True:
        return "evaluator_error"
    if evaluation.get("official_pass") is True:
        return "success"
    return "official_failure"


def paired_aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    outcome_counts: dict[str, Counter[str]] = {
        "envsolve_v0": Counter(),
        "freeagent": Counter(),
    }
    for record in records:
        condition = str(record["condition"])
        if condition not in outcome_counts:
            raise ValueError(f"unknown discovery condition: {condition}")
        case_id = str(record["case_id"])
        if condition in by_case.setdefault(case_id, {}):
            raise ValueError(f"duplicate {condition} record for {case_id}")
        by_case[case_id][condition] = record
        outcome_counts[condition][str(record["observable_outcome"])] += 1
    incomplete = {
        case_id: sorted({"envsolve_v0", "freeagent"} - conditions.keys())
        for case_id, conditions in by_case.items()
        if conditions.keys() != {"envsolve_v0", "freeagent"}
    }
    if incomplete:
        raise ValueError(f"incomplete discovery pairs: {incomplete}")

    paired = Counter()
    for conditions in by_case.values():
        v0_pass = conditions["envsolve_v0"].get("official_pass") is True
        free_pass = conditions["freeagent"].get("official_pass") is True
        if v0_pass and free_pass:
            paired["both_pass"] += 1
        elif v0_pass:
            paired["envsolve_v0_only"] += 1
        elif free_pass:
            paired["freeagent_only"] += 1
        else:
            paired["neither_pass"] += 1
    return {
        "cases": len(by_case),
        "attempts": len(records),
        "observable_outcomes": {
            condition: dict(sorted(counts.items()))
            for condition, counts in outcome_counts.items()
        },
        "official_pairing": dict(sorted(paired.items())),
    }
