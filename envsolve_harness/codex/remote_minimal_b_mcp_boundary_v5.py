#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve_harness.boundary_v5 import (
    BoundaryV5OfficialAlignedExecutableGoalVerifier,
    BoundaryV5OpenCandidateProgramValidator,
)
from envsolve_harness.codex.minimal_b_mcp import CleanReplayService, MinimalBMcpServer
from envsolve_harness.codex.remote_container_mcp import (
    SshProcessTreeSafePersistentContainerShell,
)
from envsolve_harness.core.io import read_json
from envsolve_harness.execution.remote_docker import (
    RemoteDockerCommandAdapter,
    SshDockerTransport,
)
from envsolve_harness.integrity.repository import inspect_repository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SSH-backed EnvSolve-Pro Minimal B MCP server."
    )
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--workdir", default="/data/project")
    parser.add_argument("--command-trace", type=Path, required=True)
    parser.add_argument("--replay-trace", type=Path, required=True)
    parser.add_argument("--certification", type=Path, required=True)
    parser.add_argument("--programs-root", type=Path, required=True)
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--worktrees", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--goal-contract", type=Path, required=True)
    parser.add_argument("--workspace-preconditions", type=Path, required=True)
    parser.add_argument("--command-timeout", type=int, required=True)
    parser.add_argument("--container-create-timeout", type=int, required=True)
    parser.add_argument("--max-output-chars", type=int, default=16000)
    parser.add_argument("--ssh-target", required=True)
    parser.add_argument("--remote-workspace-root", required=True)
    parser.add_argument("--ssh-executable", default="ssh")
    parser.add_argument("--ssh-identity")
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--expose-gpus", action="store_true")
    return parser.parse_args()


def _workspace_preconditions(path: Path) -> tuple[WorkspacePrecondition, ...]:
    value = read_json(path)
    if not isinstance(value, list):
        raise ValueError("workspace preconditions must be an array")
    return tuple(WorkspacePrecondition(**item) for item in value)


def build_server(args: argparse.Namespace) -> MinimalBMcpServer:
    contract = ExecutableGoalContract.from_dict(read_json(args.goal_contract))
    preconditions = _workspace_preconditions(args.workspace_preconditions)
    transport = SshDockerTransport(
        target=args.ssh_target,
        remote_root=args.remote_workspace_root,
        ssh_executable=args.ssh_executable,
        docker_executable=args.docker,
        ssh_identity=args.ssh_identity,
        ssh_port=args.ssh_port,
    )
    adapter = RemoteDockerCommandAdapter(
        transport,
        sync_timeout=max(args.command_timeout, args.container_create_timeout),
        expose_gpus=args.expose_gpus,
    )
    provider = DockerFreshEnvironmentProvider(
        source_repository=args.source_repository,
        worktrees_root=args.worktrees,
        repository=args.repository,
        revision=args.revision,
        image=args.image,
        workspace_preconditions=preconditions,
        create_timeout=args.container_create_timeout,
        run_command=adapter,
    )
    verifier = BoundaryV5OfficialAlignedExecutableGoalVerifier(
        contract,
        observation_timeout=args.command_timeout,
        effect_auditor=lambda worktree: inspect_repository(
            worktree,
            args.revision,
            required_preconditions=preconditions,
        ),
        run_command=adapter,
    )
    replay_service = CleanReplayService(
        provider=provider,
        verifier=verifier,
        repository=args.repository,
        revision=args.revision,
        image_digest=args.image,
        goal_contract_sha256=contract.sha256,
        trace_path=args.replay_trace,
        certification_path=args.certification,
        programs_root=args.programs_root,
        max_output_chars=args.max_output_chars,
    )
    replay_service.validator = BoundaryV5OpenCandidateProgramValidator()
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
    return MinimalBMcpServer(executor, args.command_trace, replay_service)


def main() -> int:
    server = build_server(parse_args())
    server.serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
