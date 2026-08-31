from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
from typing import Any, Callable


RunCommand = Callable[..., subprocess.CompletedProcess[str]]
_SSH_TARGET = re.compile(
    r"^(?:[A-Za-z0-9._-]+@)?(?:[A-Za-z0-9._-]+|\[[0-9A-Fa-f:]+\])$"
)
_REBUILDABLE_TOP_LEVEL_DIRECTORIES = (
    ".nox",
    ".tox",
    ".venv",
    "node_modules",
    "venv",
)


def _absolute_remote_path(value: str) -> str:
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Remote workspace root must be an absolute normalized path")
    return str(path)


def untracked_rebuildable_excludes(
    workspace: Path,
    *,
    run_command: RunCommand = subprocess.run,
) -> tuple[str, ...]:
    """Exclude only top-level rebuildable directories absent from the Git index."""

    if not (workspace / ".git").exists():
        return ()
    excludes: list[str] = []
    for name in _REBUILDABLE_TOP_LEVEL_DIRECTORIES:
        process = run_command(
            ["git", "-C", str(workspace), "ls-files", "-z", "--", name],
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            return ()
        if not process.stdout:
            excludes.append(f"/{name}/")
    return tuple(excludes)


@dataclass
class SshDockerTransport:
    """Quote-safe Docker and workspace transport for one SSH execution host."""

    target: str
    remote_root: str
    ssh_executable: str = "ssh"
    rsync_executable: str = "rsync"
    docker_executable: str = "docker"
    ssh_identity: str | None = None
    ssh_port: int | None = None
    run_command: RunCommand = subprocess.run

    def __post_init__(self) -> None:
        if _SSH_TARGET.fullmatch(self.target) is None:
            raise ValueError("SSH target contains unsupported characters")
        self.remote_root = _absolute_remote_path(self.remote_root)
        if self.ssh_identity is not None and not self.ssh_identity.strip():
            raise ValueError("SSH identity path cannot be empty")
        if self.ssh_port is not None and not 1 <= self.ssh_port <= 65535:
            raise ValueError("SSH port must be between 1 and 65535")

    def ssh_command_prefix(self) -> list[str]:
        command = [self.ssh_executable]
        if self.ssh_identity is not None:
            command.extend(
                ["-i", self.ssh_identity, "-o", "IdentitiesOnly=yes"]
            )
        if self.ssh_port is not None:
            command.extend(["-p", str(self.ssh_port)])
        return command

    def remote_command(self, command: list[str]) -> list[str]:
        if not command:
            raise ValueError("Remote command cannot be empty")
        return [*self.ssh_command_prefix(), "-T", self.target, shlex.join(command)]

    def _rsync_transport(self) -> list[str]:
        prefix = self.ssh_command_prefix()
        if len(prefix) == 1:
            return []
        return ["-e", shlex.join(prefix)]

    def run_remote(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return self.run_command(self.remote_command(command), **kwargs)

    def checked_remote(self, command: list[str], *, timeout: int) -> str:
        process = self.run_remote(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"remote {command[0]} failed: {detail}")
        return process.stdout.strip()

    def docker_command(self, arguments: list[str]) -> list[str]:
        return [self.docker_executable, *arguments]

    def run_docker(self, arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return self.run_remote(self.docker_command(arguments), **kwargs)

    def checked_docker(self, arguments: list[str], *, timeout: int) -> str:
        return self.checked_remote(self.docker_command(arguments), timeout=timeout)

    def workspace_path(self, local_path: Path, namespace: str) -> str:
        digest = hashlib.sha256(str(local_path.resolve()).encode("utf-8")).hexdigest()[:24]
        return str(PurePosixPath(self.remote_root) / namespace / digest)

    def sync_to_remote(self, local_path: Path, remote_path: str, *, timeout: int) -> None:
        remote_path = _absolute_remote_path(remote_path)
        self.checked_remote(["mkdir", "-p", remote_path], timeout=timeout)
        process = self.run_command(
            [
                self.rsync_executable,
                "-a",
                "--delete",
                *self._rsync_transport(),
                f"{local_path.resolve()}/",
                f"{self.target}:{remote_path}/",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"workspace upload failed: {detail}")

    def sync_from_remote(
        self,
        remote_path: str,
        local_path: Path,
        *,
        timeout: int,
        excludes: tuple[str, ...] = (),
    ) -> None:
        remote_path = _absolute_remote_path(remote_path)
        local_path.mkdir(parents=True, exist_ok=True)
        command = [
            self.rsync_executable,
            "-a",
            "--delete",
            *self._rsync_transport(),
        ]
        for pattern in excludes:
            command.extend(["--exclude", pattern])
        command.extend(
            [f"{self.target}:{remote_path}/", f"{local_path.resolve()}/"]
        )
        process = self.run_command(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"workspace download failed: {detail}")


@dataclass
class RemoteExactRevisionSourceCache:
    """Acquire and verify an immutable exact-revision checkout on the SSH host."""

    transport: SshDockerTransport
    timeout: int

    cache_version = "remote-immutable-exact-revision-cache-v1"

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("Remote source-cache timeout must be positive")

    def acquire(
        self,
        *,
        repository: str,
        revision: str,
        destination: Path,
        remote_url: str | None = None,
    ) -> dict[str, Any]:
        if destination.exists():
            raise FileExistsError(f"Source destination already exists: {destination}")
        repository_name = re.sub(r"[^A-Za-z0-9._-]+", "_", repository).strip("_")
        revision_name = re.sub(r"[^A-Za-z0-9._-]+", "_", revision).strip("_")
        if not repository_name or not revision_name:
            raise ValueError("Repository and revision must form non-empty cache keys")
        cache_path = str(
            PurePosixPath(self.transport.remote_root)
            / "_source_cache"
            / self.cache_version
            / repository_name
            / f"{revision_name}.git"
        )
        lock_path = f"{cache_path}.lock"
        source_url = remote_url or f"https://github.com/{repository}.git"
        populate_script = r"""
set -euo pipefail
lock_path=$1
cache_path=$2
source_url=$3
revision=$4
mkdir -p "$(dirname "$cache_path")"
exec 9>"$lock_path"
flock_bin="$(command -v flock || true)"
if [ -z "$flock_bin" ] && [ -x /opt/homebrew/bin/flock ]; then
  flock_bin=/opt/homebrew/bin/flock
fi
test -n "$flock_bin"
"$flock_bin" 9
cache_hit=1
if [ ! -d "$cache_path" ]; then
  cache_hit=0
  temporary="${cache_path}.tmp.$$"
  trap 'rm -rf "$temporary"' EXIT
  git init --bare --quiet "$temporary"
  git --git-dir "$temporary" remote add origin "$source_url"
  fetched=0
  for delay in 0 1 2; do
    if git --git-dir "$temporary" fetch --quiet --depth 1 origin "$revision"; then
      fetched=1
      break
    fi
    sleep "$delay"
  done
  test "$fetched" -eq 1
  fetched_revision=$(git --git-dir "$temporary" rev-parse 'FETCH_HEAD^{commit}')
  test "$fetched_revision" = "$revision"
  git --git-dir "$temporary" update-ref refs/envsolve/exact "$fetched_revision"
  git --git-dir "$temporary" update-ref refs/heads/envsolve-exact "$fetched_revision"
  git --git-dir "$temporary" symbolic-ref HEAD refs/heads/envsolve-exact
  git --git-dir "$temporary" fsck --no-dangling >/dev/null
  mv "$temporary" "$cache_path"
  trap - EXIT
fi
commit=$(git --git-dir "$cache_path" rev-parse 'refs/envsolve/exact^{commit}')
tree=$(git --git-dir "$cache_path" rev-parse 'refs/envsolve/exact^{tree}')
test "$commit" = "$revision"
git --git-dir "$cache_path" fsck --no-dangling >/dev/null
printf 'ENVSOLVE_REMOTE_SOURCE_V1=%s|%s|%s\n' "$cache_hit" "$commit" "$tree"
""".strip()
        output = self.transport.checked_remote(
            [
                "/bin/bash",
                "-lc",
                populate_script,
                "--",
                lock_path,
                cache_path,
                source_url,
                revision,
            ],
            timeout=self.timeout,
        )
        marker = next(
            (
                line.removeprefix("ENVSOLVE_REMOTE_SOURCE_V1=")
                for line in reversed(output.splitlines())
                if line.startswith("ENVSOLVE_REMOTE_SOURCE_V1=")
            ),
            None,
        )
        if marker is None:
            raise RuntimeError("Remote source cache did not emit an identity receipt")
        fields = marker.split("|")
        if len(fields) != 3 or fields[1] != revision:
            raise RuntimeError("Remote source-cache identity receipt is invalid")
        remote_checkout = self.transport.workspace_path(destination, "source")
        self.transport.checked_remote(
            ["rm", "-rf", remote_checkout],
            timeout=self.timeout,
        )
        self.transport.checked_remote(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--no-checkout",
                cache_path,
                remote_checkout,
            ],
            timeout=self.timeout,
        )
        self.transport.checked_remote(
            [
                "git",
                "-C",
                remote_checkout,
                "checkout",
                "--quiet",
                "--detach",
                revision,
            ],
            timeout=self.timeout,
        )
        checked_out = self.transport.checked_remote(
            ["git", "-C", remote_checkout, "rev-parse", "HEAD"],
            timeout=self.timeout,
        )
        if checked_out != revision:
            raise RuntimeError(f"Remote checkout resolved {checked_out}, expected {revision}")
        self.transport.sync_from_remote(
            remote_checkout,
            destination,
            timeout=self.timeout,
        )
        return {
            "source": self.cache_version,
            "cache_hit": fields[0] == "1",
            "cache_path": cache_path,
            "remote_checkout_path": remote_checkout,
            "repository": repository,
            "revision": revision,
            "commit": fields[1],
            "tree": fields[2],
            "fsck": "pass",
            "checkout": "independent-no-hardlinks",
            "acquisition_host_role": "spark-execution-host",
        }


@dataclass
class RemoteDockerCommandAdapter:
    """Run local checkout commands locally and Docker commands on the SSH host."""

    transport: SshDockerTransport
    sync_timeout: int
    expose_gpus: bool = False
    local_run_command: RunCommand = subprocess.run
    _mounts: dict[str, tuple[Path, str, str, tuple[str, ...]]] = field(
        default_factory=dict,
        init=False,
    )
    _remote_owner: str | None = field(default=None, init=False)

    @staticmethod
    def _docker_action(command: list[str]) -> str | None:
        if not command or Path(command[0]).name != "docker" or len(command) < 2:
            return None
        return command[1]

    @staticmethod
    def _exec_container_id(command: list[str]) -> str | None:
        options_with_values = {
            "--detach-keys",
            "--env",
            "--env-file",
            "--user",
            "--workdir",
            "-e",
            "-u",
            "-w",
        }
        index = 2
        while index < len(command):
            value = command[index]
            if value in options_with_values:
                index += 2
                continue
            if value.startswith("-"):
                index += 1
                continue
            return value
        return None

    def _remote_mount_command(
        self,
        command: list[str],
    ) -> tuple[list[str], Path, str, str, tuple[str, ...]]:
        rewritten = list(command)
        mount_index = rewritten.index("--mount") + 1
        fields = rewritten[mount_index].split(",")
        source_index = next(
            index for index, field in enumerate(fields) if field.startswith("src=")
        )
        destination = next(
            field.split("=", 1)[1]
            for field in fields
            if field.startswith(("dst=", "target="))
        )
        local_path = Path(fields[source_index][len("src=") :]).resolve()
        remote_path = self.transport.workspace_path(local_path, "replay")
        self.transport.sync_to_remote(local_path, remote_path, timeout=self.sync_timeout)
        fields[source_index] = f"src={remote_path}"
        rewritten[mount_index] = ",".join(fields)
        if self.expose_gpus:
            rewritten[2:2] = ["--gpus", "all"]
        excludes = untracked_rebuildable_excludes(
            local_path,
            run_command=self.local_run_command,
        )
        return rewritten, local_path, remote_path, destination, excludes

    def _host_owner(self) -> str:
        if self._remote_owner is None:
            uid = self.transport.checked_remote(["id", "-u"], timeout=self.sync_timeout)
            gid = self.transport.checked_remote(["id", "-g"], timeout=self.sync_timeout)
            self._remote_owner = f"{uid}:{gid}"
        return self._remote_owner

    def _chown_mount(
        self,
        container_id: str,
        container_path: str,
        owner: str,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        return self.transport.run_remote(
            [
                "docker",
                "exec",
                "--user",
                "0:0",
                container_id,
                "chown",
                "-R",
                owner,
                container_path,
            ],
            **kwargs,
        )

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        action = self._docker_action(command)
        if action is None:
            return self.local_run_command(command, **kwargs)

        rewritten = list(command)
        pending_mount: tuple[Path, str, str, tuple[str, ...]] | None = None
        if action == "create" and "--mount" in command:
            rewritten, local_path, remote_path, container_path, excludes = (
                self._remote_mount_command(command)
            )
            pending_mount = (local_path, remote_path, container_path, excludes)
        process = self.transport.run_remote(rewritten, **kwargs)
        if action == "create" and process.returncode == 0 and pending_mount is not None:
            container_id = process.stdout.strip()
            if container_id:
                self._mounts[container_id] = pending_mount
        elif action == "start" and len(command) >= 3 and process.returncode == 0:
            mount = self._mounts.get(command[2])
            if mount is not None:
                ownership = self._chown_mount(command[2], mount[2], "0:0", **kwargs)
                if ownership.returncode != 0:
                    return ownership
        elif action == "exec":
            container_id = self._exec_container_id(command)
            mount = self._mounts.get(container_id or "")
            if mount is not None:
                ownership = self._chown_mount(
                    container_id or "",
                    mount[2],
                    self._host_owner(),
                    **kwargs,
                )
                if ownership.returncode != 0:
                    return ownership
                self.transport.sync_from_remote(
                    mount[1],
                    mount[0],
                    timeout=self.sync_timeout,
                    excludes=mount[3],
                )
        elif action == "rm":
            for value in command[2:]:
                if not value.startswith("-"):
                    self._mounts.pop(value, None)
        return process
