from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

from envsolve_harness.adapters.envbench import _run_envbench_process
from envsolve_harness.adapters.envbench_executor import (
    EnvBenchCandidateExecutor,
    EnvBenchCandidateRequest,
    envbench_feedback_payload,
)
from envsolve_harness.core.io import write_json
from envsolve_harness.core.models import Case
from envsolve_harness.execution.batch import cleanup_case_containers
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the model-free EnvSolve-Pro v7 executor conformance phase."
    )
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--envbench-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    parser.add_argument("--process-timeout", type=int, default=1800)
    parser.add_argument("--container-timeout", type=int, default=900)
    parser.add_argument("--create-container-timeout", type=int, default=600)
    parser.add_argument("--git-fetch-timeout", type=int, default=300)
    return parser.parse_args()


def _load_fixtures(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    fixtures = value.get("fixtures") if isinstance(value, dict) else None
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("Fixture file must contain a non-empty fixtures list")
    return [dict(item) for item in fixtures]


def _warm_source_cache(
    fixtures: list[dict[str, Any]],
    cache_root: Path,
    warmup_root: Path,
    timeout: int,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    identities = {
        (str(item["repository"]), str(item["revision"])) for item in fixtures
    }
    for position, (repository, revision) in enumerate(sorted(identities), start=1):
        destination = warmup_root / f"source-{position}"
        receipt = ExactRevisionSourceCache(cache_root, timeout).acquire(
            repository=repository,
            revision=revision,
            destination=destination,
        )
        receipts.append(receipt)
        shutil.rmtree(destination)
    return receipts


def _matches_expected(payload: dict[str, Any], expected: dict[str, Any]) -> bool:
    missing = payload["missing_imports"]
    expected_missing = expected["missing_imports"]
    missing_matches = (
        missing == [] if expected_missing == "empty" else bool(missing)
    )
    return bool(
        payload["bootstrap"]["terminal_class"] == expected["terminal_class"]
        and payload["bootstrap"]["git_ownership_error"]
        is expected["git_ownership_error"]
        and payload["goal_report"]["present"]
        is expected["goal_report_present"]
        and missing_matches
    )


def main() -> int:
    args = _parse_args()
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Phase 0 output already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    fixtures = _load_fixtures(args.fixtures)
    cache_root = output_root / "source-cache"
    source_receipts = _warm_source_cache(
        fixtures,
        cache_root,
        output_root / "source-warmup",
        args.git_fetch_timeout,
    )
    executor = EnvBenchCandidateExecutor(
        _run_envbench_process,
        ExactRevisionSourceCache,
        cleanup_case_containers,
    )
    fixture_results: list[dict[str, Any]] = []
    for fixture in fixtures:
        fixture_id = str(fixture["fixture_id"])
        case = Case(
            case_id=str(fixture["case_id"]),
            repository=str(fixture["repository"]),
            revision=str(fixture["revision"]),
        )
        observations: dict[str, dict[str, Any]] = {}
        executions: dict[str, dict[str, Any]] = {}
        for mode in ("online", "postepisode"):
            root = output_root / fixture_id / mode
            execution = executor.execute(
                EnvBenchCandidateRequest(
                    case=case,
                    script=str(fixture["script"]),
                    benchmark_root=args.envbench_root.resolve(),
                    benchmark_input=root / "input.jsonl",
                    json_results=root / "json_results",
                    repo_data=root / "repos",
                    temp_dir=root / "tmp",
                    image=args.image,
                    source_cache_root=cache_root,
                    max_workers=1,
                    process_timeout=args.process_timeout,
                    create_container_timeout=args.create_container_timeout,
                    container_timeout=args.container_timeout,
                    git_fetch_timeout=args.git_fetch_timeout,
                    cleanup_root=root,
                )
            )
            observation = envbench_feedback_payload(execution)
            observations[mode] = observation
            executions[mode] = {
                "feedback_disclosed_to_agent": mode == "online",
                "process_returncode": execution.process_returncode,
                "completed": execution.completed,
                "adapter_error": execution.adapter_error,
                "termination": execution.termination,
                "started_at": execution.started_at,
                "finished_at": execution.finished_at,
                "result_path": str(execution.result_path),
                "observation": observation,
            }
            write_json(root / "execution.json", executions[mode])
        expected = dict(fixture["expected"])
        equal = observations["online"] == observations["postepisode"]
        expected_matches = all(
            _matches_expected(observation, expected)
            for observation in observations.values()
        )
        fixture_results.append(
            {
                "fixture_id": fixture_id,
                "equal": equal,
                "expected_matches": expected_matches,
                "passed": equal and expected_matches,
                "executions": executions,
            }
        )
    passed = all(item["passed"] for item in fixture_results)
    summary = {
        "schema_version": "1.0.0",
        "phase": "envsolve-pro-v7-model-free-executor-conformance",
        "passed": passed,
        "source_cache": {
            "policy": "prewarmed-immutable-cache-independent-no-hardlinks-checkout",
            "receipts": source_receipts,
        },
        "fixtures": fixture_results,
    }
    write_json(output_root / "summary.json", summary)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
