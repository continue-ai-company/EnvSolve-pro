#!/usr/bin/env python3
from pathlib import Path

from run_schedule import main


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(
        main(
            default_schedule=ROOT / "experiments/validations/p6_operation_qualification_v2_schedule.json",
            default_progress=ROOT / "experiments/runs/p6-operation-q2-progress-v2.json",
        )
    )
