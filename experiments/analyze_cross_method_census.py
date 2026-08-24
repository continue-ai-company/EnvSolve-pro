#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_json, read_jsonl, write_json
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


def _optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _effect_audit(verifier_details: dict[str, Any]) -> dict[str, Any]:
    direct = verifier_details.get("repository_effect_audit")
    if isinstance(direct, dict):
        return direct
    report = verifier_details.get("report_details")
    if isinstance(report, dict):
        nested = report.get("repository_effect_audit")
        if isinstance(nested, dict):
            return nested
    return {}


def candidate_verifications(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    for event in read_jsonl(path):
        if event.get("event_type") != "verification_recorded":
            continue
        payload = event.get("payload")
        details = payload.get("details") if isinstance(payload, dict) else None
        if not isinstance(details, dict):
            continue
        candidate_id = details.get("candidate_id")
        if not isinstance(candidate_id, str):
            continue
        verifier = details.get("verifier_details")
        if not isinstance(verifier, dict):
            verifier = {}
        assessment = details.get("candidate_assessment")
        if not isinstance(assessment, dict):
            assessment = {}
        audit = _effect_audit(verifier)
        result.append(
            {
                "candidate_id": candidate_id,
                "bootstrap_exit_code": details.get("bootstrap_exit_code"),
                "admissible": assessment.get("admissible"),
                "satisfied_constraints": assessment.get("satisfied_constraints"),
                "unknown_constraints": assessment.get("unknown_constraints"),
                "unresolved_constraints": assessment.get("unresolved_constraints"),
                "effect_valid": audit.get("valid"),
                "infrastructure_error": verifier.get("infrastructure_error"),
                "infrastructure_signature": verifier.get(
                    "infrastructure_signature"
                ),
            }
        )
    return result


def _elapsed_seconds(metadata: dict[str, Any]) -> float | None:
    started = metadata.get("started_at")
    finished = metadata.get("finished_at")
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    try:
        return (
            datetime.fromisoformat(finished) - datetime.fromisoformat(started)
        ).total_seconds()
    except ValueError:
        return None


def _resource_metrics(
    generation: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = generation.get("metadata") if isinstance(generation, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    online = metadata.get("online_budget")
    online_usage = online.get("usage") if isinstance(online, dict) else None
    ledger_usage = ledger.get("usage") if isinstance(ledger, dict) else None
    structured_usage = (
        ledger_usage
        if isinstance(ledger_usage, dict)
        else online_usage if isinstance(online_usage, dict) else None
    )
    codex_usage = metadata.get("token_usage")
    if not isinstance(codex_usage, dict):
        codex_usage = None
    command_trace = metadata.get("container_command_trace")
    if not isinstance(command_trace, dict):
        command_trace = {}
    return {
        "structured_usage": structured_usage,
        "codex_token_usage": codex_usage,
        "container_commands": command_trace.get("count"),
        "generation_wall_seconds": _elapsed_seconds(metadata),
    }


def _official_metrics(
    evaluation: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if evaluation is None:
        return None, []
    raw = evaluation.get("raw_metrics")
    metrics = raw if isinstance(raw, dict) else None
    modules: list[str] = []
    evidence = evaluation.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            if item.get("verifier_id") != "envbench-pyright-diagnostic":
                continue
            diagnostic = item.get("metrics")
            values = (
                diagnostic.get("missing_import_modules")
                if isinstance(diagnostic, dict)
                else None
            )
            if isinstance(values, list):
                modules = sorted(str(value) for value in values)
            break
    return metrics, modules


def _terminal(
    generation: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
) -> str:
    if evaluation is not None and evaluation.get("evaluation_completed") is True:
        return (
            "official_pass"
            if evaluation.get("official_pass") is True
            else "official_fail"
        )
    if evaluation is not None:
        metadata = evaluation.get("metadata")
        termination = metadata.get("termination") if isinstance(metadata, dict) else None
        if isinstance(termination, dict) and isinstance(termination.get("kind"), str):
            return str(termination["kind"])
    if generation is None:
        return "missing"
    if generation.get("generation_completed") is not True:
        error = str(generation.get("error") or "").lower()
        if any(
            marker in error
            for marker in ("connection", "timeout", "infrastructure", "network")
        ):
            return "infrastructure_unknown"
        return "generation_failed"
    return "evaluation_missing"


def _terminal_stage(
    generation: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
) -> str:
    terminal = _terminal(generation, evaluation)
    if terminal == "infrastructure_unknown":
        return "infrastructure_unknown"
    if generation is None or generation.get("generation_completed") is not True:
        return "candidate_formation"
    if evaluation is None or evaluation.get("evaluation_completed") is not True:
        return "evaluation_unknown"
    if evaluation.get("official_pass") is True:
        return "success"
    raw = evaluation.get("raw_metrics")
    if not isinstance(raw, dict):
        return "official_failure_unparsed"
    exit_code = raw.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return "target_bootstrap"
    issues_count = raw.get("issues_count")
    if isinstance(issues_count, int) and issues_count > 0:
        return "public_goal_residual"
    return "official_failure_unparsed"


def _final_program(root: Path) -> dict[str, Any] | None:
    path = root / "scripts/generated.sh"
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8")
    return {
        "path": "scripts/generated.sh",
        "sha256": sha256_file(path),
        "nonblank_line_count": sum(bool(line.strip()) for line in content.splitlines()),
    }


def collect_episode(
    episode: dict[str, Any],
    runs_root: Path,
    *,
    actual_run_id: str | None = None,
    generation_run_id: str | None = None,
    evaluation_run_id: str | None = None,
) -> dict[str, Any]:
    scheduled_run_id = str(episode["run_id"])
    if actual_run_id is not None and (
        generation_run_id is not None or evaluation_run_id is not None
    ):
        raise ValueError(
            "actual_run_id cannot be combined with stage-specific attempt IDs"
        )
    selected_generation_run_id = (
        generation_run_id or actual_run_id or scheduled_run_id
    )
    selected_evaluation_run_id = (
        evaluation_run_id or actual_run_id or scheduled_run_id
    )
    case_id = str(episode["case_id"])
    generation_root = (
        runs_root / safe_name(selected_generation_run_id) / safe_name(case_id)
    )
    evaluation_root = (
        runs_root / safe_name(selected_evaluation_run_id) / safe_name(case_id)
    )
    generation = _optional_json(generation_root / "generation/result.json")
    evaluation = _optional_json(evaluation_root / "evaluation/result.json")
    ledger = _optional_json(generation_root / "generation/budget_ledger.json")
    official_metrics, missing_modules = _official_metrics(evaluation)
    candidates = candidate_verifications(
        generation_root / "generation/episode.jsonl"
    )

    selected_candidate = None
    if generation is not None:
        metadata = generation.get("metadata")
        episode_metadata = (
            metadata.get("episode") if isinstance(metadata, dict) else None
        )
        accepted = (
            episode_metadata.get("accepted_candidate")
            if isinstance(episode_metadata, dict)
            else None
        )
        if isinstance(accepted, dict):
            selected_candidate = accepted.get("candidate_id")

    generation_evidence_paths = (
        "generation/result.json",
        "generation/budget_ledger.json",
        "generation/episode.jsonl",
        "generation/trajectory.jsonl",
        "scripts/generated.sh",
    )
    evidence = {
        relative: sha256_file(generation_root / relative)
        for relative in generation_evidence_paths
        if (generation_root / relative).is_file()
    }
    evaluation_result_path = evaluation_root / "evaluation/result.json"
    if evaluation_result_path.is_file():
        evidence["evaluation/result.json"] = sha256_file(evaluation_result_path)
    return {
        "case_id": case_id,
        "case_index": episode.get("case_index"),
        "method": episode.get("method"),
        "method_id": episode.get("method_id"),
        "model": episode.get("model"),
        "scheduled_run_id": scheduled_run_id,
        "actual_run_id": selected_generation_run_id,
        "generation_run_id": selected_generation_run_id,
        "evaluation_run_id": selected_evaluation_run_id,
        "artifact_root": str(generation_root),
        "evaluation_artifact_root": str(evaluation_root),
        "artifact_exists": generation_root.is_dir() or evaluation_root.is_dir(),
        "terminal": _terminal(generation, evaluation),
        "terminal_stage": _terminal_stage(generation, evaluation),
        "generation_completed": (
            generation.get("generation_completed")
            if generation is not None
            else None
        ),
        "evaluation_completed": (
            evaluation.get("evaluation_completed")
            if evaluation is not None
            else None
        ),
        "official_pass": (
            evaluation.get("official_pass") if evaluation is not None else None
        ),
        "official_metrics": official_metrics,
        "missing_import_modules": missing_modules,
        "final_program": _final_program(generation_root),
        "resources": _resource_metrics(generation, ledger),
        "selected_candidate_id": selected_candidate,
        "candidate_verifications": candidates,
        "evidence_sha256": evidence,
    }


def aggregate(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    by_method: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_method.setdefault(str(record["method_id"]), []).append(record)
    return {
        method: {
            "expected_cases": len(items),
            "artifact_cases": sum(item["artifact_exists"] for item in items),
            "officially_evaluated": sum(
                item["evaluation_completed"] is True for item in items
            ),
            "official_passes": sum(item["official_pass"] is True for item in items),
            "terminal_counts": dict(
                sorted(Counter(str(item["terminal"]) for item in items).items())
            ),
            "terminal_stage_counts": dict(
                sorted(
                    Counter(str(item["terminal_stage"]) for item in items).items()
                )
            ),
        }
        for method, items in sorted(by_method.items())
    }


def analyze(
    schedule_paths: list[Path],
    run_roots: list[Path],
    *,
    attempt_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(schedule_paths) != len(run_roots):
        raise ValueError("Each schedule requires one corresponding run root")
    overrides = attempt_overrides or {}
    records: list[dict[str, Any]] = []
    schedules: list[dict[str, str]] = []
    identities: set[tuple[str, str]] = set()
    for schedule_path, run_root in zip(schedule_paths, run_roots):
        schedule = read_json(schedule_path)
        schedules.append(
            {
                "path": str(schedule_path),
                "sha256": sha256_file(schedule_path),
                "run_root": str(run_root),
            }
        )
        for episode in schedule["episodes"]:
            identity = (str(episode["method_id"]), str(episode["case_id"]))
            if identity in identities:
                raise ValueError(f"Duplicate method-case identity: {identity}")
            identities.add(identity)
            scheduled_run_id = str(episode["run_id"])
            override = overrides.get(scheduled_run_id)
            generation_run_id = None
            evaluation_run_id = None
            actual_run_id = None
            if isinstance(override, str):
                actual_run_id = override
            elif isinstance(override, dict):
                unknown = set(override) - {
                    "generation_run_id",
                    "evaluation_run_id",
                }
                if unknown:
                    raise ValueError(
                        f"Unknown attempt override fields for {scheduled_run_id}: "
                        f"{sorted(unknown)}"
                    )
                generation_run_id = override.get("generation_run_id")
                evaluation_run_id = override.get("evaluation_run_id")
                for value in (generation_run_id, evaluation_run_id):
                    if value is not None and (
                        not isinstance(value, str) or not value.strip()
                    ):
                        raise ValueError(
                            f"Attempt IDs for {scheduled_run_id} must be nonempty strings"
                        )
            elif override is not None:
                raise ValueError(
                    f"Attempt override for {scheduled_run_id} must be a string or object"
                )
            records.append(
                collect_episode(
                    episode,
                    run_root,
                    actual_run_id=actual_run_id,
                    generation_run_id=generation_run_id,
                    evaluation_run_id=evaluation_run_id,
                )
            )
    records.sort(
        key=lambda item: (
            int(item["case_index"] or sys.maxsize),
            str(item["method_id"]),
        )
    )
    return {
        "schema_version": "1.0.0",
        "analysis_role": "measurement-only evidence matrix",
        "classification_policy": (
            "No automatic earliest-divergence classification; causal labels require "
            "separate evidence-linked annotations."
        ),
        "schedules": schedules,
        "aggregate": aggregate(records),
        "records": records,
    }


def load_attempt_overrides(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError("Attempt override input must be a JSON object")
    nested = value.get("attempt_overrides")
    overrides = nested if nested is not None else value
    if not isinstance(overrides, dict):
        raise ValueError("attempt_overrides must be a JSON object")
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a method-neutral evidence matrix for a frozen census."
    )
    parser.add_argument("--schedule", type=Path, action="append", required=True)
    parser.add_argument("--run-root", type=Path, action="append", required=True)
    parser.add_argument("--attempt-overrides", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    overrides = (
        load_attempt_overrides(args.attempt_overrides)
        if args.attempt_overrides
        else {}
    )
    result = analyze(
        [path.resolve() for path in args.schedule],
        [path.resolve() for path in args.run_root],
        attempt_overrides=overrides,
    )
    write_json(args.output, result)
    print(json.dumps(result["aggregate"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
