#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "experiments/cases/dev_pro_p2_dominant_contradiction_v1_6.jsonl"
SELECTION = (
    ROOT / "experiments/validations/pro_p2_dominant_contradiction_v1_selection.json"
)
OUTPUT = (
    ROOT / "experiments/validations/pro_p2_dominant_contradiction_v1_schedule.json"
)
SALT = "envsolve-pro-p2-dominant-contradiction-v1-2026-07-21"
P1_FREEZE_REVISION = "38dae3be1f575f61297e7cbbe48229abeb8866db"
METHODS = (
    {
        "method_id": "codex-cli-native",
        "runner": "codex-cli",
        "method": "codex-cli-native",
        "model": "gpt-5.5",
    },
    {
        "method_id": "repo2run-reproduced-open",
        "runner": "repo2run",
        "method": "repo2run",
        "model": "deepseek/deepseek-v4-pro",
    },
    {
        "method_id": "envbench-raw-react-open",
        "runner": "envbench-agent",
        "method": "envbench-react-freeagent",
        "model": "deepseek/deepseek-v4-pro",
    },
    {
        "method_id": "envsolve-pro-p1-scaffold",
        "runner": "envsolve",
        "method": "envsolve-pro",
        "model": "deepseek/deepseek-v4-pro",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(*parts: str) -> str:
    return hashlib.sha256((SALT + "\0" + "\0".join(parts)).encode()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"Refusing to overwrite schedule: {OUTPUT}")
    if not SELECTION.is_file():
        raise RuntimeError("P2 metadata selection must run before schedule construction")
    rows = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 6 or len({row["case_id"] for row in rows}) != 6:
        raise RuntimeError("P2 requires exactly six selected cases")
    rows.sort(key=lambda row: digest("case-order", str(row["case_id"])))

    episodes = []
    for case_index, row in enumerate(rows, start=1):
        case_id = str(row["case_id"])
        case_seed = int(digest("seed", case_id)[:8], 16)
        methods = sorted(
            METHODS,
            key=lambda method: digest(
                "method-order", case_id, str(method["method_id"])
            ),
        )
        for method_index, method in enumerate(methods, start=1):
            episodes.append(
                {
                    "position": len(episodes) + 1,
                    "case_index": case_index,
                    "method_index": method_index,
                    "case_id": case_id,
                    "host": "unbound-until-execution",
                    "run_id": f"pro-p2-v1-c{case_index:02d}-{method['method_id']}",
                    "seed": case_seed,
                    "checkout": P1_FREEZE_REVISION,
                    **method,
                }
            )
    value = {
        "schema_version": "1.0.0",
        "salt": SALT,
        "p1_freeze_revision": P1_FREEZE_REVISION,
        "algorithm": {
            "case_order": "ascending salted SHA256",
            "method_order": "ascending salted SHA256 within case",
            "seed": "first 32 bits of salted SHA256(seed, case_id)",
        },
        "case_file": str(CASES.relative_to(ROOT)),
        "case_file_sha256": sha256(CASES),
        "selection_provenance": str(SELECTION.relative_to(ROOT)),
        "selection_provenance_sha256": sha256(SELECTION),
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
