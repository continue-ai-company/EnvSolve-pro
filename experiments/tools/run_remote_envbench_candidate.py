#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from envsolve_harness.adapters.envbench_executor import (
    EnvBenchCandidateExecutor,
    EnvBenchCandidateRequest,
    envbench_feedback_payload,
)
from envsolve_harness.adapters.envbench_remote import RemoteEnvBenchProcessRunner
from envsolve_harness.core.io import write_json
from envsolve_harness.core.models import Case
from envsolve_harness.execution.remote_docker import SshDockerTransport
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one program through a remote EnvBench candidate executor."
    )
    parser.add_argument("--mode", choices=("online", "postepisode"), required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--local-envbench-root", type=Path, required=True)
    parser.add_argument("--remote-envbench-root", required=True)
    parser.add_argument("--remote-workspace-root", required=True)
    parser.add_argument("--source-cache-root", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ssh-target", required=True)
    parser.add_argument("--ssh-executable", default="ssh")
    parser.add_argument("--ssh-identity")
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--docker", default="docker")
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    parser.add_argument("--process-timeout", type=int, default=3600)
    parser.add_argument("--container-timeout", type=int, default=2400)
    parser.add_argument("--create-container-timeout", type=int, default=600)
    parser.add_argument("--git-fetch-timeout", type=int, default=900)
    parser.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args()

    root = args.output_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Candidate output already exists: {root}")
    transport = SshDockerTransport(
        target=args.ssh_target,
        remote_root=args.remote_workspace_root,
        ssh_executable=args.ssh_executable,
        docker_executable=args.docker,
        ssh_identity=args.ssh_identity,
        ssh_port=args.ssh_port,
    )
    process_runner = RemoteEnvBenchProcessRunner(
        transport=transport,
        local_benchmark_root=args.local_envbench_root,
        remote_benchmark_root=args.remote_envbench_root,
        local_benchmark_input=root / "input.jsonl",
        local_json_results=root / "json",
        local_repo_data=root / "repos",
        local_temp_dir=root / "tmp",
        remote_run_root=transport.workspace_path(root, "candidate"),
        image=args.image,
        sync_timeout=max(
            args.git_fetch_timeout,
            args.create_container_timeout,
        ),
    )
    case = Case(args.case_id, args.repository, args.revision)
    try:
        execution = EnvBenchCandidateExecutor(
            process_runner,
            ExactRevisionSourceCache,
            process_runner.cleanup_containers,
        ).execute(
            EnvBenchCandidateRequest(
                case=case,
                script=args.script.read_text(encoding="utf-8"),
                benchmark_root=args.local_envbench_root.resolve(),
                benchmark_input=root / "input.jsonl",
                json_results=root / "json",
                repo_data=root / "repos",
                temp_dir=root / "tmp",
                image=args.image,
                source_cache_root=(
                    args.source_cache_root.resolve()
                    if args.source_cache_root is not None
                    else None
                ),
                max_workers=args.max_workers,
                process_timeout=args.process_timeout,
                create_container_timeout=args.create_container_timeout,
                container_timeout=args.container_timeout,
                git_fetch_timeout=args.git_fetch_timeout,
                cleanup_root=root,
            )
        )
    finally:
        try:
            process_runner.cleanup_staging()
        except Exception as exc:
            process_runner.execution_metadata["staging_cleanup_error"] = (
                f"{type(exc).__name__}: {exc}"
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
        "execution_backend": process_runner.execution_metadata,
        "observation": observation,
    }
    write_json(root / "execution.json", record)
    print(json.dumps(record, ensure_ascii=True, sort_keys=True))
    return 0 if execution.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
