from __future__ import annotations

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
