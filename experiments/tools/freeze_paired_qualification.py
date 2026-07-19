#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_jsonl
from envsolve_harness.utils.provenance import sha256_file


def _path(root: Path, value: object) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        raise ValueError("Qualification paths must be workspace-relative")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Qualification path escapes workspace: {path}") from exc
    return resolved


def _digest(salt: str, label: str, case_id: str) -> str:
    return hashlib.sha256(
        (salt + "\0" + label + "\0" + case_id).encode("utf-8")
    ).hexdigest()


def build_qualification_outputs(
    root: Path,
    preregistration_path: Path,
) -> dict[str, tuple[Path, Any]]:
    preregistration_path = preregistration_path.resolve()
    preregistration = read_json(preregistration_path)
    if preregistration.get("status") != "registered_before_selection":
        raise ValueError("Qualification must be registered before selection")
    selection = preregistration.get("selection") or {}
    schedule_spec = preregistration.get("schedule") or {}
    if selection.get("algorithm") != "ascending SHA256(salt + NUL + case_id)":
        raise ValueError("Unsupported qualification selection algorithm")
    if selection.get("metadata_only") is not True:
        raise ValueError("Qualification selection must be metadata-only")
    source = _path(root, selection.get("source"))
    if not source.is_file() or sha256_file(source) != selection.get("source_sha256"):
        raise ValueError("Untouched source pool hash changed")
    rows = read_jsonl(source)
    source_count = int(selection.get("source_count", -1))
    if len(rows) != source_count or len({row.get("case_id") for row in rows}) != source_count:
        raise ValueError("Untouched source pool identity/count mismatch")
    count = int(selection.get("count", 0))
    if count <= 0 or count >= source_count:
        raise ValueError("Selection count must preserve a non-empty untouched pool")
    salt = str(selection.get("salt"))
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            (salt + "\0" + str(row["case_id"])).encode("utf-8")
        ).hexdigest(),
    )
    selected_ids = {str(row["case_id"]) for row in ranked[:count]}
    selected = [
        {**row, "split": str(selection["selected_split"])}
        for row in rows
        if str(row["case_id"]) in selected_ids
    ]
    remaining = [
        {**row, "split": str(selection["remaining_split"])}
        for row in rows
        if str(row["case_id"]) not in selected_ids
    ]
    selected_path = _path(root, selection.get("selected_path"))
    remaining_path = _path(root, selection.get("remaining_path"))

    selected_payload = "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in selected
    )
    remaining_payload = "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in remaining
    )
    selected_hash = hashlib.sha256(selected_payload.encode("utf-8")).hexdigest()
    remaining_hash = hashlib.sha256(remaining_payload.encode("utf-8")).hexdigest()
    provenance_path = _path(root, selection.get("provenance_path"))
    provenance = {
        "schema_version": "1.0.0",
        "preregistration": str(preregistration_path.relative_to(root.resolve())),
        "preregistration_sha256": sha256_file(preregistration_path),
        "source": str(source.relative_to(root.resolve())),
        "source_sha256": selection["source_sha256"],
        "salt": salt,
        "algorithm": "ascending SHA256(salt + NUL + case_id)",
        "selected_case_ids": [str(row["case_id"]) for row in selected],
        "selected_path": str(selected_path.relative_to(root.resolve())),
        "selected_sha256": selected_hash,
        "remaining_path": str(remaining_path.relative_to(root.resolve())),
        "remaining_sha256": remaining_hash,
    }

    methods = [str(method) for method in schedule_spec.get("methods", [])]
    if len(methods) != 2 or len(set(methods)) != 2:
        raise ValueError("Paired qualification requires two distinct methods")
    ordered_cases = sorted(
        selected,
        key=lambda row: _digest(salt, "case-order", str(row["case_id"])),
    )
    episodes: list[dict[str, Any]] = []
    run_prefix = str(schedule_spec["run_prefix"])
    for pair_index, row in enumerate(ordered_cases, start=1):
        case_id = str(row["case_id"])
        ordered_methods = list(methods)
        if int(_digest(salt, "method-order", case_id), 16) % 2:
            ordered_methods.reverse()
        for method_index, method in enumerate(ordered_methods, start=1):
            episodes.append(
                {
                    "position": len(episodes) + 1,
                    "pair_index": pair_index,
                    "method_index": method_index,
                    "case_id": case_id,
                    "method": method,
                    "run_id": f"{run_prefix}-{pair_index:02d}-{method}",
                    "seed": int(schedule_spec["seed"]),
                }
            )
    schedule_path = _path(root, schedule_spec.get("output_path"))
    schedule = {
        "schema_version": "1.0.0",
        "salt": salt,
        "algorithm": {
            "case_order": "ascending SHA256(salt + NUL + case-order + NUL + case_id)",
            "method_order": "two methods, reversed by salted method-order hash parity",
        },
        "case_file": str(selected_path.relative_to(root.resolve())),
        "case_file_sha256": selected_hash,
        "selection_provenance": str(provenance_path.relative_to(root.resolve())),
        "model": str(schedule_spec["model"]),
        "episode_timeout_seconds": int(schedule_spec["episode_timeout_seconds"]),
        "episodes": episodes,
    }
    return {
        "selected": (selected_path, selected),
        "remaining": (remaining_path, remaining),
        "provenance": (provenance_path, provenance),
        "schedule": (schedule_path, schedule),
    }


def write_qualification_outputs(outputs: dict[str, tuple[Path, Any]]) -> None:
    conflicts = [str(path) for path, _ in outputs.values() if path.exists()]
    if conflicts:
        raise FileExistsError(f"Qualification outputs already exist: {conflicts}")
    write_jsonl(outputs["selected"][0], outputs["selected"][1])
    write_jsonl(outputs["remaining"][0], outputs["remaining"][1])
    write_json(outputs["provenance"][0], outputs["provenance"][1])
    provenance_hash = sha256_file(outputs["provenance"][0])
    schedule = dict(outputs["schedule"][1])
    schedule["selection_provenance_sha256"] = provenance_hash
    write_json(outputs["schedule"][0], schedule)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize an outcome-blind paired qualification from a preregistration."
    )
    parser.add_argument("--preregistration", type=Path, required=True)
    args = parser.parse_args()
    outputs = build_qualification_outputs(ROOT, args.preregistration)
    write_qualification_outputs(outputs)
    for name, (path, _) in outputs.items():
        print(f"{name}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
