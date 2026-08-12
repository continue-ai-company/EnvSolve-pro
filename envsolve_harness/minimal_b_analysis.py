from __future__ import annotations

from collections import Counter
from datetime import datetime
from math import comb
from pathlib import Path
from statistics import mean, median
from typing import Any

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


def _elapsed_seconds(metadata: dict[str, Any]) -> float | None:
    started_at = metadata.get("started_at")
    finished_at = metadata.get("finished_at")
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (finish - start).total_seconds()


def _progress_outcome(project_root: Path, episode: dict[str, Any]) -> dict[str, Any]:
    path = project_root / str(episode["progress_path"])
    progress = read_json(path)
    matches = [
        item
        for item in progress.get("outcomes", [])
        if isinstance(item, dict) and item.get("run_id") == episode["run_id"]
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one progress outcome for {episode['run_id']!r}, found {len(matches)}"
        )
    outcome = matches[0]
    for key in ("case_id", "method", "seed"):
        if outcome.get(key) != episode.get(key):
            raise ValueError(f"Progress {key} mismatch for {episode['run_id']!r}")
    return outcome


def _token_resources(metadata: dict[str, Any]) -> dict[str, int | None]:
    usage = metadata.get("token_usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = (
        input_tokens + output_tokens
        if isinstance(input_tokens, int) and isinstance(output_tokens, int)
        else None
    )
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": usage.get("cached_input_tokens"),
        "output_tokens": output_tokens,
        "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
        "total_tokens": total_tokens,
    }


def _episode_result(
    project_root: Path,
    runs_root: Path,
    episode: dict[str, Any],
) -> dict[str, Any]:
    artifact_root = (
        runs_root
        / safe_name(str(episode["run_id"]))
        / safe_name(str(episode["case_id"]))
    )
    manifest_path = artifact_root / "manifest.json"
    generation_path = artifact_root / "generation" / "result.json"
    evaluation_path = artifact_root / "evaluation" / "result.json"
    bootstrap_path = artifact_root / "scripts" / "bootstrap.sh"
    command_trace_path = artifact_root / "generation" / "container-commands.jsonl"
    if not manifest_path.is_file() or not generation_path.is_file():
        raise ValueError(f"Required artifacts are missing: {artifact_root}")

    manifest = read_json(manifest_path)
    generation = read_json(generation_path)
    metadata = generation.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    manifest_run = manifest.get("run") or {}
    manifest_case = manifest.get("case") or {}
    for key in ("run_id", "method", "seed"):
        if manifest_run.get(key) != episode.get(key):
            raise ValueError(f"Manifest {key} mismatch for {episode['run_id']!r}")
    if manifest_case.get("case_id") != episode.get("case_id"):
        raise ValueError(f"Manifest case mismatch for {episode['run_id']!r}")

    evaluation = read_json(evaluation_path) if evaluation_path.is_file() else None
    official_pass = (
        evaluation.get("official_pass")
        if isinstance(evaluation, dict)
        and isinstance(evaluation.get("official_pass"), bool)
        else None
    )
    progress = _progress_outcome(project_root, episode)
    command_trace = metadata.get("container_command_trace") or {}
    if not isinstance(command_trace, dict):
        command_trace = {}
    minimal_b = metadata.get("minimal_b") or {}
    if not isinstance(minimal_b, dict):
        minimal_b = {}
    replay_trace = minimal_b.get("replay_trace") or {}
    if not isinstance(replay_trace, dict):
        replay_trace = {}
    evaluation_metadata = (
        evaluation.get("metadata") or {} if isinstance(evaluation, dict) else {}
    )
    raw_metrics = (
        evaluation.get("raw_metrics") or {} if isinstance(evaluation, dict) else {}
    )
    candidate_validation = metadata.get("candidate_validation") or {}
    repository_integrity = metadata.get("repository_integrity") or {}
    audit = audit_run(artifact_root)

    terminal = "official_pass" if official_pass is True else "official_fail"
    if evaluation is None:
        terminal = (
            "generation_failed"
            if generation.get("generation_completed") is False
            else "evaluator_not_reached"
        )
    return {
        **{
            key: episode.get(key)
            for key in (
                "pair_index",
                "position",
                "repository",
                "case_id",
                "run_id",
                "condition",
                "method",
                "seed",
            )
        },
        "artifact_root": str(artifact_root),
        "artifact_integrity": audit.to_dict(),
        "generation_completed": generation.get("generation_completed") is True,
        "official_evaluator_reached": evaluation is not None,
        "official_pass": official_pass,
        "official_pass_at_1": official_pass is True,
        "terminal": terminal,
        "candidate_policy": {
            "accepted": candidate_validation.get("accepted"),
            "policy_id": candidate_validation.get("policy_id"),
            "reason": candidate_validation.get("reason"),
        },
        "repository_integrity_valid": repository_integrity.get("valid"),
        "semantic_adjudication": episode.get("semantic_adjudication"),
        "resources": {
            **_token_resources(metadata),
            "commands": command_trace.get("count"),
            "successful_commands": command_trace.get("successful_count"),
            "replay_calls": replay_trace.get("count", 0),
            "generation_wall_clock_seconds": _elapsed_seconds(metadata),
            "evaluation_wall_clock_seconds": _elapsed_seconds(evaluation_metadata),
            "coordinator_wall_clock_seconds": progress.get("duration_seconds"),
            "coordinator_wall_clock_comparable": episode.get(
                "coordinator_wall_clock_comparable", True
            ),
            "coordinator_wall_clock_censor_reason": episode.get(
                "coordinator_wall_clock_censor_reason"
            ),
            "peak_memory_bytes": None,
            "disk_growth_bytes": None,
            "network_bytes": None,
        },
        "diagnostics": {
            "error_count": raw_metrics.get("error_count"),
            "missing_import_count": next(
                (
                    (item.get("metrics") or {}).get("missing_import_count")
                    for item in (evaluation or {}).get("evidence", [])
                    if item.get("verifier_id") == "envbench-pyright-diagnostic"
                ),
                None,
            ),
        },
        "evidence_sha256": {
            "manifest.json": sha256_file(manifest_path),
            "generation/result.json": sha256_file(generation_path),
            **(
                {"scripts/bootstrap.sh": sha256_file(bootstrap_path)}
                if bootstrap_path.is_file()
                else {}
            ),
            **(
                {
                    "generation/container-commands.jsonl": sha256_file(
                        command_trace_path
                    )
                }
                if command_trace_path.is_file()
                else {}
            ),
            **(
                {"evaluation/result.json": sha256_file(evaluation_path)}
                if evaluation_path.is_file()
                else {}
            ),
        },
    }


def _exact_mcnemar_p(treatment_only: int, control_only: int) -> float:
    discordant = treatment_only + control_only
    if discordant == 0:
        return 1.0
    tail = min(treatment_only, control_only)
    return min(
        1.0,
        2.0 * sum(comb(discordant, k) for k in range(tail + 1)) / (2**discordant),
    )


def _aggregate_numeric(values: list[float | int]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "sum": sum(values),
        "mean": mean(values),
        "median": median(values),
    }


def _resource_analysis(
    pairs: list[dict[str, Any]],
    treatment_condition: str,
    control_condition: str,
) -> dict[str, Any]:
    metric_policy = {
        "input_tokens": "all paired attempts",
        "total_tokens": "all paired attempts",
        "commands": "all paired attempts",
        "coordinator_wall_clock_seconds": "pairs with comparable acquisition and timing",
    }
    output: dict[str, Any] = {"metric_policy": metric_policy, "metrics": {}}
    for metric in metric_policy:
        rows = []
        for pair in pairs:
            treatment = pair["episodes"][treatment_condition]
            control = pair["episodes"][control_condition]
            if metric == "coordinator_wall_clock_seconds" and not (
                treatment["resources"]["coordinator_wall_clock_comparable"]
                and control["resources"]["coordinator_wall_clock_comparable"]
            ):
                continue
            treatment_value = treatment["resources"].get(metric)
            control_value = control["resources"].get(metric)
            if not isinstance(treatment_value, (int, float)) or not isinstance(
                control_value, (int, float)
            ):
                continue
            rows.append(
                {
                    "pair_index": pair["pair_index"],
                    "repository": pair["repository"],
                    "treatment": treatment_value,
                    "control": control_value,
                    "treatment_minus_control": treatment_value - control_value,
                }
            )
        treatment_values = [row["treatment"] for row in rows]
        control_values = [row["control"] for row in rows]
        differences = [row["treatment_minus_control"] for row in rows]
        treatment_sum = sum(treatment_values)
        control_sum = sum(control_values)
        output["metrics"][metric] = {
            "pairs": rows,
            "treatment": _aggregate_numeric(treatment_values),
            "control": _aggregate_numeric(control_values),
            "paired_difference": _aggregate_numeric(differences),
            "ratio_of_sums": treatment_sum / control_sum if control_sum else None,
        }
    return output


def analyze_minimal_b_paired_dev5(
    adjudication_path: Path,
    runs_root: Path,
) -> dict[str, Any]:
    adjudication_path = adjudication_path.resolve()
    project_root = Path(__file__).resolve().parents[1]
    adjudication = read_json(adjudication_path)
    conditions = adjudication.get("conditions") or {}
    treatment_condition = conditions.get("treatment")
    control_condition = conditions.get("control")
    if not isinstance(treatment_condition, str) or not isinstance(
        control_condition, str
    ):
        raise ValueError("Adjudication must identify treatment and control conditions")
    raw_episodes = adjudication.get("effective_episodes")
    if not isinstance(raw_episodes, list) or len(raw_episodes) != 10:
        raise ValueError("Paired Dev-5 adjudication requires exactly ten effective episodes")

    episodes = [
        _episode_result(project_root, runs_root.resolve(), episode)
        for episode in raw_episodes
    ]
    grouped: dict[int, list[dict[str, Any]]] = {}
    for episode in episodes:
        grouped.setdefault(int(episode["pair_index"]), []).append(episode)
    if len(grouped) != 5:
        raise ValueError("Paired Dev-5 adjudication requires exactly five pairs")

    pair_results = []
    counts = Counter()
    for pair_index, pair_episodes in sorted(grouped.items()):
        by_condition = {str(item["condition"]): item for item in pair_episodes}
        if set(by_condition) != {treatment_condition, control_condition}:
            raise ValueError(f"Pair {pair_index} does not contain both frozen conditions")
        treatment = by_condition[treatment_condition]
        control = by_condition[control_condition]
        treatment_pass = treatment["official_pass_at_1"]
        control_pass = control["official_pass_at_1"]
        if treatment_pass and control_pass:
            category = "both_pass"
        elif treatment_pass:
            category = "treatment_only_pass"
        elif control_pass:
            category = "control_only_pass"
        else:
            category = "neither_pass"
        counts[category] += 1
        pair_results.append(
            {
                "pair_index": pair_index,
                "repository": treatment["repository"],
                "category": category,
                "episodes": by_condition,
            }
        )

    by_condition = {}
    for condition in (treatment_condition, control_condition):
        selected = [item for item in episodes if item["condition"] == condition]
        by_condition[condition] = {
            "runs": len(selected),
            "official_evaluator_reached": sum(
                item["official_evaluator_reached"] for item in selected
            ),
            "official_pass_at_1": sum(item["official_pass_at_1"] for item in selected),
            "pass_rate": mean(item["official_pass_at_1"] for item in selected),
            "generation_completed": sum(item["generation_completed"] for item in selected),
        }

    treatment_only = counts["treatment_only_pass"]
    control_only = counts["control_only_pass"]
    semantic_counts = Counter(
        str((item.get("semantic_adjudication") or {}).get("status", "not_adjudicated"))
        for item in episodes
    )
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
            "metric": "paired Official Pass@1",
            "failure_rule": "Any episode without an Official Pass is zero; independently attributable pre-Agent infrastructure attempts are replaced only by frozen amendment.",
            "by_condition": by_condition,
            "paired_counts": {
                "pairs": 5,
                "both_pass": counts["both_pass"],
                "treatment_only_pass": treatment_only,
                "control_only_pass": control_only,
                "neither_pass": counts["neither_pass"],
            },
            "absolute_pass_rate_difference": (
                by_condition[treatment_condition]["pass_rate"]
                - by_condition[control_condition]["pass_rate"]
            ),
            "exact_two_sided_mcnemar_p": _exact_mcnemar_p(
                treatment_only, control_only
            ),
        },
        "resources": {
            **_resource_analysis(pair_results, treatment_condition, control_condition),
            "unavailable_preregistered_metrics": [
                "peak_memory_bytes",
                "disk_growth_bytes",
                "network_bytes",
            ],
        },
        "posthoc_semantic_audit": {
            "status_counts": dict(sorted(semantic_counts.items())),
            "scope": "Diagnostic only; not part of preregistered Official Pass@1.",
        },
        "pairs": pair_results,
        "excluded_attempts": adjudication.get("excluded_attempts", []),
        "analysis_implementation": {
            "path": "envsolve_harness/minimal_b_analysis.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }
