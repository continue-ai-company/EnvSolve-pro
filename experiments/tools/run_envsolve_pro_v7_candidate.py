from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("online", "postepisode"), required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--envbench-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    parser.add_argument("--process-timeout", type=int, default=3600)
    parser.add_argument("--container-timeout", type=int, default=2400)
    parser.add_argument("--create-container-timeout", type=int, default=600)
    parser.add_argument("--git-fetch-timeout", type=int, default=900)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Candidate output already exists: {root}")
    case = Case(args.case_id, args.repository, args.revision)
    execution = EnvBenchCandidateExecutor(
        _run_envbench_process,
        ExactRevisionSourceCache,
        cleanup_case_containers,
    ).execute(
        EnvBenchCandidateRequest(
            case=case,
            script=args.script.read_text(encoding="utf-8"),
            benchmark_root=args.envbench_root.resolve(),
            benchmark_input=root / "input.jsonl",
            json_results=root / "json_results",
            repo_data=root / "repos",
            temp_dir=root / "tmp",
            image=args.image,
            source_cache_root=(
                args.cache_root.resolve() if args.cache_root is not None else None
            ),
            max_workers=1,
            process_timeout=args.process_timeout,
            create_container_timeout=args.create_container_timeout,
            container_timeout=args.container_timeout,
            git_fetch_timeout=args.git_fetch_timeout,
            cleanup_root=root,
        )
    )
    observation = envbench_feedback_payload(execution)
    record = {
        "mode": args.mode,
        "feedback_disclosed_to_agent": args.mode == "online",
        "process_returncode": execution.process_returncode,
        "completed": execution.completed,
        "adapter_error": execution.adapter_error,
        "termination": execution.termination,
        "started_at": execution.started_at,
        "finished_at": execution.finished_at,
        "observation": observation,
    }
    write_json(root / "execution.json", record)
    print(json.dumps(record, ensure_ascii=True, sort_keys=True))
    return 0 if execution.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
