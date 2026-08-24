from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Mapping

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json
from envsolve_harness.results import summarize_schedule
from envsolve_harness.storage.artifacts import safe_name


_SCIENTIFIC_FAILURE_TERMINALS = frozenset(
    {
        "official_fail",
        "generation_failed",
        "candidate_limit",
        "budget_exhausted",
        "context_contract_exhausted",
        "execution_timeout_unknown",
    }
)


def _run_root(runs_root: Path, run_id: str, case_id: str) -> Path:
    return runs_root.resolve() / safe_name(run_id) / safe_name(case_id)


def _run_metrics(
    runs_root: Path,
    run_id: str,
    case_id: str,
) -> dict[str, Any] | None:
    root = _run_root(runs_root, run_id, case_id)
    generation_path = root / "generation" / "result.json"
    manifest_path = root / "manifest.json"
    if not generation_path.is_file() or not manifest_path.is_file():
        return None
    generation = read_json(generation_path).get("metadata") or {}
    manifest_result = read_json(manifest_path).get("result") or {}
    token_usage = generation.get("token_usage") or {}
    started_at = generation.get("started_at")
    finished_at = generation.get("finished_at")
    generation_seconds: float | None = None
    if isinstance(started_at, str) and isinstance(finished_at, str):
        generation_seconds = (
            datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
        ).total_seconds()
    return {
        "generation_seconds": generation_seconds,
        "official_seconds": manifest_result.get("execution_time"),
        "model_requests": generation.get("model_requests"),
        "token_usage": {
            key: token_usage.get(key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        },
        "tool_counts": generation.get("tool_counts"),
        "replay_status_counts": generation.get("replay_status_counts"),
        "verifier_handoff": generation.get("verifier_handoff"),
    }


def _adjudicate_official_retry(
    source: Mapping[str, Any],
    retry_run_id: str,
    runs_root: Path,
) -> dict[str, Any]:
    source_terminal = source.get("descriptive_terminal")
    if source_terminal not in {"infrastructure_unknown", "evaluator_unknown"}:
        raise ValueError(
            f"Official retry cannot replace terminal {source_terminal!r} "
            f"for {source.get('run_id')}"
        )

    case_id = str(source["case_id"])
    root = _run_root(runs_root, retry_run_id, case_id)
    if not root.is_dir():
        raise ValueError(f"Official retry artifact root is missing: {root}")
    audit = audit_run(root)
    if not audit.valid:
        raise ValueError(
            f"Official retry artifact is invalid for {retry_run_id}: {audit.errors}"
        )

    manifest = read_json(root / "manifest.json")
    retry = read_json(root / "inputs" / "evaluation_retry.json")
    run = manifest.get("run") or {}
    case = manifest.get("case") or {}
    result = manifest.get("result") or {}
    identity_valid = (
        run.get("run_id") == retry_run_id
        and run.get("method") == source.get("method")
        and run.get("seed") == source.get("seed")
        and case.get("case_id") == case_id
        and retry.get("source_run_id") == source.get("run_id")
        and retry.get("source_case_id") == case_id
        and retry.get("source_method") == source.get("method")
        and retry.get("model_reexecuted") is False
        and retry.get("policy") == "single-exact-script-infrastructure-retry-v1"
    )
    if not identity_valid:
        raise ValueError(
            f"Official retry identity does not match source run {source.get('run_id')}"
        )
    if result.get("evaluation_completed") is not True or not isinstance(
        result.get("official_pass"), bool
    ):
        raise ValueError(f"Official retry has no completed outcome: {retry_run_id}")

    return {
        "run_id": retry_run_id,
        "artifact_root": str(root.relative_to(runs_root.resolve())),
        "infrastructure_signature": retry.get("infrastructure_signature"),
        "model_reexecuted": False,
        "evaluation_completed": True,
        "official_pass": result["official_pass"],
    }


def adjudicate_screen(
    schedule_path: Path,
    runs_root: Path,
    *,
    official_retries: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    schedule = read_json(schedule_path.resolve())
    summary = summarize_schedule(schedule_path, runs_root)
    retry_ids = dict(official_retries or {})
    expected_run_ids = {str(run["run_id"]) for run in summary["runs"]}
    unknown_retry_sources = sorted(set(retry_ids) - expected_run_ids)
    if unknown_retry_sources:
        raise ValueError(
            f"Official retries name unknown source runs: {unknown_retry_sources}"
        )

    records: list[dict[str, Any]] = []
    for source in summary["runs"]:
        terminal = str(source["descriptive_terminal"])
        if terminal in {"missing_artifacts", "incomplete"}:
            raise ValueError(
                f"Screen is incomplete at position {source.get('position')}: {terminal}"
            )

        source_run_id = str(source["run_id"])
        retry = None
        if source_run_id in retry_ids:
            retry = _adjudicate_official_retry(
                source, retry_ids.pop(source_run_id), runs_root
            )

        eligible = bool(source["scientifically_eligible"])
        if retry is not None:
            final_class = "official_pass" if retry["official_pass"] else "official_fail"
            official_pass_at_1: bool | None = bool(retry["official_pass"])
            scientifically_eligible = eligible
        elif eligible and terminal == "official_pass":
            final_class = "official_pass"
            official_pass_at_1 = True
            scientifically_eligible = True
        elif eligible and terminal in _SCIENTIFIC_FAILURE_TERMINALS:
            final_class = "official_fail" if terminal == "official_fail" else "agent_noncompletion"
            official_pass_at_1 = False
            scientifically_eligible = True
        else:
            final_class = "infrastructure_or_measurement_censored"
            official_pass_at_1 = None
            scientifically_eligible = False

        records.append(
            {
                "position": source.get("position"),
                "case_id": source["case_id"],
                "source_run_id": source_run_id,
                "source_terminal": terminal,
                "source_artifact_integrity_valid": source[
                    "artifact_integrity_valid"
                ],
                "source_scientifically_eligible": eligible,
                "official_retry": retry,
                "final_class": final_class,
                "scientifically_eligible": scientifically_eligible,
                "official_pass_at_1": official_pass_at_1,
                "bad_case": scientifically_eligible
                and official_pass_at_1 is False,
            }
        )

    if retry_ids:
        raise AssertionError(f"Unconsumed retry mappings: {sorted(retry_ids)}")
    eligible_records = [item for item in records if item["scientifically_eligible"]]
    bad_case_ids = [str(item["case_id"]) for item in records if item["bad_case"]]
    return {
        "schema_version": "1.0.0",
        "study_id": schedule.get("study_id"),
        "screen_schedule": str(schedule_path),
        "counts": {
            "scheduled": len(records),
            "scientifically_eligible": len(eligible_records),
            "official_pass": sum(
                item["official_pass_at_1"] is True for item in eligible_records
            ),
            "official_fail": len(bad_case_ids),
            "censored": len(records) - len(eligible_records),
            "official_only_retries": sum(
                item["official_retry"] is not None for item in records
            ),
        },
        "records": records,
        "bad_case_ids": bad_case_ids,
    }


def _paired_counts(
    pairs: list[dict[str, Any]],
    outcome_key: str,
) -> dict[str, int]:
    counts = {
        "pairs": len(pairs),
        "eligible_pairs": 0,
        "censored_pairs": 0,
        "control_passes": 0,
        "treatment_passes": 0,
        "both_pass": 0,
        "control_only_pass": 0,
        "treatment_only_pass": 0,
        "neither_pass": 0,
    }
    for pair in pairs:
        control = pair["control"][outcome_key]
        treatment = pair["treatment"][outcome_key]
        if not isinstance(control, bool) or not isinstance(treatment, bool):
            counts["censored_pairs"] += 1
            continue
        counts["eligible_pairs"] += 1
        counts["control_passes"] += int(control)
        counts["treatment_passes"] += int(treatment)
        if control and treatment:
            counts["both_pass"] += 1
        elif control:
            counts["control_only_pass"] += 1
        elif treatment:
            counts["treatment_only_pass"] += 1
        else:
            counts["neither_pass"] += 1
    return counts


def adjudicate_paired_schedule(
    schedule_path: Path,
    runs_root: Path,
    *,
    official_retries: Mapping[str, str] | None = None,
    protocol_invalid: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    schedule = read_json(schedule_path.resolve())
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Paired schedule must contain an episode list")
    summary = summarize_schedule(schedule_path, runs_root)
    retry_ids = dict(official_retries or {})
    invalid_reasons = dict(protocol_invalid or {})
    expected_run_ids = {str(run["run_id"]) for run in summary["runs"]}
    unknown_retry_sources = sorted(set(retry_ids) - expected_run_ids)
    if unknown_retry_sources:
        raise ValueError(
            f"Official retries name unknown source runs: {unknown_retry_sources}"
        )
    unknown_invalid_runs = sorted(set(invalid_reasons) - expected_run_ids)
    if unknown_invalid_runs:
        raise ValueError(
            f"Protocol-invalid reasons name unknown runs: {unknown_invalid_runs}"
        )

    episode_by_run_id = {str(item["run_id"]): item for item in episodes}
    records: list[dict[str, Any]] = []
    for source in summary["runs"]:
        terminal = str(source["descriptive_terminal"])
        if terminal in {"missing_artifacts", "incomplete"}:
            raise ValueError(
                f"Paired schedule is incomplete at position "
                f"{source.get('position')}: {terminal}"
            )
        run_id = str(source["run_id"])
        episode = episode_by_run_id[run_id]
        retry = None
        if run_id in retry_ids:
            retry = _adjudicate_official_retry(
                source, retry_ids.pop(run_id), runs_root
            )

        eligible = bool(source["scientifically_eligible"])
        if retry is not None:
            official_pass: bool | None = bool(retry["official_pass"])
            official_eligible = eligible
            final_class = "official_pass" if official_pass else "official_fail"
        elif eligible and terminal == "official_pass":
            official_pass = True
            official_eligible = True
            final_class = "official_pass"
        elif eligible and terminal in _SCIENTIFIC_FAILURE_TERMINALS:
            official_pass = False
            official_eligible = True
            final_class = (
                "official_fail" if terminal == "official_fail" else "agent_noncompletion"
            )
        else:
            official_pass = None
            official_eligible = False
            final_class = "infrastructure_or_measurement_censored"

        protocol_reason = invalid_reasons.pop(run_id, None)
        protocol_pass = False if protocol_reason is not None else official_pass
        if protocol_reason is not None:
            final_class = "protocol_invalid"
        records.append(
            {
                "position": source.get("position"),
                "pair_index": episode.get("pair_index"),
                "pair_id": episode.get("pair_id"),
                "pair_position": episode.get("pair_position"),
                "arm": episode.get("arm"),
                "case_id": source["case_id"],
                "source_run_id": run_id,
                "source_terminal": terminal,
                "source_artifact_integrity_valid": source[
                    "artifact_integrity_valid"
                ],
                "source_scientifically_eligible": eligible,
                "official_retry": retry,
                "official_scientifically_eligible": official_eligible,
                "official_pass": official_pass,
                "protocol_invalid_reason": protocol_reason,
                "protocol_compliant_pass": protocol_pass,
                "final_class": final_class,
                "metrics": _run_metrics(
                    runs_root, run_id, str(source["case_id"])
                ),
            }
        )

    if retry_ids:
        raise AssertionError(f"Unconsumed retry mappings: {sorted(retry_ids)}")
    if invalid_reasons:
        raise AssertionError(
            f"Unconsumed protocol-invalid reasons: {sorted(invalid_reasons)}"
        )

    grouped: dict[int, dict[str, Any]] = {}
    for record in records:
        pair_index = record.get("pair_index")
        arm = record.get("arm")
        if not isinstance(pair_index, int) or arm not in {"S-OBS", "H-VH"}:
            raise ValueError(
                f"Run {record['source_run_id']} has invalid pair identity"
            )
        pair = grouped.setdefault(
            pair_index,
            {
                "pair_index": pair_index,
                "pair_id": record.get("pair_id"),
                "case_id": record["case_id"],
            },
        )
        key = "control" if arm == "S-OBS" else "treatment"
        if key in pair:
            raise ValueError(f"Pair {pair_index} repeats {key} arm")
        pair[key] = record

    pairs = [grouped[index] for index in sorted(grouped)]
    for pair in pairs:
        if "control" not in pair or "treatment" not in pair:
            raise ValueError(f"Pair {pair['pair_index']} lacks an arm")
        if pair["control"]["case_id"] != pair["treatment"]["case_id"]:
            raise ValueError(f"Pair {pair['pair_index']} mixes cases")

    return {
        "schema_version": "1.0.0",
        "study_id": schedule.get("study_id"),
        "paired_schedule": str(schedule_path),
        "counts": {
            "scheduled_runs": len(records),
            "pairs": len(pairs),
            "official_only_retries": sum(
                item["official_retry"] is not None for item in records
            ),
            "protocol_invalid_runs": sum(
                item["protocol_invalid_reason"] is not None for item in records
            ),
        },
        "official_paired": _paired_counts(pairs, "official_pass"),
        "protocol_compliant_paired": _paired_counts(
            pairs, "protocol_compliant_pass"
        ),
        "records": records,
        "pairs": pairs,
    }


def _case_slug(case_id: str) -> str:
    repository = case_id.split("@", 1)[0].rsplit("__", 1)[-1]
    return re.sub(r"[^a-zA-Z0-9]+", "-", repository).strip("-").lower()


def build_paired_schedule(
    screen_result: Mapping[str, Any],
    screen_schedule: Mapping[str, Any],
) -> dict[str, Any]:
    case_ids = screen_result.get("bad_case_ids")
    if not isinstance(case_ids, list) or not case_ids:
        raise ValueError("Screen result contains no bad cases for a paired study")

    episodes: list[dict[str, Any]] = []
    position = 0
    for pair_index, case_id_value in enumerate(case_ids, start=1):
        case_id = str(case_id_value)
        pair_id = f"verifier-handoff-screen-{pair_index:02d}-{_case_slug(case_id)}"
        seed = 650000 + pair_index
        arms = (
            (
                "S-OBS",
                "envsolve-pro-v2-scheduled-observation",
                "envsolve-pro-scheduled-compatibility-observation",
            ),
            ("H-VH", "envsolve-pro-v2-verifier-handoff", "envsolve-pro-verifier-triggered-handoff"),
        )
        if pair_index % 2 == 0:
            arms = tuple(reversed(arms))
        for pair_position, (arm, runner, method) in enumerate(arms, start=1):
            position += 1
            episodes.append(
                {
                    "position": position,
                    "pair_index": pair_index,
                    "pair_id": pair_id,
                    "pair_position": pair_position,
                    "case_id": case_id,
                    "arm": arm,
                    "runner": runner,
                    "method": method,
                    "seed": seed,
                    "run_id": (
                        f"pro-v2-handoff-v1-paired-{position:02d}-"
                        f"{_case_slug(case_id)}-{arm}"
                    ),
                }
            )

    return {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-v2-verifier-handoff-v1-paired-screen-bad-cases",
        "source_screen_study_id": screen_result.get("study_id"),
        "case_file": screen_schedule.get("case_file"),
        "case_file_sha256": screen_schedule.get("case_file_sha256"),
        "episode_timeout_seconds": screen_schedule.get("episode_timeout_seconds"),
        "model": screen_schedule.get("model"),
        "required_environment": screen_schedule.get("required_environment"),
        "episodes": episodes,
    }
