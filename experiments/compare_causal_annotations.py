#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


ROW_ID_FIELDS = (
    "case_id",
    "method",
    "generation_run_id",
    "evaluation_run_id",
)


def _row_id(record: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(record.get(field) for field in ROW_ID_FIELDS)


def _label(record: dict[str, Any]) -> str | None:
    annotation = record.get("annotation")
    value = (
        annotation.get("primary_layer")
        if isinstance(annotation, dict)
        else record.get("primary_layer")
    )
    return value if isinstance(value, str) and value else None


def compare(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    first_records = first.get("records")
    second_records = second.get("records")
    if not isinstance(first_records, list) or not isinstance(second_records, list):
        raise ValueError("Both annotation documents require record arrays")

    first_by_id = {
        _row_id(record): record
        for record in first_records
        if isinstance(record, dict)
    }
    second_by_id = {
        _row_id(record): record
        for record in second_records
        if isinstance(record, dict)
    }
    if len(first_by_id) != len(first_records) or len(second_by_id) != len(
        second_records
    ):
        raise ValueError("Annotation documents contain duplicate or malformed rows")
    if set(first_by_id) != set(second_by_id):
        raise ValueError("Annotation documents do not cover identical rows")

    pairs = []
    missing_second = []
    for row_id in first_by_id:
        first_label = _label(first_by_id[row_id])
        second_label = _label(second_by_id[row_id])
        if first_label is None:
            raise ValueError(f"First annotation is missing a label: {row_id}")
        if second_label is None:
            missing_second.append(row_id)
            continue
        pairs.append((first_label, second_label))

    if not pairs:
        return {
            "schema": "envsolve-pro-causal-annotation-agreement-v1",
            "coverage": {
                "rows": len(first_by_id),
                "compared_rows": 0,
                "missing_second_labels": len(missing_second),
            },
            "agreement": None,
        }

    labels = sorted({label for pair in pairs for label in pair})
    first_counts = Counter(first_label for first_label, _ in pairs)
    second_counts = Counter(second_label for _, second_label in pairs)
    observed = sum(a == b for a, b in pairs) / len(pairs)
    expected = sum(
        (first_counts[label] / len(pairs)) * (second_counts[label] / len(pairs))
        for label in labels
    )
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0
    confusion = {
        first_label: {
            second_label: sum(
                a == first_label and b == second_label for a, b in pairs
            )
            for second_label in labels
        }
        for first_label in labels
    }
    return {
        "schema": "envsolve-pro-causal-annotation-agreement-v1",
        "coverage": {
            "rows": len(first_by_id),
            "compared_rows": len(pairs),
            "missing_second_labels": len(missing_second),
        },
        "agreement": {
            "exact_count": sum(a == b for a, b in pairs),
            "exact_rate": observed,
            "expected_rate": expected,
            "cohen_kappa": kappa,
            "labels": labels,
            "first_counts": dict(sorted(first_counts.items())),
            "second_counts": dict(sorted(second_counts.items())),
            "confusion_first_by_second": confusion,
        },
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two evidence-linked causal annotation documents."
    )
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = compare(_read(args.first), _read(args.second))
    rendered = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
