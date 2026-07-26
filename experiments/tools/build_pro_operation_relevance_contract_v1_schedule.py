#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ROOT
    / "experiments/cases/dev_pro_operation_relevance_contract_v1_5.jsonl"
)
SELECTION = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_selection.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_preregistration.json"
)
CONFIG = (
    ROOT / "experiments/configs/local_mac_pro_operation_relevance_v1.json"
)
PROTOCOL = ROOT / "experiments/protocols/envbench_python_official_v1.json"
OUTPUT = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_schedule.json"
)
SALT = "d00539b:operation-relevance-contract-qv1"
IMPLEMENTATION_FREEZE = "d00539b351947ddcbca2f124ad0968d9875a6f37"
MODEL = "deepseek/deepseek-v4-pro"
CONDITIONS = (
    {
        "condition": "frozen-fresh-control",
        "runner": "envsolve",
        "method": "envsolve-pro-goal-contract-evidence-anchor",
    },
    {
        "condition": "operation-contract-v1",
        "runner": "envsolve-pro",
        "method": "envsolve-pro-operation-contract",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(*parts: str) -> str:
    return hashlib.sha256(
        (SALT + "\0" + "\0".join(parts)).encode("utf-8")
    ).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"Refusing to overwrite schedule: {OUTPUT}")
    if not SELECTION.is_file():
        raise RuntimeError("Metadata selection must precede schedule binding")
    rows = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 5 or len({row["repository"] for row in rows}) != 5:
        raise RuntimeError("Qualification requires five distinct repositories")
    rows.sort(key=lambda row: digest("case-order", str(row["case_id"])))

    episodes = []
    for case_index, row in enumerate(rows, start=1):
        conditions = sorted(
            CONDITIONS,
            key=lambda item: digest(
                "condition-order",
                str(row["case_id"]),
                str(item["condition"]),
            ),
        )
        repository_slug = str(row["repository"]).split("/")[-1].lower()
        for condition in conditions:
            episodes.append(
                {
                    "position": len(episodes) + 1,
                    "case_block": case_index,
                    "condition": condition["condition"],
                    "case_id": row["case_id"],
                    "run_id": (
                        f"pro-oprel-qv1-c{case_index:02d}-"
                        f"{repository_slug}-{condition['condition']}"
                    ),
                    "runner": condition["runner"],
                    "method": condition["method"],
                    "model": MODEL,
                    "seed": 1,
                }
            )
    value = {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-operation-relevance-contract-v1",
        "status": "frozen-before-execution",
        "implementation_freeze": IMPLEMENTATION_FREEZE,
        "salt": SALT,
        "algorithm": {
            "case_order": "ascending salted SHA256",
            "condition_order": "ascending salted SHA256 within case",
        },
        "case_file": str(CASES.relative_to(ROOT)),
        "case_file_sha256": sha256(CASES),
        "selection_provenance": str(SELECTION.relative_to(ROOT)),
        "selection_provenance_sha256": sha256(SELECTION),
        "preregistration": str(PREREGISTRATION.relative_to(ROOT)),
        "preregistration_sha256": sha256(PREREGISTRATION),
        "model": MODEL,
        "episode_timeout_seconds": 22_200,
        "execution": {
            "config": str(CONFIG.relative_to(ROOT)),
            "config_sha256": sha256(CONFIG),
            "protocol": str(PROTOCOL.relative_to(ROOT)),
            "protocol_sha256": sha256(PROTOCOL),
            "coordinator": "experiments/run_envsolve_pro_schedule.py",
            "initial_host": "mac",
        },
        "episodes": episodes,
    }
    OUTPUT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
