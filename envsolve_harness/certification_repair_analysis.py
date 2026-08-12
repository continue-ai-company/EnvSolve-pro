from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.minimal_b_analysis import (
    _episode_result,
    _exact_mcnemar_p,
    _resource_analysis,
)
from envsolve_harness.utils.provenance import sha256_file


def classify_replay_sequence(
    records: list[dict[str, Any]],
    *,
    official_pass: bool,
    infrastructure_censored_replay_ids: frozenset[str] = frozenset(),
    integrity_invalid_replay_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    executed = [
        record
        for record in records
        if record.get("replay_executed") is not False
        and record.get("status") != "replay_limit"
    ]
    observed_ids = {str(record.get("replay_id")) for record in records}
    unknown_censored = infrastructure_censored_replay_ids - observed_ids
    if unknown_censored:
        raise ValueError(
            f"Infrastructure censor references unknown replay IDs: {unknown_censored}"
        )
    unknown_invalid = integrity_invalid_replay_ids - observed_ids
    if unknown_invalid:
        raise ValueError(
            f"Integrity adjudication references unknown replay IDs: {unknown_invalid}"
        )
    overlapping = infrastructure_censored_replay_ids & integrity_invalid_replay_ids
    if overlapping:
        raise ValueError(
            f"Replay IDs cannot be both infrastructure-censored and integrity-invalid: "
            f"{overlapping}"
        )
    effective = [
        record
        for record in executed
        if str(record.get("replay_id")) not in infrastructure_censored_replay_ids
        and str(record.get("replay_id")) not in integrity_invalid_replay_ids
    ]
    raw_first = executed[0] if executed else None
    first = effective[0] if effective else None
    raw_first_status = (
        str(raw_first.get("status")) if raw_first is not None else None
    )
    first_status = str(first.get("status")) if first is not None else None
    first_digest = first.get("program_sha256") if first is not None else None
    opportunity = first_status in {"fail", "unknown"}
    later_different_passes = [
        record
        for record in effective[1:]
        if record.get("status") == "pass"
        and record.get("certified") is True
        and record.get("program_sha256") != first_digest
    ]
    activated = opportunity and bool(later_different_passes)
    return {
        "submission_records": len(records),
        "executed_replays": len(executed),
        "effective_replays": len(effective),
        "infrastructure_censored_replays": len(
            infrastructure_censored_replay_ids
        ),
        "integrity_invalid_replays": len(integrity_invalid_replay_ids),
        "replay_limit_rejections": sum(
            record.get("status") == "replay_limit" for record in records
        ),
        "status_sequence": [str(record.get("status")) for record in records],
        "raw_first_replay_status": raw_first_status,
        "first_replay_status": first_status,
        "first_replay_pass": first_status == "pass",
        "repair_opportunity": opportunity,
        "activated_repair": activated,
        "later_different_passing_replays": len(later_different_passes),
        "repair_success": activated and official_pass,
    }


def _pairwise_official(
    cases: list[dict[str, Any]],
    left: str,
    right: str,
) -> dict[str, Any]:
    counts = Counter()
    rows = []
    for case in cases:
        left_pass = case["episodes"][left]["official_pass_at_1"]
        right_pass = case["episodes"][right]["official_pass_at_1"]
        if left_pass and right_pass:
            category = "both_pass"
        elif left_pass:
            category = "left_only_pass"
        elif right_pass:
            category = "right_only_pass"
        else:
            category = "neither_pass"
        counts[category] += 1
        rows.append(
            {
                "case_index": case["case_index"],
                "repository": case["repository"],
                "category": category,
            }
        )
    return {
        "left": left,
        "right": right,
        "pairs": rows,
        "counts": {
            "both_pass": counts["both_pass"],
            "left_only_pass": counts["left_only_pass"],
            "right_only_pass": counts["right_only_pass"],
            "neither_pass": counts["neither_pass"],
        },
        "absolute_pass_rate_difference": (
            sum(case["episodes"][left]["official_pass_at_1"] for case in cases)
            - sum(case["episodes"][right]["official_pass_at_1"] for case in cases)
        )
        / len(cases),
        "exact_two_sided_mcnemar_p": _exact_mcnemar_p(
            counts["left_only_pass"],
            counts["right_only_pass"],
        ),
    }


def analyze_certification_repair_ablation(
    adjudication_path: Path,
    runs_root: Path,
) -> dict[str, Any]:
    adjudication_path = adjudication_path.resolve()
    project_root = Path(__file__).resolve().parents[1]
    adjudication = read_json(adjudication_path)
    conditions = adjudication.get("conditions")
    if not isinstance(conditions, dict) or set(conditions) != {"A", "B", "C"}:
        raise ValueError("Adjudication must define exactly A, B, and C conditions")
    raw_episodes = adjudication.get("effective_episodes")
    if not isinstance(raw_episodes, list) or len(raw_episodes) != 24:
        raise ValueError("Certification-repair Dev-8 requires 24 effective episodes")

    episodes = []
    for raw in raw_episodes:
        episode = _episode_result(project_root, runs_root.resolve(), raw)
        replay_path = Path(episode["artifact_root"]) / "generation/minimal-b/replays.jsonl"
        records = read_jsonl(replay_path) if replay_path.is_file() else []
        replay_adjudication = raw.get("replay_adjudication") or {}
        if not isinstance(replay_adjudication, dict):
            raise TypeError("Replay adjudication must be an object")
        censored_ids = replay_adjudication.get(
            "infrastructure_censored_replay_ids",
            [],
        )
        if not isinstance(censored_ids, list) or not all(
            isinstance(value, str) for value in censored_ids
        ):
            raise ValueError("Infrastructure-censored replay IDs must be strings")
        invalid_ids = replay_adjudication.get(
            "integrity_invalid_replay_ids",
            [],
        )
        if not isinstance(invalid_ids, list) or not all(
            isinstance(value, str) for value in invalid_ids
        ):
            raise ValueError("Integrity-invalid replay IDs must be strings")
        episode["replay_mechanism"] = classify_replay_sequence(
            records,
            official_pass=episode["official_pass_at_1"],
            infrastructure_censored_replay_ids=frozenset(censored_ids),
            integrity_invalid_replay_ids=frozenset(invalid_ids),
        )
        episode["replay_adjudication"] = replay_adjudication
        if episode["condition"] == conditions["A"] and records:
            raise ValueError("Arm A unexpectedly contains generation clean replay records")
        if (
            episode["condition"] == conditions["B"]
            and episode["replay_mechanism"]["executed_replays"] > 1
        ):
            raise ValueError("Arm B executed more than one clean replay")
        episodes.append(episode)

    grouped: dict[int, list[dict[str, Any]]] = {}
    for episode in episodes:
        grouped.setdefault(int(episode["pair_index"]), []).append(episode)
    if len(grouped) != 8:
        raise ValueError("Certification-repair Dev-8 requires eight case groups")

    cases = []
    expected_conditions = set(conditions.values())
    for case_index, case_episodes in sorted(grouped.items()):
        by_condition = {str(item["condition"]): item for item in case_episodes}
        if set(by_condition) != expected_conditions:
            raise ValueError(f"Case {case_index} does not contain all frozen arms")
        repositories = {str(item["repository"]) for item in case_episodes}
        if len(repositories) != 1:
            raise ValueError(f"Case {case_index} has inconsistent repositories")
        cases.append(
            {
                "case_index": case_index,
                "pair_index": case_index,
                "repository": repositories.pop(),
                "episodes": by_condition,
            }
        )

    by_arm = {}
    for arm, condition in conditions.items():
        selected = [item for item in episodes if item["condition"] == condition]
        by_arm[arm] = {
            "condition": condition,
            "runs": len(selected),
            "generation_completed": sum(item["generation_completed"] for item in selected),
            "official_evaluator_reached": sum(
                item["official_evaluator_reached"] for item in selected
            ),
            "official_pass_at_1": sum(item["official_pass_at_1"] for item in selected),
            "pass_rate": mean(item["official_pass_at_1"] for item in selected),
        }

    mechanism_by_arm = {}
    for arm in ("B", "C"):
        condition = conditions[arm]
        selected = [item for item in episodes if item["condition"] == condition]
        mechanism_by_arm[arm] = {
            key: sum(item["replay_mechanism"][key] for item in selected)
            for key in (
                "executed_replays",
                "effective_replays",
                "infrastructure_censored_replays",
                "integrity_invalid_replays",
                "replay_limit_rejections",
                "first_replay_pass",
                "repair_opportunity",
                "activated_repair",
                "repair_success",
            )
        }

    pairwise = {
        "B_vs_A_certification": _pairwise_official(
            cases,
            conditions["B"],
            conditions["A"],
        ),
        "C_vs_B_retry": _pairwise_official(
            cases,
            conditions["C"],
            conditions["B"],
        ),
    }
    return {
        "schema_version": "1.0.0",
        "study_id": adjudication["study_id"],
        "claim_scope": adjudication["claim_scope"],
        "inputs": {
            "adjudication": str(adjudication_path),
            "adjudication_sha256": sha256_file(adjudication_path),
            "runs_root": str(runs_root.resolve()),
        },
        "conditions": conditions,
        "primary": {
            "metric": "repository-paired Official Pass@1",
            "by_arm": by_arm,
            "pairwise": pairwise,
        },
        "mechanism": {
            "by_arm": mechanism_by_arm,
            "feedback_conditioned_repair_activation_observed": (
                mechanism_by_arm["C"]["activated_repair"] > 0
            ),
            "feedback_conditioned_repair_success_observed": (
                mechanism_by_arm["C"]["repair_success"] > 0
            ),
            "support_rule": (
                "C first integrity-valid replay Fail/Unknown, later different "
                "integrity-valid replay Pass, and final Official Pass"
            ),
        },
        "resources": {
            "B_vs_A": _resource_analysis(
                cases,
                conditions["B"],
                conditions["A"],
            ),
            "C_vs_B": _resource_analysis(
                cases,
                conditions["C"],
                conditions["B"],
            ),
            "optional_unavailable_metrics": [
                "peak_memory_bytes",
                "disk_growth_bytes",
                "network_bytes",
            ],
        },
        "cases": cases,
        "excluded_attempts": adjudication.get("excluded_attempts", []),
        "analysis_implementation": {
            "path": "envsolve_harness/certification_repair_analysis.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }
