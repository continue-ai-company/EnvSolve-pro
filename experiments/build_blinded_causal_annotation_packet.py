#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROW_ID_FIELDS = (
    "case_id",
    "method",
    "generation_run_id",
    "evaluation_run_id",
)


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def build_packet(matrix: dict[str, Any]) -> dict[str, Any]:
    records = matrix.get("records")
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError("Evidence matrix must contain an object record array")

    eligible = [
        record for record in records if record.get("terminal_stage") != "success"
    ]
    packet_records = []
    for index, record in enumerate(eligible, 1):
        packet_records.append(
            {
                "annotation_index": index,
                **{field: record.get(field) for field in ROW_ID_FIELDS},
                "case_index": record.get("case_index"),
                "model": record.get("model"),
                "terminal_stage": record.get("terminal_stage"),
                "generation_completed": record.get("generation_completed"),
                "evaluation_completed": record.get("evaluation_completed"),
                "official_pass": record.get("official_pass"),
                "official_metrics": record.get("official_metrics"),
                "missing_import_modules": record.get("missing_import_modules"),
                "artifact_lookup": {
                    "generation_run_id": record.get("generation_run_id"),
                    "evaluation_run_id": record.get("evaluation_run_id"),
                    "inspect_when_present": [
                        "generation/result.json",
                        "generation/trajectory.jsonl",
                        "generation/trajectory.json",
                        "generation/episode.jsonl",
                        "logs/solver.log",
                        "scripts/generated.sh",
                        "evaluation/result.json",
                    ],
                },
                "annotation": {
                    "primary_layer": None,
                    "subtype": None,
                    "evidence": [],
                    "rationale": None,
                    "confidence": None,
                },
            }
        )

    return {
        "schema": "envsolve-pro-blinded-causal-annotation-packet-v1",
        "study_id": matrix.get("study_id"),
        "annotation_role": "independent-second-reviewer",
        "claim_scope": "Consumed-development taxonomy reliability only",
        "instructions": [
            "Inspect the full generation and evaluation trajectory before assigning a label.",
            "Label the earliest unsupported transition that changed the outcome, not the terminal error message.",
            "Use observation when a target-relevant fact was absent, unobserved, or not carried into replay.",
            "Use constraint when observed evidence was not converted into, retained as, or reconciled with a deployment requirement.",
            "Use operation when a represented requirement was not translated into an effective state-changing action and revalidation.",
            "Use protocol_censored when the candidate interface or adapter cannot validly represent the method behavior.",
            "Use infrastructure_unknown when an external execution incident plausibly determines the outcome.",
            "Use unresolved when the available trajectory does not support one primary cause.",
            "Provide at least one raw artifact path and a concise anchor for every annotation.",
            "Do not inspect the first-reviewer annotation or summary until this packet is complete."
        ],
        "allowed_primary_layers": [
            "observation",
            "constraint",
            "operation",
            "protocol_censored",
            "infrastructure_unknown",
            "unresolved"
        ],
        "coverage": {
            "matrix_rows": len(records),
            "non_success_rows": len(eligible),
            "packet_rows": len(packet_records)
        },
        "records": packet_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a label-blinded second-reviewer causal annotation packet."
    )
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    packet = build_packet(_read_object(args.matrix))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(packet, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
