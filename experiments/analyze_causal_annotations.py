#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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


def _records(document: dict[str, Any], *, source: str) -> list[dict[str, Any]]:
    values = document.get("records")
    if not isinstance(values, list) or not all(
        isinstance(value, dict) for value in values
    ):
        raise ValueError(f"Expected records array in {source}")
    return values


def _row_id(record: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(record.get(field) for field in ROW_ID_FIELDS)


def join_annotations(
    matrix: dict[str, Any], annotations: dict[str, Any]
) -> list[dict[str, Any]]:
    matrix_records = _records(matrix, source="evidence matrix")
    annotation_records = _records(annotations, source="causal annotations")
    matrix_by_id: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in matrix_records:
        key = _row_id(record)
        if key in matrix_by_id:
            raise ValueError(f"Duplicate evidence-matrix row: {key}")
        matrix_by_id[key] = record

    seen: set[tuple[Any, ...]] = set()
    joined: list[dict[str, Any]] = []
    for annotation in annotation_records:
        key = _row_id(annotation)
        if key in seen:
            raise ValueError(f"Duplicate causal annotation: {key}")
        seen.add(key)
        matrix_record = matrix_by_id.get(key)
        if matrix_record is None:
            raise ValueError(f"Annotation has no evidence-matrix row: {key}")
        if annotation.get("terminal_stage") != matrix_record.get("terminal_stage"):
            raise ValueError(f"Terminal-stage mismatch for annotation: {key}")
        evidence = annotation.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"Annotation has no evidence anchors: {key}")
        joined.append({**matrix_record, "causal_annotation": annotation})
    return joined


def summarize(
    matrix: dict[str, Any], annotations: dict[str, Any]
) -> dict[str, Any]:
    joined = join_annotations(matrix, annotations)
    matrix_records = _records(matrix, source="evidence matrix")
    eligible = [
        record
        for record in matrix_records
        if record.get("terminal_stage") != "success"
    ]
    by_method: dict[str, Counter[str]] = defaultdict(Counter)
    by_terminal_stage: dict[str, Counter[str]] = defaultdict(Counter)
    overall: Counter[str] = Counter()
    for record in joined:
        annotation = record["causal_annotation"]
        label = str(annotation["primary_layer"])
        overall[label] += 1
        by_method[str(record["method"])][label] += 1
        by_terminal_stage[str(record["terminal_stage"])][label] += 1

    return {
        "schema": "envsolve-pro-causal-annotation-summary-v1",
        "study_id": annotations.get("study_id"),
        "annotation_status": annotations.get("status"),
        "claim_scope": annotations.get("claim_scope"),
        "coverage": {
            "matrix_rows": len(matrix_records),
            "non_success_rows": len(eligible),
            "annotated_rows": len(joined),
            "remaining_non_success_rows": len(eligible) - len(joined),
        },
        "primary_layer_counts": dict(sorted(overall.items())),
        "by_method": {
            method: dict(sorted(counts.items()))
            for method, counts in sorted(by_method.items())
        },
        "by_terminal_stage": {
            stage: dict(sorted(counts.items()))
            for stage, counts in sorted(by_terminal_stage.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and summarize provisional causal annotations."
    )
    parser.add_argument("matrix", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = summarize(_read_object(args.matrix), _read_object(args.annotations))
    rendered = json.dumps(summary, indent=2, sort_keys=False) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
