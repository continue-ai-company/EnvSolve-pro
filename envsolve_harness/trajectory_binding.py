from __future__ import annotations

from pathlib import Path
from typing import Any

from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


SELECTION_POLICY = "last-recorded-verification-v1"


def _workspace_relative(path: Path, workspace_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()))
    except ValueError as exc:
        raise ValueError(f"Artifact is outside the workspace: {path}") from exc


def _source_root(episode: dict[str, Any], runs_root: Path) -> Path:
    return (
        runs_root
        / safe_name(str(episode["run_id"]))
        / safe_name(str(episode["case_id"]))
    ).resolve()


def _last_verification(events: list[dict[str, Any]], source_root: Path) -> dict[str, Any]:
    verifications = [
        event for event in events if event.get("event_type") == "verification_recorded"
    ]
    if not verifications:
        raise ValueError(f"Run has no recorded verification: {source_root}")
    return max(verifications, key=lambda event: int(event["sequence"]))


def _candidate_proposal(
    events: list[dict[str, Any]], candidate_id: str, source_root: Path
) -> dict[str, Any]:
    matches = [
        event
        for event in events
        if event.get("event_type") == "action_proposed"
        and str((event.get("payload") or {}).get("action_id")) == candidate_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one proposal for {candidate_id} in {source_root}, got {len(matches)}"
        )
    return matches[0]


def _script_source(
    proposal: dict[str, Any], verification: dict[str, Any], source_root: Path
) -> tuple[Path, str, int]:
    proposal_payload = proposal.get("payload") or {}
    artifact = proposal_payload.get("command_artifact") or {}
    relative_path = artifact.get("path")
    claimed_sha256 = artifact.get("sha256")
    if not isinstance(relative_path, str) or not isinstance(claimed_sha256, str):
        raise ValueError("Selected proposal has no content-addressed command artifact")

    raw_root = (source_root / "generation" / "raw-artifacts").resolve()
    script_path = (raw_root / relative_path).resolve()
    try:
        script_path.relative_to(raw_root)
    except ValueError as exc:
        raise ValueError(f"Command artifact escapes raw artifact root: {relative_path}") from exc
    if not script_path.is_file():
        raise ValueError(f"Selected command artifact does not exist: {script_path}")

    actual_sha256 = sha256_file(script_path)
    actual_size = script_path.stat().st_size
    claimed_size = artifact.get("size_bytes")
    if claimed_size is not None and int(claimed_size) != actual_size:
        raise ValueError("Candidate size disagrees between proposal and artifact")
    verification_sha256 = str(
        ((verification.get("payload") or {}).get("details") or {}).get(
            "candidate_sha256"
        )
        or ""
    )
    if len({claimed_sha256, verification_sha256, actual_sha256}) != 1:
        raise ValueError(
            "Candidate hashes disagree between proposal, verification, and artifact"
        )
    return script_path, actual_sha256, actual_size


def freeze_last_verified_candidates(
    schedule_path: Path,
    runs_root: Path,
    scripts_dir: Path,
    workspace_root: Path,
    *,
    calibration_run_prefix: str,
) -> dict[str, Any]:
    schedule_path = schedule_path.resolve()
    runs_root = runs_root.resolve()
    scripts_dir = scripts_dir.resolve()
    workspace_root = workspace_root.resolve()
    _workspace_relative(scripts_dir, workspace_root)
    schedule = read_json(schedule_path)
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("Schedule must contain a non-empty episode list")

    scripts_dir.mkdir(parents=True, exist_ok=True)
    bindings: list[dict[str, Any]] = []
    seen_run_ids: set[str] = set()
    for episode in sorted(episodes, key=lambda item: int(item["position"])):
        source_root = _source_root(episode, runs_root)
        episode_path = source_root / "generation" / "episode.jsonl"
        if not episode_path.is_file():
            raise ValueError(f"Run has no episode evidence: {source_root}")
        events = read_jsonl(episode_path)
        verification = _last_verification(events, source_root)
        details = (verification.get("payload") or {}).get("details") or {}
        candidate_id = str(details.get("candidate_id") or "")
        if not candidate_id:
            raise ValueError(f"Selected verification has no candidate ID: {source_root}")
        proposal = _candidate_proposal(events, candidate_id, source_root)
        script_source, script_sha256, size_bytes = _script_source(
            proposal, verification, source_root
        )

        position = int(episode["position"])
        calibration_run_id = f"{calibration_run_prefix}-{position:02d}"
        if calibration_run_id in seen_run_ids:
            raise ValueError(f"Duplicate calibration run ID: {calibration_run_id}")
        seen_run_ids.add(calibration_run_id)
        target_name = (
            f"{position:02d}-{safe_name(str(episode['method']))}-"
            f"{safe_name(candidate_id)}.sh"
        )
        target_path = scripts_dir / target_name
        target_path.write_bytes(script_source.read_bytes())
        if sha256_file(target_path) != script_sha256:
            raise ValueError(f"Frozen script copy hash mismatch: {target_path}")

        bindings.append(
            {
                **{
                    key: episode.get(key)
                    for key in (
                        "position",
                        "pair_index",
                        "case_id",
                        "run_id",
                        "method",
                        "seed",
                    )
                },
                "source_episode": {
                    "path": _workspace_relative(episode_path, workspace_root),
                    "sha256": sha256_file(episode_path),
                },
                "selected_candidate": {
                    "candidate_id": candidate_id,
                    "proposal_sequence": int(proposal["sequence"]),
                    "verification_sequence": int(verification["sequence"]),
                    "internal_passed": (verification.get("payload") or {}).get("passed"),
                    "internal_summary": str(details.get("summary") or ""),
                    "source_script_path": _workspace_relative(
                        script_source, workspace_root
                    ),
                    "frozen_script_path": _workspace_relative(
                        target_path, workspace_root
                    ),
                    "script_sha256": script_sha256,
                    "size_bytes": size_bytes,
                },
                "calibration_run_id": calibration_run_id,
            }
        )

    return {
        "schema_version": "1.0.0",
        "selection_policy": {
            "id": SELECTION_POLICY,
            "rule": "maximum event sequence among verification_recorded events",
            "uses_official_outcome": False,
            "uses_repository_specific_log_text": False,
        },
        "source_schedule": {
            "path": _workspace_relative(schedule_path, workspace_root),
            "sha256": sha256_file(schedule_path),
        },
        "count": len(bindings),
        "bindings": bindings,
    }
