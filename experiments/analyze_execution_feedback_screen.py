#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.state import EventStore
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.utils.provenance import sha256_file

_PROVIDER_FAILURE = re.compile(
    r"(?:APIConnectionError|APITimeoutError|"
    r"EpisodeProviderAcquisitionFailed|Request timed out)",
)
_REPOSITORY_ACQUISITION_FAILURE = re.compile(
    r"(?:Unable to acquire the requested repository revision|"
    r"Failed to download repository)",
)
_ALGORITHMIC_EXECUTION_TIMEOUT = re.compile(
    r"(?:Executable goal contract exceeded its observation timeout|"
    r"candidate (?:command|execution).*timed? out)",
    re.IGNORECASE,
)
_MEASUREMENT_INTEGRITY_FAILURE = re.compile(
    r"(?:Import alias integrity audit|Internal import probe) "
    r"did not produce a valid report",
)
_INTEGRITY_FAILURE = re.compile(
    r"(?:effect boundaries|protected environment|outer workspace|"
    r"synthetic Python import alias)",
    re.IGNORECASE,
)
_EDITABLE_EXTRAS = re.compile(
    r"(?:python(?:3)?\s+-m\s+)?pip(?:3)?\s+install[^\n]*"
    r"-e\s+[\"']?\.\[([^\]]+)\]",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize the dual-host execution-feedback-v3 screen."
    )
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--mac-runs-root", type=Path, required=True)
    parser.add_argument("--spark-runs-root", type=Path, required=True)
    parser.add_argument(
        "--amendment",
        action="append",
        default=[],
        type=Path,
        help=(
            "Audited external-interruption amendment whose retry artifact "
            "replaces an ineligible preregistered attempt."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _apply_interruption_amendments(
    preregistration: dict[str, Any],
    amendments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    episodes = [dict(episode) for episode in preregistration["episodes"]]
    replacements: list[dict[str, str]] = []
    replaced_run_ids: set[str] = set()
    for amendment in amendments:
        if amendment.get("amendment_type") != (
            "user-directed-external-interruption"
        ):
            raise ValueError("Unsupported analysis amendment type")
        if amendment.get("study_id") != preregistration.get("study_id"):
            raise ValueError("Amendment study_id does not match preregistration")
        source = amendment.get("source_episode")
        retry = amendment.get("retry")
        if not isinstance(source, dict) or not isinstance(retry, dict):
            raise TypeError("Amendment must define source_episode and retry")
        if source.get("primary_metric_eligible") is not False:
            raise ValueError("Amendment source must be primary-metric ineligible")
        required_retry_invariants = (
            "same_algorithm_files",
            "same_budget_and_timeouts",
            "same_case",
            "same_host",
            "same_model",
            "same_seed",
            "fresh_episode_and_containers",
        )
        if any(retry.get(key) is not True for key in required_retry_invariants):
            raise ValueError("Amendment retry invariants are incomplete")
        if retry.get("inherits_partial_candidate_state") is not False:
            raise ValueError("Amendment retry cannot inherit candidate state")
        if retry.get("algorithm_prompt_or_threshold_changed") is not False:
            raise ValueError("Amendment retry cannot change the algorithm")

        source_run_id = str(source.get("run_id", "")).strip()
        retry_run_id = str(retry.get("run_id", "")).strip()
        if not source_run_id or not retry_run_id:
            raise ValueError("Amendment run ids cannot be empty")
        if source_run_id in replaced_run_ids:
            raise ValueError(f"Duplicate amendment for {source_run_id}")
        matches = [
            episode
            for episode in episodes
            if episode.get("run_id") == source_run_id
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Amendment source {source_run_id} must match one episode"
            )
        episode = matches[0]
        if episode.get("case_id") != source.get("case_id"):
            raise ValueError("Amendment source case does not match episode")
        episode["preregistered_run_id"] = source_run_id
        episode["run_id"] = retry_run_id
        episode["analysis_replacement"] = (
            "user-directed-external-interruption-retry"
        )
        replacements.append(
            {
                "preregistered_run_id": source_run_id,
                "analyzed_run_id": retry_run_id,
            }
        )
        replaced_run_ids.add(source_run_id)
    return episodes, replacements


def _case_root(runs_root: Path, run_id: str) -> Path:
    roots = sorted(
        path.parent
        for path in (runs_root / run_id).glob("*/manifest.json")
    )
    if len(roots) != 1:
        raise ValueError(
            f"{run_id}: expected exactly one case root, found {len(roots)}"
        )
    return roots[0]


def _artifact_hashes(case_root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for relative in (
        "generation/result.json",
        "generation/episode.jsonl",
        "generation/episode_snapshot.json",
        "generation/budget_ledger.json",
        "evaluation/result.json",
    ):
        path = case_root / relative
        if path.is_file():
            values[relative] = sha256_file(path)
    return values


def _mechanism_metrics(state: Any) -> dict[str, Any]:
    redirection_removals: list[dict[str, Any]] = []
    for action in state.actions.values():
        validation = action.get("metadata", {}).get("candidate_validation")
        details = (
            validation.get("details")
            if isinstance(validation, dict)
            else None
        )
        count = (
            details.get("diagnostic_redirection_removal_count")
            if isinstance(details, dict)
            else None
        )
        if isinstance(count, int) and count:
            redirection_removals.append(
                {
                    "candidate_id": action.get("action_id"),
                    "count": count,
                }
            )

    recoveries: list[str] = []
    infrastructure_unknowns: list[str] = []
    integrity_failures: list[str] = []
    for verification in state.verifications:
        details = verification.get("details")
        if not isinstance(details, dict):
            continue
        verifier_details = details.get("verifier_details")
        verifier_details = (
            verifier_details if isinstance(verifier_details, dict) else {}
        )
        candidate_id = str(details.get("candidate_id"))
        if verifier_details.get("recoverable_goal_execution_failure") is True:
            recoveries.append(candidate_id)
        if (
            verifier_details.get("failure_disposition")
            == "infrastructure-censored"
        ):
            infrastructure_unknowns.append(candidate_id)
        summary = details.get("summary")
        if isinstance(summary, str) and _INTEGRITY_FAILURE.search(summary):
            integrity_failures.append(candidate_id)
    return {
        "candidate_count": len(state.actions),
        "diagnostic_redirection_removal_count": sum(
            item["count"] for item in redirection_removals
        ),
        "diagnostic_redirection_removals": redirection_removals,
        "recoverable_goal_execution_failure_count": len(recoveries),
        "recoverable_goal_execution_failure_candidate_ids": recoveries,
        "infrastructure_censored_unknown_count": len(
            infrastructure_unknowns
        ),
        "infrastructure_censored_unknown_candidate_ids": (
            infrastructure_unknowns
        ),
        "integrity_failure_count": len(integrity_failures),
        "integrity_failure_candidate_ids": integrity_failures,
    }


def _operation_metrics(state: Any) -> dict[str, Any]:
    statuses = Counter(
        str(action.get("status", "unknown"))
        for action in state.actions.values()
    )
    durations: list[tuple[str, float]] = []
    editable_extras: list[dict[str, Any]] = []
    for action_id, action in state.actions.items():
        observation = action.get("observation")
        duration = (
            observation.get("duration_seconds")
            if isinstance(observation, dict)
            else None
        )
        if isinstance(duration, (int, float)) and not isinstance(
            duration, bool
        ):
            durations.append((action_id, float(duration)))
        command = action.get("command")
        if not isinstance(command, str):
            continue
        groups = {
            value.strip()
            for match in _EDITABLE_EXTRAS.finditer(command)
            for value in match.group(1).split(",")
            if value.strip()
        }
        if groups:
            editable_extras.append(
                {
                    "candidate_id": action_id,
                    "extra_group_count": len(groups),
                    "extra_groups": sorted(groups),
                }
            )
    failure_categories = Counter(
        str(failure.get("category", "unknown"))
        for failure in state.failures.values()
    )
    validation_reject_messages = Counter(
        str(failure.get("message", ""))
        for failure in state.failures.values()
        if failure.get("category") == "candidate-validation-reject"
    )
    return {
        "action_status_counts": dict(sorted(statuses.items())),
        "running_action_ids": sorted(
            action_id
            for action_id, action in state.actions.items()
            if action.get("status") == "running"
        ),
        "completed_action_duration_seconds": {
            "count": len(durations),
            "total": round(sum(value for _, value in durations), 6),
            "maximum": (
                round(max(value for _, value in durations), 6)
                if durations
                else None
            ),
            "maximum_candidate_id": (
                max(durations, key=lambda item: item[1])[0]
                if durations
                else None
            ),
        },
        "editable_extra_groups": editable_extras,
        "maximum_editable_extra_group_count": max(
            (
                int(item["extra_group_count"])
                for item in editable_extras
            ),
            default=0,
        ),
        "failure_category_counts": dict(sorted(failure_categories.items())),
        "candidate_validation_reject_count": failure_categories.get(
            "candidate-validation-reject",
            0,
        ),
        "candidate_validation_reject_messages": dict(
            sorted(validation_reject_messages.items())
        ),
    }


def _constraint_progress_metrics(state: Any) -> dict[str, Any]:
    finding_sets: list[tuple[str, tuple[str, ...]]] = []
    for verification in state.verifications:
        details = verification.get("details")
        details = details if isinstance(details, dict) else {}
        verifier_details = details.get("verifier_details")
        verifier_details = (
            verifier_details if isinstance(verifier_details, dict) else {}
        )
        finding_ids = verifier_details.get("finding_ids")
        if not isinstance(finding_ids, list) or not all(
            isinstance(item, str) for item in finding_ids
        ):
            continue
        finding_sets.append(
            (
                str(details.get("candidate_id")),
                tuple(sorted(set(finding_ids))),
            )
        )
    stagnant_transitions: list[dict[str, Any]] = []
    for index in range(1, len(finding_sets)):
        previous = finding_sets[index - 1]
        current = finding_sets[index]
        if current[1] and current[1] == previous[1]:
            stagnant_transitions.append(
                {
                    "from_candidate_id": previous[0],
                    "to_candidate_id": current[0],
                    "finding_count": len(current[1]),
                }
            )
    longest_run = 0
    current_run = 0
    previous_findings: tuple[str, ...] | None = None
    for _, findings in finding_sets:
        if not findings:
            current_run = 0
        elif findings == previous_findings:
            current_run += 1
        else:
            current_run = 1
        longest_run = max(longest_run, current_run)
        previous_findings = findings
    return {
        "finding_set_observation_count": len(finding_sets),
        "finding_count_sequence": [
            {
                "candidate_id": candidate_id,
                "finding_count": len(findings),
            }
            for candidate_id, findings in finding_sets
        ],
        "stagnant_frontier_transition_count": len(stagnant_transitions),
        "stagnant_frontier_transitions": stagnant_transitions,
        "longest_identical_nonempty_finding_set_run": longest_run,
    }


def _terminal_class(
    *,
    generation: dict[str, Any],
    evaluation: dict[str, Any] | None,
) -> tuple[str, bool]:
    error = generation.get("error")
    error_text = error if isinstance(error, str) else ""
    if _PROVIDER_FAILURE.search(error_text):
        return "provider-infrastructure-censored", True
    if _REPOSITORY_ACQUISITION_FAILURE.search(error_text):
        return "repository-acquisition-infrastructure-censored", True
    if _MEASUREMENT_INTEGRITY_FAILURE.search(error_text):
        return "measurement-integrity-censored", True
    evaluation_completed = (
        isinstance(evaluation, dict)
        and evaluation.get("evaluation_completed") is True
    )
    if evaluation_completed:
        return (
            "official-pass"
            if evaluation.get("official_pass") is True
            else "official-fail"
        ), False
    if _ALGORITHMIC_EXECUTION_TIMEOUT.search(error_text):
        return "algorithmic-execution-timeout", False
    if generation.get("generation_completed") is not True:
        return "algorithmic-generation-failure", False
    return "official-evaluation-missing", False


def _episode(
    episode: dict[str, Any],
    *,
    runs_roots: dict[str, Path],
) -> dict[str, Any]:
    run_id = str(episode["run_id"])
    host = str(episode["host"])
    case_root = _case_root(runs_roots[host], run_id)
    generation = read_json(case_root / "generation" / "result.json")
    ledger = read_json(case_root / "generation" / "budget_ledger.json")
    evaluation_path = case_root / "evaluation" / "result.json"
    evaluation = (
        read_json(evaluation_path) if evaluation_path.is_file() else None
    )
    error = generation.get("error")
    terminal_class, primary_censored = _terminal_class(
        generation=generation,
        evaluation=evaluation,
    )
    provider_censored = terminal_class == "provider-infrastructure-censored"
    infrastructure_censored = terminal_class in {
        "provider-infrastructure-censored",
        "repository-acquisition-infrastructure-censored",
    }
    measurement_censored = (
        terminal_class == "measurement-integrity-censored"
    )
    evaluation_completed = (
        isinstance(evaluation, dict)
        and evaluation.get("evaluation_completed") is True
    )
    if evaluation_completed:
        official_pass = evaluation.get("official_pass")
    elif primary_censored:
        official_pass = None
    else:
        official_pass = False
    manifest = read_json(case_root / "manifest.json")
    case = manifest["case"]
    state = EventStore(
        case_root / "generation" / "episode.jsonl",
        str(case["case_id"]),
    ).reconstruct()
    usage = ledger.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return {
        **episode,
        "artifact_root": str(case_root.resolve()),
        "terminal_class": terminal_class,
        "infrastructure_censored": infrastructure_censored,
        "measurement_censored": measurement_censored,
        "provider_censored": provider_censored,
        "primary_metric_eligible": not primary_censored,
        "generation_completed": (
            generation.get("generation_completed") is True
        ),
        "evaluation_completed": evaluation_completed,
        "official_pass": official_pass,
        "generation_error": error,
        "usage": {
            key: usage.get(key)
            for key in (
                "candidates",
                "commands",
                "environments",
                "requests_started",
                "input_tokens",
                "cache_read_tokens",
                "output_tokens",
                "total_tokens",
                "elapsed_wall_clock_seconds",
            )
        },
        "mechanism": _mechanism_metrics(state),
        "operation": _operation_metrics(state),
        "constraint_progress": _constraint_progress_metrics(state),
        "artifact_sha256": _artifact_hashes(case_root),
    }


def _pairs(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        grouped[str(episode["case_id"])].append(episode)
    rows: list[dict[str, Any]] = []
    for case_id, values in sorted(grouped.items()):
        conditions = {
            str(item["condition"]): item for item in values
        }
        treatment = conditions["execution-feedback-v3"]
        control = conditions["goal-frontier-v1-control"]
        eligible = all(item["primary_metric_eligible"] for item in values)
        difference = (
            int(treatment["official_pass"])
            - int(control["official_pass"])
            if eligible
            else None
        )
        usage_difference: dict[str, int | float | None] = {}
        for key in (
            "candidates",
            "total_tokens",
            "elapsed_wall_clock_seconds",
        ):
            treatment_value = treatment["usage"][key]
            control_value = control["usage"][key]
            usage_difference[key] = (
                treatment_value - control_value
                if isinstance(treatment_value, (int, float))
                and isinstance(control_value, (int, float))
                else None
            )
        rows.append(
            {
                "case_id": case_id,
                "host": treatment["host"],
                "paired_primary_eligible": eligible,
                "official_pass_treatment": treatment["official_pass"],
                "official_pass_control": control["official_pass"],
                "terminal_class_treatment": treatment["terminal_class"],
                "terminal_class_control": control["terminal_class"],
                "official_pass_difference": difference,
                "treatment_minus_control": usage_difference,
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    preregistration = read_json(args.preregistration.resolve())
    amendment_paths = [path.resolve() for path in args.amendment]
    amendments = [read_json(path) for path in amendment_paths]
    selected_episodes, replacements = _apply_interruption_amendments(
        preregistration,
        amendments,
    )
    roots = {
        "mac": args.mac_runs_root.resolve(),
        "spark": args.spark_runs_root.resolve(),
    }
    episodes = [
        _episode(dict(episode), runs_roots=roots)
        for episode in selected_episodes
    ]
    pairs = _pairs(episodes)
    eligible = [item for item in episodes if item["primary_metric_eligible"]]
    treatment_passes = sum(
        item["condition"] == "execution-feedback-v3"
        and item["official_pass"] is True
        for item in eligible
    )
    control_passes = sum(
        item["condition"] == "goal-frontier-v1-control"
        and item["official_pass"] is True
        for item in eligible
    )
    payload = {
        "schema_version": "1.0.0",
        "study_id": preregistration["study_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": preregistration["claim_scope"],
        "analysis_policy": {
            "generation_failure_is_official_pass_failure": True,
            "provider_censoring_is_not_official_pass_failure": True,
            "measurement_integrity_censoring_is_not_official_pass_failure": (
                True
            ),
            "official_evaluator_feedback_used_online": False,
            "posthoc_case_replacement": False,
        },
        "source_artifacts": {
            "preregistration": str(args.preregistration),
            "preregistration_sha256": sha256_file(args.preregistration),
            "runs_roots": {
                host: str(path) for host, path in roots.items()
            },
            "amendments": [
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                }
                for path in amendment_paths
            ],
            "run_id_replacements": replacements,
        },
        "primary_summary": {
            "selected_pair_count": len(pairs),
            "primary_eligible_pair_count": sum(
                item["paired_primary_eligible"] for item in pairs
            ),
            "official_pass_treatment": treatment_passes,
            "official_pass_control": control_passes,
            "official_pass_difference_sum": sum(
                int(item["official_pass_difference"])
                for item in pairs
                if item["official_pass_difference"] is not None
            ),
            "treatment_win_count": sum(
                item["official_pass_difference"] == 1 for item in pairs
            ),
            "control_win_count": sum(
                item["official_pass_difference"] == -1 for item in pairs
            ),
            "tie_count": sum(
                item["official_pass_difference"] == 0 for item in pairs
            ),
        },
        "mechanism_summary": {
            "diagnostic_redirection_removal_count": sum(
                item["mechanism"][
                    "diagnostic_redirection_removal_count"
                ]
                for item in episodes
                if item["condition"] == "execution-feedback-v3"
            ),
            "recoverable_goal_execution_failure_count": sum(
                item["mechanism"][
                    "recoverable_goal_execution_failure_count"
                ]
                for item in episodes
                if item["condition"] == "execution-feedback-v3"
            ),
            "infrastructure_censored_unknown_count": sum(
                item["mechanism"]["infrastructure_censored_unknown_count"]
                for item in episodes
                if item["condition"] == "execution-feedback-v3"
            ),
            "integrity_failure_count": sum(
                item["mechanism"]["integrity_failure_count"]
                for item in episodes
                if item["condition"] == "execution-feedback-v3"
            ),
        },
        "terminal_class_summary": dict(
            sorted(Counter(item["terminal_class"] for item in episodes).items())
        ),
        "operation_summary": {
            "algorithmic_execution_timeout_count": sum(
                item["terminal_class"] == "algorithmic-execution-timeout"
                for item in episodes
            ),
            "episode_with_running_action_at_terminal_count": sum(
                bool(item["operation"]["running_action_ids"])
                for item in episodes
            ),
            "maximum_editable_extra_group_count": max(
                (
                    item["operation"]["maximum_editable_extra_group_count"]
                    for item in episodes
                ),
                default=0,
            ),
            "candidate_validation_reject_count": sum(
                item["operation"]["candidate_validation_reject_count"]
                for item in episodes
            ),
            "candidate_validation_reject_message_counts": dict(
                sorted(
                    sum(
                        (
                            Counter(
                                item["operation"][
                                    "candidate_validation_reject_messages"
                                ]
                            )
                            for item in episodes
                        ),
                        Counter(),
                    ).items()
                )
            ),
        },
        "constraint_progress_summary": {
            "episode_with_stagnant_frontier_count": sum(
                item["constraint_progress"][
                    "stagnant_frontier_transition_count"
                ]
                > 0
                for item in episodes
            ),
            "stagnant_frontier_transition_count": sum(
                item["constraint_progress"][
                    "stagnant_frontier_transition_count"
                ]
                for item in episodes
            ),
            "maximum_identical_nonempty_finding_set_run": max(
                (
                    item["constraint_progress"][
                        "longest_identical_nonempty_finding_set_run"
                    ]
                    for item in episodes
                ),
                default=0,
            ),
        },
        "pairs": pairs,
        "episodes": episodes,
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
