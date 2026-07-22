from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable
import uuid

from packaging.version import InvalidVersion, Version

from envsolve.constraints import InitialConstraintEvidence

from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    ProvisionedEnvironment,
)
from envsolve.runtime.workspace import WorkspacePrecondition


RunCommand = Callable[..., subprocess.CompletedProcess[str]]
_BASE_RUNTIME_MARKER = "ENVSOLVE_BASE_RUNTIME_V2="


@dataclass(frozen=True)
class BaseRuntimeObservation:
    """Fresh, read-only observation of the candidate image's runtime and platform."""

    image: str
    image_digest: str
    python_implementation: str
    python_version: str
    sys_platform: str
    platform_name: str
    machine: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(item, str) and item.strip()
            for item in (
                self.image,
                self.image_digest,
                self.python_implementation,
                self.python_version,
                self.sys_platform,
                self.platform_name,
                self.machine,
            )
        ):
            raise ValueError("Base runtime observation fields cannot be empty")
        try:
            normalized = str(Version(self.python_version))
        except InvalidVersion as exc:
            raise ValueError("Base runtime observation has an invalid version") from exc
        object.__setattr__(self, "python_version", normalized)

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": "envsolve-base-runtime-observation-v2",
            "image": self.image,
            "image_digest": self.image_digest,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "sys_platform": self.sys_platform,
            "platform_name": self.platform_name,
            "machine": self.machine,
        }

    def constraint_evidence(self) -> InitialConstraintEvidence:
        value = {
            "name": "python",
            "version": self.python_version,
            "implementation": self.python_implementation,
            "sys_platform": self.sys_platform,
            "platform_name": self.platform_name,
            "machine": self.machine,
            "image": self.image,
            "image_digest": self.image_digest,
        }
        semantic = {
            "kind": "runtime-observation",
            "source": f"fresh-base-runtime:{self.image_digest}",
            "value": value,
        }
        digest = hashlib.sha256(
            json.dumps(
                semantic, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        return InitialConstraintEvidence(
            evidence_id=f"base-runtime-observation-{digest[:24]}",
            kind=semantic["kind"],
            source=semantic["source"],
            value=value,
        )

    def platform_constraint_evidence(self) -> tuple[InitialConstraintEvidence, ...]:
        values = {
            "sys_platform": self.sys_platform,
            "platform_name": self.platform_name,
            "machine": self.machine,
        }
        evidence: list[InitialConstraintEvidence] = []
        for name, value in sorted(values.items()):
            semantic = {
                "kind": "platform-observation",
                "source": f"fresh-base-runtime:{self.image_digest}",
                "value": {
                    "name": name,
                    "value": value,
                    "image": self.image,
                    "image_digest": self.image_digest,
                },
            }
            digest = hashlib.sha256(
                json.dumps(
                    semantic,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            evidence.append(
                InitialConstraintEvidence(
                    evidence_id=f"base-platform-observation-{digest[:24]}",
                    kind=str(semantic["kind"]),
                    source=str(semantic["source"]),
                    value=dict(semantic["value"]),
                )
            )
        return tuple(evidence)


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
        workspace_preconditions: tuple[WorkspacePrecondition, ...] = (),
        create_timeout: int = 180,
        run_command: RunCommand = subprocess.run,
    ) -> None:
        self.source_repository = source_repository.resolve()
        self.worktrees_root = worktrees_root.resolve()
        self.repository = repository
        self.revision = revision
        self.image = image
        self.workspace_preconditions = workspace_preconditions
        self.create_timeout = create_timeout
        self.run_command = run_command
        self.base_image_digest: str | None = None
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

    def observe_base_runtime(self) -> BaseRuntimeObservation:
        """Observe Python in a fresh, network-disabled instance of the base image."""
        image_digest = self._checked(
            ["docker", "image", "inspect", "--format", "{{.Id}}", self.image],
            "Docker image identity",
        )
        probe = (
            "import json, platform, sys; "
            f"print({_BASE_RUNTIME_MARKER!r} + json.dumps({{"
            "'python_implementation': platform.python_implementation(), "
            "'python_version': platform.python_version(), "
            "'sys_platform': sys.platform, "
            "'platform_name': platform.system(), "
            "'machine': platform.machine()"
            "}, sort_keys=True))"
        )
        process = self._run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--entrypoint",
                "python",
                image_digest,
                "-I",
                "-c",
                probe,
            ]
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"Base runtime observation failed: {detail}")
        payloads = [
            line[len(_BASE_RUNTIME_MARKER) :]
            for line in process.stdout.splitlines()
            if line.startswith(_BASE_RUNTIME_MARKER)
        ]
        if len(payloads) != 1:
            raise RuntimeError("Base runtime observation produced an invalid report")
        try:
            payload = json.loads(payloads[0])
            implementation = payload["python_implementation"]
            version = payload["python_version"]
            sys_platform = payload["sys_platform"]
            platform_name = payload["platform_name"]
            machine = payload["machine"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError("Base runtime observation report is malformed") from exc
        observation = BaseRuntimeObservation(
            image=self.image,
            image_digest=image_digest,
            python_implementation=str(implementation),
            python_version=str(version),
            sys_platform=str(sys_platform),
            platform_name=str(platform_name),
            machine=str(machine),
        )
        self.base_image_digest = image_digest
        return observation

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
            for precondition in self.workspace_preconditions:
                precondition.materialize(worktree)
            image_digest = self._checked(
                ["docker", "image", "inspect", "--format", "{{.Id}}", self.image],
                "Docker image identity",
            )
            if (
                self.base_image_digest is not None
                and image_digest != self.base_image_digest
            ):
                raise RuntimeError(
                    "Docker image identity changed after base-runtime observation"
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
                    image_digest,
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
        ownership = self._run(
            [
                "docker",
                "exec",
                "--user",
                "0:0",
                handle.container_id,
                "chown",
                "-R",
                f"{os.getuid()}:{os.getgid()}",
                handle.container_workdir,
            ]
        )
        process = self._run(["docker", "rm", "-f", handle.container_id])
        if handle.worktree.exists():
            try:
                shutil.rmtree(handle.worktree)
            except OSError as exc:
                ownership_detail = ownership.stderr.strip() or ownership.stdout.strip()
                if ownership.returncode != 0 and ownership_detail:
                    raise RuntimeError(
                        "Docker worktree cleanup failed after ownership restoration "
                        f"failed: {ownership_detail}"
                    ) from exc
                raise RuntimeError(f"Docker worktree cleanup failed: {exc}") from exc
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"Docker container release failed: {detail}")
