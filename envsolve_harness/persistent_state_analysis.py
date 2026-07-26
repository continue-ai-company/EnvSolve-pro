from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from envsolve_harness.core.io import read_json
from envsolve_harness.results import summarize_schedule
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


PERSISTENT_METHODS = {
    "envsolve-pro-goal-contract-evidence-anchor-persistent",
    "envsolve-pro-goal-aware-raw-evidence-anchor-persistent",
}
FRESH_METHOD = "envsolve-pro-goal-contract-evidence-anchor"


def _sequence(item: dict[str, Any]) -> int:
    metadata = item.get("state_metadata")
    if not isinstance(metadata, dict):
        return 0
    value = metadata.get("event_sequence")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _details(verification: dict[str, Any]) -> dict[str, Any]:
    value = verification.get("details")
    return value if isinstance(value, dict) else {}


def _environment_id(verification: dict[str, Any]) -> str | None:
    receipt = _details(verification).get("environment_receipt")
    if not isinstance(receipt, dict):
        return None
    value = receipt.get("environment_id")
    return value if isinstance(value, str) and value else None


def _action_sha256(actions: dict[str, Any], candidate_id: str) -> str | None:
    action = actions.get(candidate_id)
    if not isinstance(action, dict):
        return None
    artifact = action.get("command_artifact")
    if not isinstance(artifact, dict):
        return None
    value = artifact.get("sha256")
    return value if isinstance(value, str) and value else None


def _transition_records(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = snapshot.get("evidence")
    if not isinstance(evidence, dict):
        return []
    records = []
    for item in evidence.values():
        if (
            not isinstance(item, dict)
            or item.get("kind") != "state-transition-observation"
        ):
            continue
        value = item.get("value")
        if not isinstance(value, dict):
            continue
        records.append(
            {
                "candidate_id": value.get("candidate_id"),
                "environment_id": value.get("environment_id"),
                "disposition": value.get("disposition"),
                "reason": value.get("reason"),
                "event_sequence": _sequence(item),
            }
        )
    return sorted(records, key=lambda item: item["event_sequence"])


def audit_persistent_episode(root: Path, method: str) -> dict[str, Any]:
    """Audit state reuse and clean certification without interpreting task findings."""
    snapshot_path = root / "generation" / "episode_snapshot.json"
    result_path = root / "generation" / "result.json"
    errors: list[str] = []
    if not snapshot_path.is_file():
        return {
            "schema_version": "1.0.0",
            "method": method,
            "environment_strategy": (
                "postcondition-persistent"
                if method in PERSISTENT_METHODS
                else "fresh-candidate"
            ),
            "valid": False,
            "errors": ["episode snapshot is missing"],
            "metrics": None,
        }

    snapshot = read_json(snapshot_path)
    raw_actions = snapshot.get("actions")
    actions = raw_actions if isinstance(raw_actions, dict) else {}
    raw_verifications = snapshot.get("verifications")
    verifications = (
        sorted(
            (
                item
                for item in raw_verifications
                if isinstance(item, dict)
            ),
            key=_sequence,
        )
        if isinstance(raw_verifications, list)
        else []
    )
    transitions = _transition_records(snapshot)
    dispositions = Counter(
        str(item["disposition"])
        for item in transitions
        if item.get("disposition") in {"reusable", "damaged", "unknown"}
    )

    for verification in verifications:
        details = _details(verification)
        if details.get("feedback_channel") != "internal_execution":
            errors.append(
                f"{verification.get('verification_id')} uses a non-internal feedback channel"
            )
    raw_evidence = snapshot.get("evidence")
    if isinstance(raw_evidence, dict):
        for item in raw_evidence.values():
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "").lower()
            if "official-evaluator" in source or "official_evaluator" in source:
                errors.append("Official evaluator evidence entered the online episode")
                break

    persistent = method in PERSISTENT_METHODS
    if not persistent:
        if transitions:
            errors.append("Fresh-state control contains state-transition evidence")
        for verification in verifications:
            details = _details(verification)
            if details.get("environment_fresh") is not True:
                errors.append(
                    f"{verification.get('verification_id')} is not fresh in the control"
                )
        return {
            "schema_version": "1.0.0",
            "method": method,
            "environment_strategy": "fresh-candidate",
            "valid": not errors,
            "errors": errors,
            "metrics": {
                "transition_counts": dict(dispositions),
                "construction_verifications": 0,
                "reused_construction_verifications": 0,
                "clean_replay_attempts": 0,
                "clean_replay_passes": 0,
                "reused_construction_clean_passes": 0,
            },
        }

    construction = [
        item
        for item in verifications
        if _details(item).get("verification_role") == "construction-state"
    ]
    clean = [
        item
        for item in verifications
        if _details(item).get("verification_role")
        == "clean-replay-certification"
    ]
    clean_by_source: dict[str, list[dict[str, Any]]] = {}
    for verification in clean:
        candidate_id = _details(verification).get("candidate_id")
        if not isinstance(candidate_id, str):
            errors.append("Clean replay verification has no candidate identity")
            continue
        action = actions.get(candidate_id)
        metadata = action.get("metadata") if isinstance(action, dict) else None
        source = (
            metadata.get("source_candidate_id")
            if isinstance(metadata, dict)
            else None
        )
        if not isinstance(source, str) or not source:
            errors.append(f"{candidate_id} has no source candidate")
            continue
        clean_by_source.setdefault(source, []).append(verification)
        if _details(verification).get("environment_fresh") is not True:
            errors.append(f"{candidate_id} clean replay is not fresh")
        if _details(verification).get("state_lineage_id") is not None:
            errors.append(f"{candidate_id} clean replay retains construction lineage")
        if _action_sha256(actions, source) != _action_sha256(actions, candidate_id):
            errors.append(f"{candidate_id} does not replay the exact source program")

    reused = []
    reused_clean_passes = 0
    for verification in construction:
        details = _details(verification)
        candidate_id = details.get("candidate_id")
        lineage = details.get("state_lineage_id")
        environment_id = _environment_id(verification)
        if lineage != environment_id or not isinstance(lineage, str):
            errors.append(
                f"{verification.get('verification_id')} has inconsistent construction lineage"
            )
            continue
        if details.get("environment_fresh") is False:
            reused.append(verification)
            prior = [
                item
                for item in transitions
                if item.get("environment_id") == lineage
                and item.get("candidate_id") != candidate_id
                and item.get("disposition") == "reusable"
                and item["event_sequence"] < _sequence(verification)
            ]
            if not prior:
                errors.append(
                    f"{candidate_id} reused lineage {lineage} without prior reusable evidence"
                )
        elif details.get("environment_fresh") is not True:
            errors.append(f"{candidate_id} has no valid freshness label")

        if details.get("reported_passed") is True:
            replay = clean_by_source.get(str(candidate_id), [])
            if len(replay) != 1:
                errors.append(
                    f"{candidate_id} construction Pass has {len(replay)} clean replay verifications"
                )
            elif replay[0].get("passed") is True:
                if details.get("environment_fresh") is False:
                    reused_clean_passes += 1

    for transition in transitions:
        if transition.get("disposition") not in {"damaged", "unknown"}:
            continue
        later_reuse = any(
            _details(item).get("state_lineage_id")
            == transition.get("environment_id")
            and _details(item).get("candidate_id")
            != transition.get("candidate_id")
            and _sequence(item) > transition["event_sequence"]
            for item in construction
        )
        if later_reuse:
            errors.append(
                f"{transition.get('disposition')} lineage "
                f"{transition.get('environment_id')} was reused"
            )

    if result_path.is_file():
        result = read_json(result_path)
        metadata = result.get("metadata")
        episode = metadata.get("episode") if isinstance(metadata, dict) else None
        certification = (
            episode.get("candidate_certification")
            if isinstance(episode, dict)
            else None
        )
        if certification == "certified":
            accepted = episode.get("accepted_candidate")
            accepted_environment = episode.get("accepted_environment")
            accepted_id = (
                accepted.get("candidate_id")
                if isinstance(accepted, dict)
                else None
            )
            matched = [
                item
                for item in clean
                if _details(item).get("candidate_id") == accepted_id
                and item.get("passed") is True
            ]
            if len(matched) != 1:
                errors.append("Certified candidate lacks one passing clean replay")
            else:
                accepted_environment_id = (
                    accepted_environment.get("environment_id")
                    if isinstance(accepted_environment, dict)
                    else None
                )
                if accepted_environment_id != _environment_id(matched[0]):
                    errors.append(
                        "Certified candidate records the wrong clean replay environment"
                    )

    return {
        "schema_version": "1.0.0",
        "method": method,
        "environment_strategy": "postcondition-persistent",
        "valid": not errors,
        "errors": errors,
        "metrics": {
            "transition_counts": {
                key: dispositions.get(key, 0)
                for key in ("reusable", "damaged", "unknown")
            },
            "construction_verifications": len(construction),
            "reused_construction_verifications": len(reused),
            "clean_replay_attempts": len(clean),
            "clean_replay_passes": sum(item.get("passed") is True for item in clean),
            "reused_construction_clean_passes": reused_clean_passes,
        },
    }


def _paired_contrast(
    runs: list[dict[str, Any]],
    treatment: str,
    control: str,
) -> dict[str, Any]:
    blocks: dict[int, dict[str, dict[str, Any]]] = {}
    for run in runs:
        block = run.get("case_block")
        if isinstance(block, int):
            blocks.setdefault(block, {})[str(run["condition"])] = run
    counts = {
        "case_blocks": len(blocks),
        "eligible_blocks": 0,
        "censored_blocks": 0,
        "treatment_only_pass": 0,
        "control_only_pass": 0,
        "both_pass": 0,
        "neither_pass": 0,
    }
    for conditions in blocks.values():
        if treatment not in conditions or control not in conditions:
            raise ValueError("Schedule case block lacks a contrast condition")
        treatment_run = conditions[treatment]
        control_run = conditions[control]
        if not (
            treatment_run["scientifically_eligible"]
            and control_run["scientifically_eligible"]
            and isinstance(treatment_run["official_pass"], bool)
            and isinstance(control_run["official_pass"], bool)
        ):
            counts["censored_blocks"] += 1
            continue
        counts["eligible_blocks"] += 1
        outcomes = (
            treatment_run["official_pass"],
            control_run["official_pass"],
        )
        if outcomes == (True, True):
            counts["both_pass"] += 1
        elif outcomes == (True, False):
            counts["treatment_only_pass"] += 1
        elif outcomes == (False, True):
            counts["control_only_pass"] += 1
        else:
            counts["neither_pass"] += 1
    return counts


def analyze_postcondition_persistent_schedule(
    schedule_path: Path,
    runs_root: Path,
) -> dict[str, Any]:
    schedule_path = schedule_path.resolve()
    runs_root = runs_root.resolve()
    schedule = read_json(schedule_path)
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Schedule must contain episodes")
    base = summarize_schedule(schedule_path, runs_root)
    episode_by_run = {
        str(item["run_id"]): item for item in episodes if isinstance(item, dict)
    }
    runs = []
    for run in base["runs"]:
        episode = episode_by_run[str(run["run_id"])]
        root = runs_root / safe_name(str(run["run_id"])) / safe_name(
            str(run["case_id"])
        )
        runs.append(
            {
                **run,
                "condition": episode.get("condition"),
                "case_block": episode.get("case_block"),
                "mechanism": audit_persistent_episode(
                    root,
                    str(run["method"]),
                ),
            }
        )

    by_condition: dict[str, dict[str, Any]] = {}
    for condition in sorted({str(run["condition"]) for run in runs}):
        selected = [run for run in runs if run["condition"] == condition]
        mechanism_metrics = [
            run["mechanism"]["metrics"]
            for run in selected
            if isinstance(run["mechanism"].get("metrics"), dict)
        ]
        by_condition[condition] = {
            "runs": len(selected),
            "scientifically_eligible": sum(
                run["scientifically_eligible"] for run in selected
            ),
            "official_pass": sum(run["official_pass"] is True for run in selected),
            "official_fail": sum(run["official_pass"] is False for run in selected),
            "mechanism_integrity_valid": sum(
                run["mechanism"]["valid"] for run in selected
            ),
            "reused_construction_verifications": sum(
                item["reused_construction_verifications"]
                for item in mechanism_metrics
            ),
            "clean_replay_passes": sum(
                item["clean_replay_passes"] for item in mechanism_metrics
            ),
            "reused_construction_clean_passes": sum(
                item["reused_construction_clean_passes"]
                for item in mechanism_metrics
            ),
        }

    primary = _paired_contrast(runs, "persistent-explicit", "fresh-explicit")
    secondary = _paired_contrast(runs, "persistent-explicit", "persistent-raw")
    complete = all(
        run["descriptive_terminal"] not in {"missing_artifacts", "incomplete"}
        for run in runs
    )
    integrity_valid = complete and all(run["mechanism"]["valid"] for run in runs)
    primary_no_loss: bool | None = None
    if primary["eligible_blocks"] == primary["case_blocks"] == 5:
        primary_no_loss = (
            primary["treatment_only_pass"] >= primary["control_only_pass"]
        )
    reuse_demonstrated = (
        by_condition.get("persistent-explicit", {}).get(
            "reused_construction_clean_passes",
            0,
        )
        > 0
    )
    if not complete:
        decision = "pending"
    elif not integrity_valid:
        decision = "measurement-integrity-failed"
    elif primary_no_loss is None:
        decision = "effect-inconclusive"
    elif primary_no_loss and reuse_demonstrated:
        decision = "retain-mechanism"
    else:
        decision = "redesign-mechanism"

    return {
        "schema_version": "1.0.0",
        "schedule": {
            "path": schedule_path.name,
            "sha256": sha256_file(schedule_path),
        },
        "conditions": by_condition,
        "contrasts": {
            "primary_persistent_vs_fresh_explicit": primary,
            "secondary_explicit_vs_raw_persistent": secondary,
        },
        "gate": {
            "schedule_complete": complete,
            "mechanism_integrity_valid": integrity_valid,
            "primary_no_official_pass_loss": primary_no_loss,
            "verified_reuse_demonstrated": reuse_demonstrated,
            "decision": decision,
        },
        "base_summary": {
            "descriptive": base["descriptive"],
            "scientific": base["scientific"],
        },
        "runs": runs,
    }
