#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/cases/train_rest204.jsonl"
CASE_FILE = ROOT / "experiments/cases/dev_pro_strong_ab_census83_v1.jsonl"
SCHEDULE = (
    ROOT / "experiments/schedules/envsolve_pro_strong_ab_census83_v1.json"
)
EXPOSURE_AUDIT = (
    ROOT
    / "experiments/validations/"
    "envsolve_pro_strong_ab_census83_v1_exposure_audit.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "envsolve_pro_strong_ab_census83_v1_preregistration.json"
)

STRONG_MODELS = {"gpt-5.4", "gpt-5.5", "gpt-5.6-sol"}
SEED = 20260902
EXPECTED_SOURCE_COUNT = 204
EXPECTED_EXCLUDED_COUNT = 121
EXPECTED_ELIGIBLE_COUNT = 83

# These two schedules assigned all 200 census positions before most positions
# ran. Treating assignment as execution would incorrectly consume the source.
PLANNED_ONLY_SCHEDULES = {
    "pro_dev_bad_case_census_v1_mac_lane1.json",
    "pro_dev_bad_case_census_v1_mac_lane2.json",
}

HOSTS = {
    "agenthub": {
        "target": "agenthub@100.66.96.39",
        "workspace_root": "/Users/agenthub/work/envsolve-pro-strong-ab-census83-v1",
        "docker_executable": "/usr/local/bin/docker",
        "ssh_identity": "/Users/admin/.ssh/continue_ai_context_agenthub",
        "expose_gpus": False,
    },
    "spark": {
        "target": "avdpro@100.81.196.23",
        "workspace_root": "/home/avdpro/work/envsolve-pro-strong-ab-census83-v1",
        "docker_executable": "docker",
        "ssh_identity": None,
        "expose_gpus": True,
    },
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _manifest_evidence(
    roots: Iterable[Path], source_ids: set[str]
) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {}
    visited: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        resolved = root.resolve()
        if resolved in visited:
            continue
        visited.add(resolved)
        for path in root.rglob("manifest.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            run = payload.get("run")
            case = payload.get("case")
            if not isinstance(run, dict) or not isinstance(case, dict):
                continue
            case_id = case.get("case_id")
            if run.get("model") not in STRONG_MODELS or case_id not in source_ids:
                continue
            evidence.setdefault(str(case_id), []).append(str(path))
    return evidence


def _document_evidence(source_ids: set[str]) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {}
    for relative in ("experiments/schedules", "experiments/validations"):
        for path in (ROOT / relative).glob("*.json"):
            if path.name in PLANNED_ONLY_SCHEDULES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
                payload = json.loads(text)
            except (OSError, json.JSONDecodeError):
                continue

            def strings(value: Any) -> Iterable[str]:
                if isinstance(value, str):
                    yield value
                elif isinstance(value, dict):
                    for key, item in value.items():
                        yield from strings(key)
                        yield from strings(item)
                elif isinstance(value, list):
                    for item in value:
                        yield from strings(item)

            values = set(strings(payload))
            if not values.intersection(STRONG_MODELS):
                continue
            for case_id in source_ids.intersection(values):
                evidence.setdefault(case_id, []).append(str(path.relative_to(ROOT)))
    return evidence


def _merge_evidence(
    *sources: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for source in sources:
        for case_id, paths in source.items():
            merged.setdefault(case_id, []).extend(paths)
    return {case_id: sorted(set(paths)) for case_id, paths in merged.items()}


def _case_plan(
    ordered: list[dict[str, Any]], rng: random.Random
) -> list[dict[str, Any]]:
    hosts = ["agenthub", "spark"] * (len(ordered) // 2)
    if len(hosts) < len(ordered):
        hosts.append("agenthub")
    rng.shuffle(hosts)
    plans: list[dict[str, Any]] = []
    for position, (row, host) in enumerate(zip(ordered, hosts), start=1):
        followups = ["A2-no-replay", "B-same-session-replay"]
        rng.shuffle(followups)
        prefix = f"pro-strong-ab-census83-{position:02d}"
        plans.append(
            {
                "position": position,
                "case_id": row["case_id"],
                "construction_host": host,
                "a1": {
                    "condition": "A1-no-replay",
                    "run_id": f"{prefix}-A1",
                    "runner": (
                        "codex-cli-boundary-v5-official-primary-remote-docker"
                    ),
                    "method": "codex-cli-goal-aware-boundary-v5",
                },
                "conditional_followup_order": followups,
                "a2": {
                    "condition": "A2-no-replay",
                    "run_id": f"{prefix}-A2",
                    "runner": (
                        "codex-cli-boundary-v5-official-primary-remote-docker"
                    ),
                    "method": "codex-cli-goal-aware-boundary-v5",
                },
                "b": {
                    "condition": "B-same-session-replay",
                    "run_id": f"{prefix}-B",
                    "runner": (
                        "envsolve-pro-minimal-b-boundary-v5-remote-docker"
                    ),
                    "method": "envsolve-pro-minimal-b-boundary-v5",
                },
            }
        )
    return plans


def main() -> int:
    source = _read_jsonl(SOURCE)
    if len(source) != EXPECTED_SOURCE_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_SOURCE_COUNT} source cases")
    source_by_id = {str(row["case_id"]): row for row in source}
    if len(source_by_id) != len(source):
        raise RuntimeError("Source case IDs are not unique")

    external_runs = Path(
        os.environ.get(
            "ENVSOLVE_HISTORICAL_RUNS_ROOT",
            "/Users/admin/Documents/AnyDeploy/runs",
        )
    )
    evidence = _merge_evidence(
        _manifest_evidence((ROOT / "runs", external_runs), set(source_by_id)),
        _document_evidence(set(source_by_id)),
    )
    excluded_ids = set(evidence)
    eligible_ids = set(source_by_id).difference(excluded_ids)
    if len(excluded_ids) != EXPECTED_EXCLUDED_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_EXCLUDED_COUNT} exclusions, got {len(excluded_ids)}"
        )
    if len(eligible_ids) != EXPECTED_ELIGIBLE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_ELIGIBLE_COUNT} eligible cases, got "
            f"{len(eligible_ids)}"
        )

    rng = random.Random(SEED)
    ordered_ids = sorted(eligible_ids)
    rng.shuffle(ordered_ids)
    ordered = [source_by_id[case_id] for case_id in ordered_ids]
    selected_rows = [
        {**row, "split": "dev-pro-strong-ab-census83-v1"} for row in ordered
    ]
    plans = _case_plan(ordered, rng)
    recorded_at = datetime.now(timezone.utc).isoformat()

    _write_jsonl(CASE_FILE, selected_rows)
    _write_json(
        EXPOSURE_AUDIT,
        {
            "study_id": "envsolve-pro-strong-ab-census83-v1",
            "recorded_at": recorded_at,
            "source_case_file": str(SOURCE.relative_to(ROOT)),
            "source_count": len(source),
            "strong_models": sorted(STRONG_MODELS),
            "evidence_policy": (
                "Exclude identities with a strong-model run manifest or a "
                "strong-model-associated committed schedule/validation record. "
                "The two blanket census assignment schedules are ignored "
                "because assignment did not establish execution."
            ),
            "manifest_roots": [str((ROOT / "runs").resolve()), str(external_runs)],
            "remote_reconciliation": {
                "spark_manifest_count": 4331,
                "spark_strong_case_count": 56,
                "agenthub_manifest_count": 2991,
                "agenthub_strong_case_count": 1,
                "additional_source_identities_beyond_local_evidence": 0,
                "observed_at": "2026-09-02",
            },
            "planned_only_schedules_ignored": sorted(PLANNED_ONLY_SCHEDULES),
            "excluded_count": len(excluded_ids),
            "eligible_count": len(eligible_ids),
            "excluded_cases": [
                {"case_id": case_id, "evidence": evidence[case_id]}
                for case_id in sorted(excluded_ids)
            ],
            "claim_limit": (
                "All Dev identities are consumed under at least one method. "
                "This audit supports strong-model mechanism diagnosis only, "
                "not repository-unseen generalization."
            ),
        },
    )
    _write_json(
        SCHEDULE,
        {
            "study_id": "envsolve-pro-strong-ab-census83-v1",
            "case_file": str(CASE_FILE.relative_to(ROOT)),
            "model": "gpt-5.6-sol",
            "reasoning_effort": "xhigh",
            "random_seed": SEED,
            "case_order": "random shuffle fixed before outcomes",
            "construction_hosts": HOSTS,
            "official_host": "Spark fresh EnvBench container",
            "official_fallback": (
                "Mac ARM64 fresh EnvBench container only after a recorded "
                "Spark infrastructure failure; submitted program unchanged"
            ),
            "max_parallel_generation_sessions": 2,
            "max_generation_sessions_per_construction_host": 1,
            "cases": plans,
        },
    )
    _write_json(
        PREREGISTRATION,
        {
            "study_id": "envsolve-pro-strong-ab-census83-v1",
            "recorded_at": recorded_at,
            "status": "recorded_before_first_a1_outcome",
            "scientific_role": (
                "Consumed/Dev falsification cohort for same-session complete-"
                "program replay; not protected-set effect estimation."
            ),
            "question": (
                "Does same-session target-state complete-program replay produce "
                "terminal Official wins that a second equally strong free-Agent "
                "session does not?"
            ),
            "selection": {
                "source": str(SOURCE.relative_to(ROOT)),
                "exposure_audit": str(EXPOSURE_AUDIT.relative_to(ROOT)),
                "source_count": len(source),
                "excluded_strong_association_count": len(excluded_ids),
                "census_count": len(eligible_ids),
                "selection": "all eligible identities; no outcome sampling",
                "order_seed": SEED,
                "repository_content_or_current_outcome_used": False,
            },
            "shared_protocol": {
                "model": "gpt-5.6-sol",
                "reasoning_effort": "xhigh",
                "candidate_interface": "complete executable Bash program",
                "operation_space": "open",
                "resource_limits": "nonbinding safety caps",
                "official_feedback_returned_online": False,
                "official_metric": "Official Pass@1",
                "case_specific_rules": False,
                "cross_case_experience": False,
                "protected_canary_opened": False,
                "official_test_opened": False,
            },
            "execution": {
                "run_a1_on_every_case": True,
                "followup_eligibility": (
                    "A1 formed an admissible complete program and independent "
                    "Official completed but failed for a deployment reason"
                ),
                "pre_candidate_failure": (
                    "Record as a replay boundary; do not run conditional A2/B"
                ),
                "followup": (
                    "Run both A2 and B for every eligible A1 failure in the "
                    "preassigned per-case order"
                ),
                "unique_treatment_difference": (
                    "B may call target-state complete-program replay and receive "
                    "its result before the same active Agent session ends; A1 "
                    "and A2 cannot"
                ),
                "construction_host_blocking": (
                    "All arms for one case use its preassigned host; host is "
                    "balanced and assigned before outcomes"
                ),
                "machine_roles": {
                    "mac": "Agent controller, scheduler, artifact collection",
                    "agenthub": "one remote non-GPU construction/replay lane",
                    "spark": (
                        "one remote CUDA-capable construction/replay lane and "
                        "primary independent Official queue"
                    ),
                },
            },
            "analysis": {
                "primary_unit": "eligible A1 complete-program Official failure",
                "primary_contrast": (
                    "B-exclusive wins versus A2-exclusive wins; both-pass and "
                    "both-fail are ties"
                ),
                "screen_level_report": (
                    "A1-only, A1-then-A2, and A1-then-B Official Pass@1"
                ),
                "secondary_metrics": [
                    "tokens",
                    "wall-clock time",
                    "container commands",
                    "complete-program replay count",
                    "infrastructure censoring",
                ],
                "frontier_metrics": "diagnostic only; never substitute for pass",
                "competitive_explanation": "independent Agent-session variability",
            },
            "decision": {
                "promote": (
                    "Only after reproducible B-exclusive Official wins establish "
                    "incremental terminal success over A2"
                ),
                "retain": (
                    "Evidence is mixed or opportunity count is insufficient; "
                    "do not add replay rules"
                ),
                "kill": (
                    "No reproducible B-exclusive terminal advantage, or A2 "
                    "matches/exceeds B across the opportunity cohort"
                ),
            },
            "safeguard_policy": (
                "No new hash, frozen contract, or software gate. Git records "
                "the preregistered files; ordinary tests check consistency."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
