#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.analysis.trajectory import (
    aggregate_trajectory_analyses,
    analyze_trajectory_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze deployment-agent decision trajectories.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    run_root = args.run_root.resolve()
    paths = sorted(run_root.glob("*/generation/trajectory.jsonl"))
    if not paths:
        raise ValueError(f"no trajectories found below {run_root}")
    cases = []
    for path in paths:
        analysis = analyze_trajectory_file(path)
        analysis["case_id"] = path.parents[1].name
        analysis["path"] = str(path.relative_to(ROOT))
        cases.append(analysis)
    result = {
        "analysis_id": "deployment-trajectory-error-analysis-v1",
        "run_root": str(run_root.relative_to(ROOT)),
        "aggregate": aggregate_trajectory_analyses(cases),
        "cases": cases,
        "interpretation_boundary": {
            "mechanism_selected": False,
            "causal_failure_labels_assigned": False,
            "infrastructure_failures_inferred_from_exit_code": False,
            "purpose": "Quantify action-level symptoms before selecting an EnvSolve mechanism.",
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
