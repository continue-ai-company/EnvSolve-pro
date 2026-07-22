#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "experiments/cases/train_untouched_after_pro_p2_dominant_contradiction_v1_112.jsonl"
)
SELECTED = ROOT / "experiments/cases/dev_pro_trajectory_census_v1_8.jsonl"
REMAINING = ROOT / "experiments/cases/train_untouched_after_pro_trajectory_census_v1_104.jsonl"
PREREGISTRATION = (
    ROOT / "experiments/validations/pro_trajectory_census_v1_preregistration.json"
)
PROVENANCE = ROOT / "experiments/validations/pro_trajectory_census_v1_selection.json"
SALT = "envsolve-pro-trajectory-census-v1-2026-07-22"
EXPECTED_SOURCE_SHA256 = (
    "13d7710cf5331161f7fa6e3bf814c86d578b43a5cbc0dddb06cfc717f7ebf491"
)
SAMPLE_SIZE = 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(payload, encoding="utf-8")


def main() -> int:
    if sha256(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched trajectory census source pool hash changed")
    if not PREREGISTRATION.is_file():
        raise RuntimeError("Trajectory census must be preregistered before selection")
    for output in (SELECTED, REMAINING, PROVENANCE):
        if output.exists():
            raise RuntimeError(f"Refusing to overwrite selection artifact: {output}")

    rows = [
        json.loads(line)
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 112 or len({row["case_id"] for row in rows}) != 112:
        raise RuntimeError("Unexpected trajectory census source pool")
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            (SALT + "\0" + str(row["case_id"])).encode()
        ).hexdigest(),
    )
    selected_ids = {row["case_id"] for row in ranked[:SAMPLE_SIZE]}
    selected = [
        {**row, "split": "dev-pro-trajectory-census-v1-8"}
        for row in rows
        if row["case_id"] in selected_ids
    ]
    remaining = [
        {
            **row,
            "split": "train-untouched-after-pro-trajectory-census-v1-104",
        }
        for row in rows
        if row["case_id"] not in selected_ids
    ]
    write_jsonl(SELECTED, selected)
    write_jsonl(REMAINING, remaining)
    provenance = {
        "schema_version": "1.0.0",
        "preregistration": str(PREREGISTRATION.relative_to(ROOT)),
        "preregistration_sha256": sha256(PREREGISTRATION),
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "salt": SALT,
        "algorithm": "ascending SHA256(salt + NUL + case_id)",
        "selected_case_ids": [row["case_id"] for row in selected],
        "selected_path": str(SELECTED.relative_to(ROOT)),
        "selected_sha256": sha256(SELECTED),
        "remaining_path": str(REMAINING.relative_to(ROOT)),
        "remaining_sha256": sha256(REMAINING),
    }
    PROVENANCE.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
