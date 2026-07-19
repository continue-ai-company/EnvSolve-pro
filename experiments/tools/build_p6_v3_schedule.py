#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "experiments/cases/dev_v3_qualification5.jsonl"
OUTPUT = ROOT / "experiments/validations/p6_v3_unseen_dev5_schedule.json"
SELECTION = ROOT / "experiments/validations/p6_v3_unseen_dev5_selection.json"
SALT = "envsolve-p6-v3-qualification-v1-2026-07-16"
METHODS = ("envsolve-runtime-only", "envsolve-full")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(label: str, case_id: str) -> str:
    return hashlib.sha256((SALT + "\0" + label + "\0" + case_id).encode()).hexdigest()


def main() -> int:
    rows = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
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
                    "run_id": f"p6-v3-q1-{pair_index:02d}-{method}",
                    "seed": 0,
                }
            )
    value = {
        "schema_version": "1.0.0",
        "salt": SALT,
        "algorithm": {
            "case_order": "ascending SHA256(salt + NUL + case-order + NUL + case_id)",
            "method_order": "runtime-only/full, reversed when SHA256(salt + NUL + method-order + NUL + case_id) is odd",
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
