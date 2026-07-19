from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


def _verification_category(event: dict[str, Any]) -> str:
    payload = event.get("payload") or {}
    details = payload.get("details") or {}
    verifier_details = details.get("verifier_details") or {}
    if isinstance(verifier_details.get("failed_candidate_action"), dict):
        return "candidate_command_failure"
    summary = str(details.get("summary") or "")
    if summary.startswith("structured verifier:"):
        return "structured_obligations_active"
    if summary == "Complete candidate failed fixed internal Python checks":
        return "fixed_internal_check_failure"
    passed = payload.get("passed")
    if passed is True:
        return "verification_pass"
    if passed is None:
        return "verification_unknown"
    return "verification_failure_other"


def _candidate_category(
    finished: dict[str, Any],
    verification: dict[str, Any] | None,
) -> str:
    exit_code = (finished.get("payload") or {}).get("exit_code")
    if exit_code == 252:
        return "candidate_validation_reject"
    if exit_code == 251:
        return "operation_guard_reject"
    if verification is None:
        return "unverified_action"
    return _verification_category(verification)


def _analyze_run(episode: dict[str, Any], runs_root: Path) -> dict[str, Any]:
    root = runs_root / safe_name(str(episode["run_id"])) / safe_name(str(episode["case_id"]))
    episode_path = root / "generation" / "episode.jsonl"
    if not episode_path.is_file():
        raise ValueError(f"Run has no episode evidence: {root}")
    events = read_jsonl(episode_path)
    proposed = {
        str((event.get("payload") or {}).get("action_id")): event
        for event in events
        if event.get("event_type") == "action_proposed"
    }
    finished = {
        str((event.get("payload") or {}).get("action_id")): event
        for event in events
        if event.get("event_type") == "action_finished"
    }
    verifications = {
        str(((event.get("payload") or {}).get("details") or {}).get("candidate_id")): event
        for event in events
        if event.get("event_type") == "verification_recorded"
    }
    if not proposed or set(proposed) != set(finished):
        raise ValueError(f"Run has incomplete candidate transitions: {root}")

    proposed_sequences = sorted(int(event["sequence"]) for event in proposed.values())
    candidates: list[dict[str, Any]] = []
    for candidate_id, proposed_event in sorted(
        proposed.items(), key=lambda item: int(item[1]["sequence"])
    ):
        finished_event = finished[candidate_id]
        category = _candidate_category(finished_event, verifications.get(candidate_id))
        finished_sequence = int(finished_event["sequence"])
        candidates.append(
            {
                "candidate_id": candidate_id,
                "proposed_sequence": int(proposed_event["sequence"]),
                "finished_sequence": finished_sequence,
                "exit_code": (finished_event.get("payload") or {}).get("exit_code"),
                "category": category,
                "later_proposal": any(
                    sequence > finished_sequence for sequence in proposed_sequences
                ),
            }
        )
    counts = Counter(str(candidate["category"]) for candidate in candidates)
    return {
        **{
            key: episode.get(key)
            for key in ("position", "pair_index", "case_id", "run_id", "method", "seed")
        },
        "episode_sha256": sha256_file(episode_path),
        "candidates": candidates,
        "counts": {
            "candidates": len(candidates),
            "executed_candidates": len(candidates)
            - counts["candidate_validation_reject"]
            - counts["operation_guard_reject"],
            "later_proposal_candidates": sum(
                bool(candidate["later_proposal"]) for candidate in candidates
            ),
            "categories": dict(sorted(counts.items())),
        },
    }


def _aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    categories: Counter[str] = Counter()
    candidates = 0
    executed = 0
    later = 0
    for run in runs:
        counts = run["counts"]
        candidates += int(counts["candidates"])
        executed += int(counts["executed_candidates"])
        later += int(counts["later_proposal_candidates"])
        categories.update(counts["categories"])
    return {
        "runs": len(runs),
        "candidates": candidates,
        "executed_candidates": executed,
        "later_proposal_candidates": later,
        "categories": dict(sorted(categories.items())),
    }


def analyze_candidate_failures(schedule_path: Path, runs_root: Path) -> dict[str, Any]:
    schedule_path = schedule_path.resolve()
    schedule = read_json(schedule_path)
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Schedule must contain an episode list")
    runs = [
        _analyze_run(dict(episode), runs_root.resolve())
        for episode in sorted(episodes, key=lambda item: int(item["position"]))
    ]
    methods = {
        method: _aggregate([run for run in runs if run.get("method") == method])
        for method in sorted({str(run.get("method")) for run in runs})
    }
    return {
        "schema_version": "1.0.0",
        "schedule": {
            "path": schedule_path.name,
            "sha256": sha256_file(schedule_path),
        },
        "aggregate": _aggregate(runs),
        "methods": methods,
        "runs": runs,
    }
