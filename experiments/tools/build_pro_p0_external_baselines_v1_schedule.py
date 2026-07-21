#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "experiments/cases/dev_pro_p0_external_baselines_v1_5.jsonl"
SELECTION = (
    ROOT / "experiments/validations/pro_p0_external_baselines_v1_selection.json"
)
OUTPUT = ROOT / "experiments/validations/pro_p0_external_baselines_v1_schedule.json"
SALT = "envsolve-pro-p0-external-baselines-v1-2026-07-21"
METHODS = (
    {
        "method_id": "codex-cli-native",
        "runner": "codex-cli",
        "method": "codex-cli-native",
        "model": "gpt-5.5",
        "checkout": "envsolve-pro-frozen-execution-revision",
    },
    {
        "method_id": "repo2run-reproduced",
        "runner": "repo2run",
        "method": "repo2run",
        "model": "deepseek/deepseek-v4-pro",
        "checkout": "envsolve-pro-frozen-execution-revision",
    },
    {
        "method_id": "envbench-raw-react",
        "runner": "envbench-agent",
        "method": "envbench-react-freeagent",
        "model": "deepseek/deepseek-v4-pro",
        "checkout": "envsolve-pro-frozen-execution-revision",
    },
    {
        "method_id": "envsolve-v1-frozen",
        "runner": "envsolve",
        "method": "envsolve-full",
        "model": "deepseek/deepseek-v4-pro",
        "checkout": "07a208f9b2390a36ad64f0c0d7cedf00423a889e",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(*parts: str) -> str:
    return hashlib.sha256((SALT + "\0" + "\0".join(parts)).encode()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"Refusing to overwrite schedule: {OUTPUT}")
    rows = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 5 or len({row["case_id"] for row in rows}) != 5:
        raise RuntimeError("P0 requires exactly five selected cases")
    rows.sort(key=lambda row: digest("case-order", str(row["case_id"])))

    episodes = []
    for case_index, row in enumerate(rows, start=1):
        case_id = str(row["case_id"])
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
                    "run_id": (
                        f"pro-p0-v1-c{case_index:02d}-{method['method_id']}"
                    ),
                    "seed": None,
                    **method,
                }
            )
    value = {
        "schema_version": "1.0.0",
        "salt": SALT,
        "algorithm": {
            "case_order": "ascending SHA256(salt + NUL + case-order + NUL + case_id)",
            "method_order": "ascending SHA256(salt + NUL + method-order + NUL + case_id + NUL + method_id)",
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
