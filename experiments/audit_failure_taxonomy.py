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
    records = document.get("records")
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError(f"Expected records array in {source}")
    return records


def _row_id(record: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(record.get(field) for field in ROW_ID_FIELDS)


def _taxonomy_labels(taxonomy: dict[str, Any]) -> tuple[set[str], set[str]]:
    dimensions = taxonomy.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("Taxonomy requires dimensions")
    primary = dimensions.get("primary_failure_layer")
    censoring = dimensions.get("censoring")
    if not isinstance(primary, dict) or not isinstance(censoring, dict):
        raise ValueError("Taxonomy requires primary failure and censoring labels")
    return set(primary), set(censoring)


def _resolve_artifact(
    run_id: str, relative_path: str, run_roots: list[Path]
) -> Path | None:
    for root in run_roots:
        run_directory = root / run_id
        direct = run_directory / relative_path
        if direct.is_file():
            return direct
        if run_directory.is_dir():
            nested = [
                child / relative_path
                for child in run_directory.iterdir()
                if child.is_dir() and (child / relative_path).is_file()
            ]
            if len(nested) == 1:
                return nested[0]
    return None


def audit(
    matrix: dict[str, Any],
    annotations: dict[str, Any],
    taxonomy: dict[str, Any],
    *,
    run_roots: list[Path] | None = None,
) -> dict[str, Any]:
    run_roots = run_roots or []
    matrix_records = _records(matrix, source="evidence matrix")
    annotation_records = _records(annotations, source="annotations")
    matrix_by_id = {_row_id(record): record for record in matrix_records}
    if len(matrix_by_id) != len(matrix_records):
        raise ValueError("Evidence matrix contains duplicate row identifiers")

    primary_labels, censoring_labels = _taxonomy_labels(taxonomy)
    allowed_labels = primary_labels | censoring_labels
    method_profiles = taxonomy.get("method_profiles")
    if not isinstance(method_profiles, dict):
        raise ValueError("Taxonomy requires method_profiles")

    by_method: dict[str, Counter[str]] = defaultdict(Counter)
    overall: Counter[str] = Counter()
    missing_rows: list[list[Any]] = []
    structural_errors: list[dict[str, Any]] = []
    artifact_checks: Counter[str] = Counter()
    artifact_checks_by_method: dict[str, Counter[str]] = defaultdict(Counter)
    seen: set[tuple[Any, ...]] = set()

    for record in annotation_records:
        row_id = _row_id(record)
        if row_id in seen:
            structural_errors.append(
                {"row_id": row_id, "error": "duplicate_annotation"}
            )
            continue
        seen.add(row_id)
        matrix_record = matrix_by_id.get(row_id)
        if matrix_record is None:
            structural_errors.append({"row_id": row_id, "error": "missing_matrix_row"})
            continue

        label = record.get("primary_layer")
        if label not in allowed_labels:
            structural_errors.append(
                {"row_id": row_id, "error": "invalid_primary_layer", "value": label}
            )
            continue
        method = str(record.get("method"))
        if method not in method_profiles:
            structural_errors.append(
                {"row_id": row_id, "error": "missing_method_profile", "value": method}
            )
        if record.get("terminal_stage") != matrix_record.get("terminal_stage"):
            structural_errors.append(
                {"row_id": row_id, "error": "terminal_stage_drift"}
            )

        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            structural_errors.append({"row_id": row_id, "error": "missing_evidence"})
            evidence = []
        for item in evidence:
            if not isinstance(item, dict):
                structural_errors.append(
                    {"row_id": row_id, "error": "malformed_evidence"}
                )
                continue
            run_id = item.get("run_id")
            relative_path = item.get("relative_path")
            anchor = item.get("anchor")
            values = (run_id, relative_path, anchor)
            if not all(isinstance(value, str) and value for value in values):
                structural_errors.append(
                    {"row_id": row_id, "error": "incomplete_evidence_anchor"}
                )
                continue
            if run_roots:
                resolved = _resolve_artifact(run_id, relative_path, run_roots)
                artifact_status = "found" if resolved else "not_found_in_supplied_roots"
                artifact_checks[artifact_status] += 1
                artifact_checks_by_method[method][artifact_status] += 1
            else:
                artifact_checks["not_checked"] += 1
                artifact_checks_by_method[method]["not_checked"] += 1

        overall[str(label)] += 1
        by_method[method][str(label)] += 1

    for record in matrix_records:
        if record.get("terminal_stage") == "success":
            continue
        row_id = _row_id(record)
        if row_id not in seen:
            missing_rows.append(list(row_id))

    causal_labels = primary_labels - {"unresolved"}
    algorithmic_count = sum(overall[label] for label in causal_labels)
    unresolved_count = overall["unresolved"]
    censored_count = sum(overall[label] for label in censoring_labels)
    algorithmic_distribution = {
        label: {
            "count": overall[label],
            "share": overall[label] / algorithmic_count if algorithmic_count else None,
        }
        for label in sorted(causal_labels)
    }

    return {
        "schema": "envsolve-pro-failure-taxonomy-audit-v2",
        "study_id": annotations.get("study_id"),
        "annotation_status": annotations.get("status"),
        "claim_scope": annotations.get("claim_scope"),
        "coverage": {
            "matrix_rows": len(matrix_records),
            "non_success_rows": sum(
                record.get("terminal_stage") != "success" for record in matrix_records
            ),
            "annotation_rows": len(annotation_records),
            "missing_annotation_rows": len(missing_rows),
            "algorithmic_rows": algorithmic_count,
            "unresolved_rows": unresolved_count,
            "censored_rows": censored_count,
        },
        "algorithmic_distribution": algorithmic_distribution,
        "by_method": {
            method: {
                "profile": method_profiles.get(method),
                "failure_counts": dict(sorted(counts.items())),
            }
            for method, counts in sorted(by_method.items())
        },
        "evidence_artifacts": dict(sorted(artifact_checks.items())),
        "evidence_artifacts_by_method": {
            method: dict(sorted(counts.items()))
            for method, counts in sorted(artifact_checks_by_method.items())
        },
        "missing_annotation_row_ids": missing_rows,
        "structural_errors": structural_errors,
        "valid": not missing_rows and not structural_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and summarize evidence-linked EnvSolve-Pro failure labels."
    )
    parser.add_argument("matrix", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("taxonomy", type=Path)
    parser.add_argument("--run-root", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit(
        _read_object(args.matrix),
        _read_object(args.annotations),
        _read_object(args.taxonomy),
        run_roots=args.run_root,
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
