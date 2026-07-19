#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "experiments/cases/dev_operation_qualification_v2_5.jsonl"
OUTPUT = ROOT / "experiments/validations/p6_operation_qualification_v2_schedule.json"
SELECTION = ROOT / "experiments/validations/p6_operation_qualification_v2_selection.json"
SALT = "envsolve-p6-operation-qualification-v2-2026-07-17"
METHODS = ("envsolve-operation-ablation", "envsolve-operation")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(label: str, case_id: str) -> str:
    return hashlib.sha256(
        (SALT + "\0" + label + "\0" + case_id).encode()
    ).hexdigest()


def main() -> int:
    rows = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 5:
        raise RuntimeError("Q2 requires exactly five selected cases")
    rows.sort(key=lambda row: digest("case-order", str(row["case_id"])))
    episodes = []
    for pair_index, row in enumerate(rows, start=1):
        case_id = str(row["case_id"])
        methods = list(METHODS)
        if int(digest("method-order", case_id), 16) % 2:
            methods.reverse()
        for method_index, method in enumerate(methods, start=1):
            episodes.append(
                {
                    "position": len(episodes) + 1,
                    "pair_index": pair_index,
                    "method_index": method_index,
                    "case_id": case_id,
                    "method": method,
                    "run_id": f"p6-operation-q2-{pair_index:02d}-{method}",
                    "seed": 0,
                }
            )
    value = {
        "schema_version": "1.0.0",
        "salt": SALT,
        "algorithm": {
            "case_order": "ascending SHA256(salt + NUL + case-order + NUL + case_id)",
            "method_order": "ablation/full, reversed by salted method-order hash parity",
        },
        "case_file": str(CASES.relative_to(ROOT)),
        "case_file_sha256": sha256(CASES),
        "selection_provenance": str(SELECTION.relative_to(ROOT)),
        "selection_provenance_sha256": sha256(SELECTION),
        "model": "deepseek/deepseek-v4-pro",
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

