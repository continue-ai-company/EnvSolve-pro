#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from io import StringIO
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, write_json, write_text_atomic


def _model_usage(solver_metadata: dict[str, Any]) -> dict[str, Any]:
    online_usage = (solver_metadata.get("online_budget") or {}).get("usage")
    if isinstance(online_usage, dict):
        return {
            "model_requests": online_usage.get("requests_started"),
            "model_responses": online_usage.get("responses_completed"),
            "model_request_errors": online_usage.get("request_errors"),
            "input_tokens": online_usage.get("input_tokens"),
            "output_tokens": online_usage.get("output_tokens"),
            "cache_read_tokens": online_usage.get("cache_read_tokens"),
            "total_tokens": online_usage.get("total_tokens"),
            "estimated_cost_usd": online_usage.get("estimated_cost_usd"),
        }

    legacy_usage = solver_metadata.get("token_usage") or {}
    return {
        "model_requests": legacy_usage.get("requests"),
        "model_responses": legacy_usage.get("responses"),
        "model_request_errors": legacy_usage.get("request_errors"),
        "input_tokens": legacy_usage.get("input_tokens"),
        "output_tokens": legacy_usage.get("output_tokens"),
        "cache_read_tokens": legacy_usage.get("cache_read_tokens"),
        "total_tokens": legacy_usage.get("total_tokens"),
        "estimated_cost_usd": legacy_usage.get("estimated_cost_usd"),
    }


def _failure_stage(record: dict[str, Any]) -> str:
    if record["generation_completed"] is not True:
        return "generation"
    if record["evaluation_completed"] is not True:
        return "evaluator"
    bootstrap = next(
        (
            item
            for item in record["diagnostic_evidence"]
            if item.get("verifier_id") == "envbench-bootstrap-diagnostic"
        ),
        None,
    )
    if bootstrap is not None:
        if bootstrap.get("passed") is False:
            return "bootstrap"
    elif record["raw_metrics"].get("exit_code") not in (None, 0):
        return "bootstrap"
    return "verification" if record["official_pass"] is not True else "success"


def summarize(run_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for manifest_path in sorted(run_root.glob("*/manifest.json")):
        case_root = manifest_path.parent
        manifest = read_json(manifest_path)
        solver = manifest.get("solver") or {}
        solver_metadata = solver.get("metadata") or {}
        model_usage = _model_usage(solver_metadata)
        distillation = solver_metadata.get("distillation") or {}
        result = manifest.get("result") or {}
        raw_metrics = result.get("raw_metrics") or {}
        evidence = result.get("evidence") or []
        diagnostic_evidence = [
            item
            for item in evidence
            if isinstance(item, dict) and item.get("channel") == "diagnostic"
        ]
        record = {
            "case_id": manifest["case"]["case_id"],
            "repository": manifest["case"]["repository"],
            "revision": manifest["case"]["revision"],
            "split": manifest["case"]["split"],
            "method": manifest["run"]["method"],
            "model": manifest["run"].get("model"),
            "seed": manifest["run"].get("seed"),
            "generation_completed": solver.get("generation_completed"),
            "generation_error": solver.get("error"),
            "evaluation_completed": result.get("evaluation_completed"),
            "official_pass": result.get("official_pass"),
            "benchmark": result.get("benchmark") or manifest["protocol"].get("benchmark"),
            "raw_metrics": raw_metrics,
            "diagnostic_evidence": diagnostic_evidence,
            "execution_time": result.get("execution_time"),
            **model_usage,
            "kept_actions": distillation.get("kept_count"),
            "dropped_actions": distillation.get("dropped_count"),
            "unknown_actions": distillation.get("unknown_count"),
            "audit_valid": audit_run(case_root).valid,
        }
        record["failure_stage"] = _failure_stage(record)
        records.append(record)
    completed = sum(record["evaluation_completed"] is True for record in records)
    passed = sum(record["official_pass"] is True for record in records)

    def total(field: str) -> int:
        return sum(value for record in records if isinstance((value := record[field]), int))

    def decimal_total(field: str) -> float:
        return sum(
            float(value)
            for record in records
            if isinstance((value := record[field]), (int, float))
            and not isinstance(value, bool)
        )

    return {
        "schema_version": "1.1.0",
        "run_root": str(run_root.resolve()),
        "aggregate": {
            "cases": len(records),
            "generation_completed": sum(record["generation_completed"] is True for record in records),
            "evaluation_completed": completed,
            "official_pass": passed,
            "official_pass_rate": passed / len(records) if records else 0.0,
            "model_requests": total("model_requests"),
            "model_responses": total("model_responses"),
            "model_request_errors": total("model_request_errors"),
            "input_tokens": total("input_tokens"),
            "output_tokens": total("output_tokens"),
            "cache_read_tokens": total("cache_read_tokens"),
            "total_tokens": total("total_tokens"),
            "estimated_cost_usd": decimal_total("estimated_cost_usd"),
            "kept_actions": total("kept_actions"),
            "dropped_actions": total("dropped_actions"),
            "unknown_actions": total("unknown_actions"),
            "diagnostic_checks": sum(
                len(record["diagnostic_evidence"]) for record in records
            ),
            "diagnostic_passes": sum(
                item.get("passed") is True
                for record in records
                for item in record["diagnostic_evidence"]
            ),
            "all_audits_valid": all(record["audit_valid"] for record in records),
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize one EnvSolve batch run.")
    parser.add_argument("run_root", type=Path)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    summary = summarize(run_root)
    write_json(run_root / "summary.json", summary)

    output = StringIO()
    records = summary["records"]
    if records:
        writer = csv.DictWriter(output, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    write_text_atomic(run_root / "results.csv", output.getvalue())
    print(json.dumps(summary["aggregate"], indent=2, sort_keys=True))
    return 0 if summary["aggregate"]["all_audits_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
