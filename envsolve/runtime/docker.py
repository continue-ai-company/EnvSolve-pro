from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable
import uuid

from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    ProvisionedEnvironment,
)


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class DockerEnvironmentHandle:
    container_id: str
    worktree: Path
    container_workdir: str


class DockerFreshEnvironmentProvider:
    """Provision a distinct clean checkout and Docker container per candidate."""

    def __init__(
        self,
        *,
        source_repository: Path,
        worktrees_root: Path,
        repository: str,
        revision: str,
        image: str,
        create_timeout: int = 180,
        run_command: RunCommand = subprocess.run,
    ) -> None:
        self.source_repository = source_repository.resolve()
        self.worktrees_root = worktrees_root.resolve()
        self.repository = repository
        self.revision = revision
        self.image = image
        self.create_timeout = create_timeout
        self.run_command = run_command
        if not self.source_repository.is_dir():
            raise ValueError("Fresh environment source repository is missing")

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self.run_command(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=self.create_timeout,
        )

    def _checked(self, command: list[str], label: str) -> str:
        process = self._run(command)
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"{label} failed: {detail}")
        return process.stdout.strip()

    def provision(self, candidate: DeploymentCandidate) -> ProvisionedEnvironment:
        nonce = uuid.uuid4().hex
        worktree = self.worktrees_root / f"{candidate.candidate_id}-{nonce}"
        self.worktrees_root.mkdir(parents=True, exist_ok=True)
        container_id: str | None = None
        try:
            self._checked(
                [
                    "git",
                    "clone",
                    "--shared",
                    "--no-checkout",
                    str(self.source_repository),
                    str(worktree),
                ],
                "clean checkout clone",
            )
            self._checked(
                ["git", "-C", str(worktree), "checkout", "--detach", self.revision],
                "clean checkout revision",
            )
            observed_revision = self._checked(
                ["git", "-C", str(worktree), "rev-parse", "HEAD"],
                "clean checkout identity",
            )
            if observed_revision != self.revision:
                raise RuntimeError("Clean checkout does not match the requested revision")
            image_digest = self._checked(
                ["docker", "image", "inspect", "--format", "{{.Id}}", self.image],
                "Docker image identity",
            )
            container_workdir = (
                f"/data/project/{self.repository.replace('/', '__')}@{self.revision}"
            )
            container_id = self._checked(
                [
                    "docker",
                    "create",
                    "--entrypoint",
                    "/bin/bash",
                    "--mount",
                    f"type=bind,src={worktree},dst={container_workdir}",
                    self.image,
                    "-lc",
                    "while true; do sleep 1000; done",
                ],
                "Docker container creation",
            )
            self._checked(["docker", "start", container_id], "Docker container start")
            return ProvisionedEnvironment(
                receipt=EnvironmentReceipt(
                    environment_id=container_id,
                    provider_id="docker-fresh-checkout-v1",
                    image_digest=image_digest,
                    repository=self.repository,
                    revision=self.revision,
                    created_at=datetime.now(timezone.utc).isoformat(),
                ),
                handle=DockerEnvironmentHandle(
                    container_id=container_id,
                    worktree=worktree,
                    container_workdir=container_workdir,
                ),
            )
        except Exception:
            if container_id:
                self._run(["docker", "rm", "-f", container_id])
            if worktree.exists():
                shutil.rmtree(worktree)
            raise

    def release(self, environment: ProvisionedEnvironment) -> None:
        handle = environment.handle
        if not isinstance(handle, DockerEnvironmentHandle):
            raise ValueError("Docker environment lease has an invalid handle")
        process = self._run(["docker", "rm", "-f", handle.container_id])
        if handle.worktree.exists():
            shutil.rmtree(handle.worktree)
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"Docker container release failed: {detail}")
