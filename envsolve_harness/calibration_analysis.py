from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


def classify_calibration_outcome(
    internal_passed: bool | None,
    evaluation_completed: bool,
    official_pass: bool,
) -> str:
    if not evaluation_completed:
        return "official_unknown"
    if internal_passed is False and official_pass:
        return "internal_false_official_true"
    if internal_passed is False and not official_pass:
        return "internal_false_official_false"
    if internal_passed is True and official_pass:
        return "internal_true_official_true"
    if internal_passed is True and not official_pass:
        return "internal_true_official_false"
    return "internal_unknown_official_true" if official_pass else "internal_unknown_official_false"


def _run_root(binding: dict[str, Any], runs_root: Path) -> Path:
    return (
        runs_root
        / safe_name(str(binding["calibration_run_id"]))
        / safe_name(str(binding["case_id"]))
    ).resolve()


def _analyze_binding(
    binding: dict[str, Any],
    runs_root: Path,
    workspace_root: Path,
    expected_evaluator: dict[str, Any],
) -> dict[str, Any]:
    root = _run_root(binding, runs_root)
    report = audit_run(root)
    if not report.valid:
        raise ValueError(f"Calibration run failed audit: {root}: {report.errors}")

    result_path = root / "evaluation" / "result.json"
    manifest_path = root / "manifest.json"
    result = read_json(result_path)
    manifest = read_json(manifest_path)
    selected = binding["selected_candidate"]
    frozen_script = workspace_root / str(selected["frozen_script_path"])
    script_sha256 = str(selected["script_sha256"])
    manifest_script = manifest.get("script") or {}
    if sha256_file(frozen_script) != script_sha256:
        raise ValueError(f"Frozen script changed after binding: {frozen_script}")
    if manifest_script.get("sha256") != script_sha256:
        raise ValueError(f"Evaluated script does not match binding: {root}")

    evaluator = manifest.get("evaluator") or {}
    image = evaluator.get("image") or {}
    if evaluator.get("revision") != expected_evaluator.get("revision"):
        raise ValueError(f"Evaluator revision drift: {root}")
    if evaluator.get("dirty") is not False:
        raise ValueError(f"Evaluator source was dirty: {root}")
    if image.get("id") != expected_evaluator.get("image_id"):
        raise ValueError(f"Evaluator image ID drift: {root}")
    if expected_evaluator.get("image_digest") not in image.get("repo_digests", []):
        raise ValueError(f"Evaluator image digest drift: {root}")

    raw_relative = result.get("raw_result_path")
    if not isinstance(raw_relative, str):
        raise ValueError(f"Calibration run has no raw result: {root}")
    raw_path = root / raw_relative
    raw_records = read_jsonl(raw_path)
    if len(raw_records) != 1:
        raise ValueError(f"Calibration run must have exactly one raw result: {root}")

    completed = bool(result.get("evaluation_completed"))
    official_pass = bool(result.get("official_pass"))
    internal_passed = selected.get("internal_passed")
    raw_metrics = result.get("raw_metrics") or {}
    metadata = result.get("metadata") or {}
    termination = metadata.get("termination") or {}
    return {
        **{
            key: binding.get(key)
            for key in (
                "position",
                "pair_index",
                "case_id",
                "run_id",
                "method",
                "seed",
                "calibration_run_id",
            )
        },
        "candidate_id": selected.get("candidate_id"),
        "script_sha256": script_sha256,
        "audit_valid": True,
        "result_sha256": sha256_file(result_path),
        "raw_result_sha256": sha256_file(raw_path),
        "evaluation_completed": completed,
        "official_pass": official_pass,
        "calibration_outcome": classify_calibration_outcome(
            internal_passed, completed, official_pass
        ),
        "bootstrap_exit_code": raw_metrics.get("exit_code"),
        "pyright_error_count": raw_metrics.get("error_count"),
        "pyright_warning_count": raw_metrics.get("warning_count"),
        "issues_count": raw_metrics.get("issues_count"),
        "execution_time_seconds": result.get("execution_time"),
        "identity_matches": metadata.get("identity_matches"),
        "termination_kind": termination.get("kind"),
        "termination_signature": termination.get("signature"),
    }


def _aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = Counter(str(run["calibration_outcome"]) for run in runs)
    return {
        "runs": len(runs),
        "audit_valid": sum(bool(run["audit_valid"]) for run in runs),
        "evaluation_completed": sum(bool(run["evaluation_completed"]) for run in runs),
        "official_unknown": sum(not bool(run["evaluation_completed"]) for run in runs),
        "official_pass": sum(bool(run["official_pass"]) for run in runs),
        "bootstrap_succeeded": sum(run["bootstrap_exit_code"] == 0 for run in runs),
        "pyright_observed": sum(run["pyright_error_count"] is not None for run in runs),
        "outcomes": dict(sorted(outcomes.items())),
    }


def analyze_terminal_calibration(
    binding_path: Path,
    preregistration_path: Path,
    runs_root: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    binding_path = binding_path.resolve()
    preregistration_path = preregistration_path.resolve()
    bindings = read_json(binding_path)
    preregistration = read_json(preregistration_path)
    expected_binding_sha256 = (preregistration.get("selection") or {}).get(
        "binding_sha256"
    )
    if sha256_file(binding_path) != expected_binding_sha256:
        raise ValueError("Binding manifest does not match preregistration")
    records = bindings.get("bindings")
    if not isinstance(records, list) or len(records) != bindings.get("count"):
        raise ValueError("Binding manifest count is invalid")

    expected_evaluator = preregistration.get("evaluator") or {}
    runs = [
        _analyze_binding(
            dict(binding),
            runs_root.resolve(),
            workspace_root.resolve(),
            expected_evaluator,
        )
        for binding in records
    ]
    methods = {
        method: _aggregate([run for run in runs if run.get("method") == method])
        for method in sorted({str(run.get("method")) for run in runs})
    }
    return {
        "schema_version": "1.0.0",
        "preregistration": {
            "path": str(preregistration_path.relative_to(workspace_root.resolve())),
            "sha256": sha256_file(preregistration_path),
        },
        "bindings": {
            "path": str(binding_path.relative_to(workspace_root.resolve())),
            "sha256": sha256_file(binding_path),
        },
        "aggregate": _aggregate(runs),
        "methods": methods,
        "runs": runs,
    }
