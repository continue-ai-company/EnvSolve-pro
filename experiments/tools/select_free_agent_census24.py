"""Select the fixed free-Agent Dev census without reading outcome data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def select(
    universe_path: Path,
    *,
    seed: int,
    size: int,
) -> list[dict[str, object]]:
    rows = read_jsonl(universe_path)
    by_id = {str(row["case_id"]): row for row in rows}
    if len(rows) != len(by_id):
        raise ValueError("Universe contains duplicate case IDs")
    selected_ids = random.Random(seed).sample(sorted(by_id), size)
    return [
        {
            **by_id[case_id],
            "position": position,
            "split": "dev-pro-free-agent-census24-v1",
        }
        for position, case_id in enumerate(selected_ids, 1)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--cases-output", type=Path, required=True)
    parser.add_argument("--schedule-output", type=Path, required=True)
    parser.add_argument(
        "--exposure-audit",
        type=Path,
        default=Path(
            "experiments/validations/"
            "envsolve_pro_strong_ab_census83_v1_exposure_audit.json"
        ),
    )
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--size", type=int, default=24)
    args = parser.parse_args()

    selected = select(args.universe, seed=args.seed, size=args.size)
    exposure_audit = json.loads(args.exposure_audit.read_text(encoding="utf-8"))
    exposure_source = Path(str(exposure_audit["source_case_file"]))
    exposed_ids = {str(row["case_id"]) for row in read_jsonl(exposure_source)}
    exposure_by_id = {
        str(row["case_id"]): str(row["case_id"]) in exposed_ids for row in selected
    }
    args.cases_output.parent.mkdir(parents=True, exist_ok=True)
    args.schedule_output.parent.mkdir(parents=True, exist_ok=True)
    args.cases_output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in selected),
        encoding="utf-8",
    )
    schedule = {
        "study_id": "envsolve-pro-free-agent-census24-v1",
        "status": "fixed-not-started",
        "recorded_at": "2026-09-07",
        "purpose": (
            "Estimate strong-Agent submission and terminal-failure prevalence; "
            "not treatment efficacy."
        ),
        "population": {
            "case_file": str(args.universe),
            "count": len(read_jsonl(args.universe)),
            "definition": "explicit consumed/Dev universe; no protected data",
        },
        "selection": {
            "algorithm": "random.Random(seed).sample(sorted(case_ids), size)",
            "seed": args.seed,
            "size": args.size,
            "replacement": False,
            "outcomes_read_for_selection": False,
        },
        "configuration": {
            "model": "gpt-5.6-sol",
            "reasoning_effort": "xhigh",
            "codex_cli": "0.153.4",
            "runner": "free-agent-voluntary-environments-remote",
            "runner_version": "1.0.1",
            "construction": "Mac controller with AgentHub remote Docker",
            "official": "postepisode only on Spark",
            "config": "experiments/configs/local_mac_free_agent_census_v1.json",
            "protocol": "experiments/protocols/envbench_python_public_goal_v2.json",
        },
        "stopping": {
            "positions": args.size,
            "replacement_cases": False,
            "outcome_driven_retries": False,
            "continuation_arms": False,
        },
        "reporting": {
            "primary": "legitimate Official Pass@1 over all 24 positions",
            "also_report": [
                "valid program submissions",
                "bootstrap failures",
                "missing-import failures",
                "source failures",
                "explicit infrastructure censoring",
                "unresolved outcomes",
                "time and token usage",
            ],
            "conditional_valid_score_is_not_whole_sample_success": True,
        },
        "prior_exposure": {
            "definition": "at least one prior method executed on the identity",
            "overlap_count": sum(exposure_by_id.values()),
            "all_selected_previously_exposed": all(exposure_by_id.values()),
            "evidence": str(args.exposure_audit),
            "evidence_population": str(exposure_source),
            "claim_limit": "consumed development evidence, not unseen generalization",
        },
        "cases": [
            {
                "position": row["position"],
                "case_id": row["case_id"],
                "source_split": row["source_split"],
                "prior_exposure": exposure_by_id[str(row["case_id"])],
            }
            for row in selected
        ],
    }
    args.schedule_output.write_text(
        json.dumps(schedule, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
