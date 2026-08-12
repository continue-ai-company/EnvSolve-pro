#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.adapters.registry import create_benchmark_adapter
from envsolve_harness.adapters.infrastructure import (
    envbench_evaluation_infrastructure_signature,
)
from envsolve_harness.audit import audit_run
from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import load_case, read_json, read_jsonl, write_json, write_text_atomic
from envsolve_harness.core.models import RunSpec, SolverResult
from envsolve_harness.core.protocol import load_protocol
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest, update_manifest
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a bootstrap script with a benchmark adapter.")
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=WORKSPACE_ROOT / "experiments/configs/local_mac.json")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=WORKSPACE_ROOT / "experiments/protocols/envbench_python_official_v1.json",
    )
    parser.add_argument("--method", default="manual-script")
    parser.add_argument("--model")
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--source-run",
        type=Path,
        help="Audit-valid run whose infrastructure-censored official evaluation is retried",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _existing_retry(config_runs: Path, source_run_id: str, case_id: str) -> str | None:
    for manifest_path in config_runs.glob("*/*/manifest.json"):
        try:
            manifest = read_json(manifest_path)
        except (OSError, TypeError, ValueError):
            continue
        metadata = ((manifest.get("solver") or {}).get("metadata") or {})
        retry = metadata.get("evaluation_retry")
        if (
            isinstance(retry, dict)
            and retry.get("source_run_id") == source_run_id
            and retry.get("source_case_id") == case_id
        ):
            result = manifest.get("result")
            if isinstance(result, dict):
                result_metadata = result.get("metadata") or {}
                adapter_error = str(result_metadata.get("adapter_error") or "")
                launcher_never_started = (
                    result.get("raw_result_path") is None
                    and result_metadata.get("harness_process_exit_code") is None
                    and adapter_error.startswith("FileNotFoundError:")
                    and "No such file or directory: 'uv'" in adapter_error
                )
                if launcher_never_started:
                    continue
            return str((manifest.get("run") or {}).get("run_id"))
    return None


def _prepare_evaluation_retry(
    source_root: Path,
    script_path: Path,
    artifacts: RunArtifacts,
    case_id: str,
    method: str,
) -> SolverResult:
    source_root = source_root.resolve()
    report = audit_run(source_root)
    if not report.valid:
        raise ValueError(f"Source run is not audit-valid: {report.errors}")
    source_manifest = read_json(source_root / "manifest.json")
    source_case = source_manifest.get("case") or {}
    if source_case.get("case_id") != case_id:
        raise ValueError("Source run case does not match the retry case")
    source_result = source_manifest.get("result") or {}
    if source_result.get("official_pass") is True:
        raise ValueError("A passing official evaluation is not retry-eligible")
    raw_relative = source_result.get("raw_result_path")
    source_raw_result_sha256: str | None = None
    if isinstance(raw_relative, str):
        source_raw_result_path = source_root / raw_relative
        source_raw_result_sha256 = sha256_file(source_raw_result_path)
        raw_records = read_jsonl(source_raw_result_path)
        if len(raw_records) > 1:
            raise ValueError("Source run contains multiple raw official results")
        if raw_records:
            source_evidence = raw_records[0]
            source_evidence_path = source_raw_result_path
            source_evidence_kind = "official-raw-result"
        else:
            adapter_result_path = source_root / "evaluation/result.json"
            adapter_result = read_json(adapter_result_path)
            evaluation_log_path = source_root / "logs/evaluation.log"
            evaluation_log = evaluation_log_path.read_text(encoding="utf-8")
            metadata = adapter_result.get("metadata") or {}
            source_evidence = {
                "exit_code": metadata.get("harness_process_exit_code"),
                "pyright": {},
                "container_logs": evaluation_log,
                "adapter_result": adapter_result,
            }
            source_evidence_path = evaluation_log_path
            source_evidence_kind = "adapter-result-with-evaluation-log"
    else:
        source_evidence_path = source_root / "evaluation/result.json"
        source_evidence = read_json(source_evidence_path)
        source_evidence_kind = "adapter-result"
    signature = envbench_evaluation_infrastructure_signature(source_evidence)
    if signature is None:
        raise ValueError("Source official result is not an eligible infrastructure failure")

    source_script = source_root / "scripts/bootstrap.sh"
    source_script_sha256 = sha256_file(source_script)
    if sha256_file(script_path) != source_script_sha256:
        raise ValueError("Retry script does not exactly match the frozen source bootstrap")
    source_run = source_manifest.get("run") or {}
    provenance = {
        "schema_version": "1.0.0",
        "policy": "single-exact-script-infrastructure-retry-v1",
        "source_run_id": source_run.get("run_id"),
        "source_case_id": case_id,
        "source_method": source_run.get("method"),
        "source_script_sha256": source_script_sha256,
        "source_result_sha256": sha256_file(source_root / "evaluation/result.json"),
        "source_raw_result_sha256": source_raw_result_sha256,
        "source_evidence_sha256": sha256_file(source_evidence_path),
        "source_evidence_kind": source_evidence_kind,
        "infrastructure_signature": signature,
        "model_reexecuted": False,
        "max_retries": 1,
    }
    write_json(artifacts.root / "inputs/evaluation_retry.json", provenance)
    write_json(artifacts.root / "inputs/source_raw_result.json", source_evidence)
    write_text_atomic(artifacts.generated_script, script_path.read_text(encoding="utf-8"))
    solver = SolverResult(
        generation_completed=True,
        method=method,
        script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
        metadata={
            "runner": "evaluation-retry-v1",
            "audit_requirements": {"evaluation_retry": True},
            "evaluation_retry": provenance,
        },
    )
    write_json(artifacts.solver_result, solver.to_dict())
    update_manifest(artifacts, solver=solver.to_dict())
    return solver


def main() -> int:
    args = parse_args()
    case = load_case(args.case_file.resolve(), args.case_id)
    protocol = load_protocol(args.protocol.resolve())
    config = load_harness_config(args.config.resolve(), WORKSPACE_ROOT)
    if args.source_run is not None and args.overwrite:
        raise ValueError("Infrastructure evaluation retries cannot use --overwrite")
    if args.source_run is not None:
        source_manifest = read_json(args.source_run.resolve() / "manifest.json")
        source_run_id = str((source_manifest.get("run") or {}).get("run_id"))
        existing = _existing_retry(config.runs_root, source_run_id, case.case_id)
        if existing is not None:
            raise RuntimeError(
                f"Infrastructure evaluation retry already exists: {existing}"
            )
    try:
        artifacts = RunArtifacts.create(
            config.runs_root,
            args.run_id,
            case.case_id,
            overwrite=args.overwrite,
        )
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    run_spec = RunSpec(run_id=args.run_id, method=args.method, model=args.model, seed=args.seed)
    initialize_manifest(artifacts, config, case, run_spec, protocol)
    if args.source_run is not None:
        _prepare_evaluation_retry(
            args.source_run,
            args.script.resolve(),
            artifacts,
            case.case_id,
            args.method,
        )
    result = create_benchmark_adapter(config, protocol).evaluate(
        case, args.script.resolve(), artifacts, run_spec
    )

    print(f"artifacts={artifacts.root}")
    print(f"evaluation_completed={str(result.evaluation_completed).lower()}")
    print(f"official_pass={str(result.official_pass).lower()}")
    print(f"benchmark={result.benchmark}")
    print(f"raw_metrics={result.raw_metrics}")
    return 0 if result.evaluation_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
