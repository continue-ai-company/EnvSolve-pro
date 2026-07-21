from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json
from envsolve_harness.eligibility import assess_scientific_eligibility
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


_CORE_EVIDENCE_PATHS = (
    "manifest.json",
    "status.json",
    "inputs/case.json",
    "scripts/bootstrap.sh",
    "generation/result.json",
    "generation/budget_ledger.json",
    "generation/episode.jsonl",
    "generation/episode_snapshot.json",
    "generation/trajectory.json",
    "generation/trajectory.jsonl",
    "runtime/heartbeat.jsonl",
    "evaluation/official_attempt.json",
    "evaluation/result.json",
)


def _artifact_hashes(root: Path) -> dict[str, str]:
    paths = [root / relative for relative in _CORE_EVIDENCE_PATHS]
    result_path = root / "evaluation" / "result.json"
    if result_path.is_file():
        raw = read_json(result_path).get("raw_result_path")
        if isinstance(raw, str):
            candidate = root / raw
            try:
                candidate.resolve().relative_to(root.resolve())
            except ValueError:
                pass
            else:
                paths.append(candidate)
    return {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(set(paths))
        if path.is_file()
    }


def _bundle_hash(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, file_hash in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_hash))
    return digest.hexdigest()


def _resources(root: Path) -> dict[str, Any] | None:
    path = root / "generation" / "budget_ledger.json"
    if not path.is_file():
        return None
    usage = read_json(path).get("usage") or {}
    return {
        key: usage.get(key)
        for key in (
            "candidates",
            "requests_started",
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "total_tokens",
            "environments",
            "commands",
            "elapsed_wall_clock_seconds",
        )
    }


def _descriptive_terminal(manifest: dict[str, Any]) -> tuple[str, bool | None]:
    result = manifest.get("result")
    if isinstance(result, dict) and result.get("evaluation_completed") is True:
        passed = result.get("official_pass") is True
        return ("official_pass" if passed else "official_fail", passed)
    solver = manifest.get("solver") or {}
    metadata = solver.get("metadata") or {}
    error = str(solver.get("error") or "").lower()
    budget = metadata.get("online_budget") or {}
    exhausted = set(budget.get("exhausted_limits") or [])
    if "candidates" in exhausted:
        return "candidate_limit", None
    if exhausted:
        return "budget_exhausted", None
    if (
        metadata.get("infrastructure_signature")
        or metadata.get("infrastructure_stage")
        or "infrastructure" in error
        or "timeout" in error
        or "connectionerror" in error
    ):
        return "infrastructure_unknown", None
    if solver.get("generation_completed") is False:
        return "generation_failed", None
    if isinstance(result, dict):
        return "evaluator_unknown", None
    return "incomplete", None


def _summarize_episode(
    episode: dict[str, Any],
    runs_root: Path,
) -> dict[str, Any]:
    root = runs_root / safe_name(str(episode["run_id"])) / safe_name(str(episode["case_id"]))
    if not root.is_dir():
        return {
            **{key: episode.get(key) for key in ("position", "pair_index", "case_id", "run_id", "method", "seed")},
            "artifact_root": str(root.relative_to(runs_root)),
            "artifact_integrity_valid": False,
            "scientifically_eligible": False,
            "descriptive_terminal": "missing_artifacts",
            "official_pass": None,
            "errors": ["run artifact root is missing"],
            "artifact_hashes": {},
            "artifact_bundle_sha256": _bundle_hash({}),
            "resources": None,
        }
    integrity = audit_run(root)
    eligibility = assess_scientific_eligibility(root)
    manifest = read_json(root / "manifest.json")
    manifest_run = manifest.get("run") or {}
    manifest_case = manifest.get("case") or {}
    identity_valid = (
        manifest_run.get("run_id") == episode.get("run_id")
        and manifest_run.get("method") == episode.get("method")
        and manifest_run.get("seed") == episode.get("seed")
        and manifest_case.get("case_id") == episode.get("case_id")
    )
    terminal, official_pass = _descriptive_terminal(manifest)
    hashes = _artifact_hashes(root)
    errors = list(integrity.errors)
    if not identity_valid:
        errors.append("manifest identity does not match schedule episode")
    scientific = eligibility.eligible and identity_valid
    return {
        **{key: episode.get(key) for key in ("position", "pair_index", "case_id", "run_id", "method", "seed")},
        "artifact_root": str(root.relative_to(runs_root)),
        "artifact_integrity_valid": integrity.valid,
        "schedule_identity_valid": identity_valid,
        "scientifically_eligible": scientific,
        "eligibility": eligibility.to_dict(),
        "descriptive_terminal": terminal,
        "official_pass": official_pass,
        "errors": errors,
        "artifact_hashes": hashes,
        "artifact_bundle_sha256": _bundle_hash(hashes),
        "resources": _resources(root),
    }


def _paired_aggregate(
    runs: list[dict[str, Any]],
    treatment_method: str,
    control_method: str,
) -> dict[str, int]:
    pairs: dict[int, dict[str, dict[str, Any]]] = {}
    for run in runs:
        if not isinstance(run.get("pair_index"), int):
            continue
        methods = pairs.setdefault(int(run["pair_index"]), {})
        method = str(run["method"])
        if method in methods:
            raise ValueError(f"Pair {run['pair_index']} repeats method {method!r}")
        methods[method] = run
    counts = {
        "pairs": len(pairs),
        "eligible_pairs": 0,
        "censored_pairs": 0,
        "treatment_only_pass": 0,
        "control_only_pass": 0,
        "both_pass": 0,
        "neither_pass": 0,
    }
    for pair_index, methods in pairs.items():
        if treatment_method not in methods or control_method not in methods:
            raise ValueError(f"Pair {pair_index} lacks a treatment or control episode")
        treatment = methods[treatment_method]
        control = methods[control_method]
        if not (
            treatment["scientifically_eligible"]
            and control["scientifically_eligible"]
            and isinstance(treatment["official_pass"], bool)
            and isinstance(control["official_pass"], bool)
        ):
            counts["censored_pairs"] += 1
            continue
        counts["eligible_pairs"] += 1
        if treatment["official_pass"] and control["official_pass"]:
            counts["both_pass"] += 1
        elif treatment["official_pass"]:
            counts["treatment_only_pass"] += 1
        elif control["official_pass"]:
            counts["control_only_pass"] += 1
        else:
            counts["neither_pass"] += 1
    return counts


def _normalize_schedule_episode(
    episode: dict[str, Any],
    shared: dict[str, Any],
) -> dict[str, Any]:
    normalized = {**shared, **episode}
    if "pair_index" not in normalized and isinstance(normalized.get("pair"), int):
        normalized["pair_index"] = normalized["pair"]
    return normalized


def summarize_schedule(
    schedule_path: Path,
    runs_root: Path,
    *,
    treatment_method: str | None = None,
    control_method: str | None = None,
) -> dict[str, Any]:
    schedule_path = schedule_path.resolve()
    schedule = read_json(schedule_path)
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Schedule must contain an episode list")
    shared = schedule.get("shared") or {}
    if not isinstance(shared, dict):
        raise ValueError("Schedule shared settings must be an object")
    runs = [
        _summarize_episode(
            _normalize_schedule_episode(dict(episode), shared),
            runs_root.resolve(),
        )
        for episode in episodes
    ]
    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "schedule": {
            "path": schedule_path.name,
            "sha256": sha256_file(schedule_path),
            "case_file": schedule.get("case_file"),
            "case_file_sha256": schedule.get("case_file_sha256"),
        },
        "descriptive": {
            "runs": len(runs),
            "artifact_integrity_valid": sum(bool(run["artifact_integrity_valid"]) for run in runs),
            "official_pass": sum(run["official_pass"] is True for run in runs),
            "official_fail": sum(run["official_pass"] is False for run in runs),
        },
        "scientific": {
            "eligible_runs": sum(bool(run["scientifically_eligible"]) for run in runs),
            "excluded_runs": sum(not bool(run["scientifically_eligible"]) for run in runs),
            "official_pass": sum(
                run["scientifically_eligible"] and run["official_pass"] is True for run in runs
            ),
            "official_fail": sum(
                run["scientifically_eligible"] and run["official_pass"] is False for run in runs
            ),
        },
        "runs": runs,
    }
    if (treatment_method is None) != (control_method is None):
        raise ValueError("Treatment and control methods must be provided together")
    if treatment_method is not None and control_method is not None:
        summary["paired_scientific"] = {
            "treatment_method": treatment_method,
            "control_method": control_method,
            **_paired_aggregate(runs, treatment_method, control_method),
        }
    return summary
