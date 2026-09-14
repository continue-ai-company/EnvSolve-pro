#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from envsolve.solver import DeploymentCandidate
from envsolve_harness.adapters.envbench_executor import (
    EnvBenchCandidateExecution,
    EnvBenchCandidateExecutor,
    EnvBenchCandidateRequest,
    envbench_feedback_payload,
)
from envsolve_harness.adapters.envbench_remote import RemoteEnvBenchProcessRunner
from envsolve_harness.boundary_v6 import BoundaryV6OpenCandidateProgramValidator
from envsolve_harness.codex.matched_replay_mcp import (
    MatchedEnvBenchMinimalBMcpServer,
    WithheldReplayService,
)
from envsolve_harness.codex.minimal_b_mcp import (
    CERTIFICATION_SCHEMA,
    REPLAY_SCHEMA,
    MinimalBMcpServer,
    canonical_script,
    script_sha256,
)
from envsolve_harness.codex.remote_container_mcp import (
    SshProcessTreeSafePersistentContainerShell,
)
from envsolve_harness.core.io import write_json, write_text_atomic
from envsolve_harness.core.models import Case
from envsolve_harness.execution.remote_docker import SshDockerTransport
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache

EXECUTOR_PROFILE = "envbench-candidate-executor-online-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


CandidateExecution = Callable[
    [str, str], tuple[EnvBenchCandidateExecution, dict[str, Any]]
]


class EnvBenchReplayService:
    """Expose the EnvBench candidate executor as same-session clean replay."""

    def __init__(
        self,
        *,
        case: Case,
        image_digest: str,
        goal_contract_sha256: str,
        trace_path: Path,
        certification_path: Path,
        programs_root: Path,
        execute_candidate: CandidateExecution,
    ) -> None:
        self.case = case
        self.image_digest = image_digest
        self.goal_contract_sha256 = goal_contract_sha256
        self.trace_path = trace_path
        self.certification_path = certification_path
        self.programs_root = programs_root
        self.execute_candidate = execute_candidate
        self.validator = BoundaryV6OpenCandidateProgramValidator()
        self.sequence = 0
        self.certified_programs: list[dict[str, Any]] = []
        self._write_certification()

    def _write_certification(self) -> None:
        write_json(
            self.certification_path,
            {
                "schema": CERTIFICATION_SCHEMA,
                "repository": self.case.repository,
                "revision": self.case.revision,
                "image_digest": self.image_digest,
                "goal_contract_sha256": self.goal_contract_sha256,
                "replay_count": self.sequence,
                "certified_programs": self.certified_programs,
                "updated_at": _now(),
            },
        )

    def _finish(self, result: dict[str, Any]) -> dict[str, Any]:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"recorded_at": _now(), **result},
                    ensure_ascii=True,
                    sort_keys=True,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        self._write_certification()
        return result

    def submit(self, program: str) -> dict[str, Any]:
        self.sequence += 1
        replay_id = f"envbench-replay-{self.sequence:04d}"
        canonical = canonical_script(program)
        digest = script_sha256(canonical)
        program_path = self.programs_root / f"{replay_id}.sh"
        write_text_atomic(program_path, canonical + ("\n" if canonical else ""))
        base: dict[str, Any] = {
            "schema": REPLAY_SCHEMA,
            "executor_profile": EXECUTOR_PROFILE,
            "replay_id": replay_id,
            "replay_index": self.sequence,
            "program_sha256": digest,
            "program_artifact": f"{self.programs_root.name}/{program_path.name}",
            "certified": False,
        }
        candidate = DeploymentCandidate(
            candidate_id=replay_id,
            script=canonical,
            rationale="Complete program submitted for online EnvBench-path replay",
        )
        validation = self.validator.validate(candidate)
        base["candidate_validation"] = {
            "accepted": validation.accepted,
            "policy_id": validation.policy_id,
            "reason": validation.reason,
            "details": validation.details,
        }
        if not canonical or not validation.accepted:
            if not canonical:
                base["candidate_validation"]["reason"] = "candidate program is empty"
            return self._finish(
                {**base, "status": "fail", "phase": "candidate-validation"}
            )

        canonical = canonical_script(validation.normalized_script or canonical)
        digest = script_sha256(canonical)
        base["program_sha256"] = digest
        write_text_atomic(program_path, canonical + "\n")
        try:
            execution, backend = self.execute_candidate(canonical, replay_id)
        except Exception as exc:
            return self._finish(
                {
                    **base,
                    "status": "infrastructure_error",
                    "phase": "target-state-replay",
                    "infrastructure_error": f"{type(exc).__name__}: {exc}",
                }
            )

        feedback = envbench_feedback_payload(execution)
        base["execution_backend"] = backend
        if not execution.completed:
            return self._finish(
                {
                    **base,
                    "status": "infrastructure_error",
                    "phase": "target-state-replay",
                    "infrastructure_error": execution.adapter_error,
                    "feedback": feedback,
                }
            )

        passed = (
            execution.raw.get("exit_code") == 0
            and execution.raw.get("issues_count") == 0
        )
        result = {
            **base,
            "status": "pass" if passed else "fail",
            "phase": "target-state-replay",
            "feedback": feedback,
            "certified": passed,
        }
        if passed:
            receipt = {
                "environment_id": replay_id,
                "repository": self.case.repository,
                "revision": self.case.revision,
                "image_digest": self.image_digest,
                "executor_profile": EXECUTOR_PROFILE,
            }
            certificate = {
                "replay_id": replay_id,
                "program_sha256": digest,
                "environment_receipt": receipt,
                "certified_at": _now(),
            }
            self.certified_programs.append(certificate)
            result["environment_receipt"] = receipt
            result["certificate"] = certificate
        return self._finish(result)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Same-session EnvBench-path target-state replay MCP server."
    )
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--workdir", default="/data/project")
    parser.add_argument("--command-trace", type=Path, required=True)
    parser.add_argument("--replay-trace", type=Path, required=True)
    parser.add_argument("--certification", type=Path, required=True)
    parser.add_argument("--programs-root", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--goal-contract-sha256", required=True)
    parser.add_argument("--local-envbench-root", type=Path, required=True)
    parser.add_argument("--remote-envbench-root", required=True)
    parser.add_argument("--remote-evaluation-root", required=True)
    parser.add_argument("--process-timeout", type=int, required=True)
    parser.add_argument("--container-timeout", type=int, required=True)
    parser.add_argument("--container-create-timeout", type=int, required=True)
    parser.add_argument("--git-fetch-timeout", type=int, required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--command-timeout", type=int, required=True)
    parser.add_argument("--max-output-chars", type=int, default=16000)
    parser.add_argument("--ssh-target", required=True)
    parser.add_argument("--remote-workspace-root", required=True)
    parser.add_argument("--ssh-executable", default="ssh")
    parser.add_argument("--ssh-identity")
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--docker", default="docker")
    parser.add_argument(
        "--feedback-mode",
        choices=("legacy", "real", "withheld"),
        default="legacy",
    )
    return parser.parse_args()


def _build_server(args: argparse.Namespace) -> MinimalBMcpServer:
    evaluation_transport = SshDockerTransport(
        target=args.ssh_target,
        remote_root=args.remote_evaluation_root,
        ssh_executable=args.ssh_executable,
        docker_executable=args.docker,
        ssh_identity=args.ssh_identity,
        ssh_port=args.ssh_port,
    )
    case = Case(args.case_id, args.repository, args.revision)
    execution_root = args.replay_trace.parent / "envbench-executions"

    def execute_candidate(
        program: str, replay_id: str
    ) -> tuple[EnvBenchCandidateExecution, dict[str, Any]]:
        local_root = execution_root / replay_id
        process_runner = RemoteEnvBenchProcessRunner(
            transport=evaluation_transport,
            local_benchmark_root=args.local_envbench_root,
            remote_benchmark_root=args.remote_envbench_root,
            local_benchmark_input=local_root / "input.jsonl",
            local_json_results=local_root / "json",
            local_repo_data=local_root / "repos",
            local_temp_dir=local_root / "tmp",
            remote_run_root=evaluation_transport.workspace_path(
                local_root, replay_id
            ),
            image=args.image,
            sync_timeout=max(
                args.git_fetch_timeout,
                args.container_create_timeout,
            ),
        )
        try:
            execution = EnvBenchCandidateExecutor(
                process_runner,
                ExactRevisionSourceCache,
                process_runner.cleanup_containers,
            ).execute(
                EnvBenchCandidateRequest(
                    case=case,
                    script=program,
                    benchmark_root=args.local_envbench_root,
                    benchmark_input=local_root / "input.jsonl",
                    json_results=local_root / "json",
                    repo_data=local_root / "repos",
                    temp_dir=local_root / "tmp",
                    image=args.image,
                    source_cache_root=None,
                    max_workers=args.max_workers,
                    process_timeout=args.process_timeout,
                    create_container_timeout=args.container_create_timeout,
                    container_timeout=args.container_timeout,
                    git_fetch_timeout=args.git_fetch_timeout,
                    cleanup_root=local_root,
                )
            )
        finally:
            try:
                process_runner.cleanup_staging()
            except Exception as exc:
                process_runner.execution_metadata["staging_cleanup_error"] = (
                    f"{type(exc).__name__}: {exc}"
                )
        return execution, dict(process_runner.execution_metadata)

    if args.feedback_mode == "withheld":
        replay_service = WithheldReplayService(
            repository=case.repository,
            revision=case.revision,
            image_digest=args.image,
            goal_contract_sha256=args.goal_contract_sha256,
            trace_path=args.replay_trace,
            certification_path=args.certification,
            programs_root=args.programs_root,
            replay_id_prefix="envbench-replay",
            phase="target-state-replay",
        )
        replay_service.validator = BoundaryV6OpenCandidateProgramValidator()
    else:
        replay_service = EnvBenchReplayService(
            case=case,
            image_digest=args.image,
            goal_contract_sha256=args.goal_contract_sha256,
            trace_path=args.replay_trace,
            certification_path=args.certification,
            programs_root=args.programs_root,
            execute_candidate=execute_candidate,
        )
    executor = SshProcessTreeSafePersistentContainerShell(
        args.container_id,
        args.workdir,
        args.command_timeout,
        args.max_output_chars,
        args.ssh_target,
        args.ssh_executable,
        args.docker,
        args.ssh_identity,
        args.ssh_port,
    )
    server_type = (
        MinimalBMcpServer
        if args.feedback_mode == "legacy"
        else MatchedEnvBenchMinimalBMcpServer
    )
    return server_type(  # type: ignore[arg-type]
        executor,
        args.command_trace,
        replay_service,
    )


def main() -> int:
    server = _build_server(_parse_args())
    server.serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
