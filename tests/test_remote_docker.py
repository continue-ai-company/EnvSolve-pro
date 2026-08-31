from __future__ import annotations

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

from envsolve_harness.codex.remote_container_mcp import (
    SshProcessTreeSafePersistentContainerShell,
)
from envsolve_harness.execution.remote_docker import (
    RemoteExactRevisionSourceCache,
    RemoteDockerCommandAdapter,
    SshDockerTransport,
    untracked_rebuildable_excludes,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.remote_root = "/srv/envsolve"
        self.docker_executable = "docker"
        self.remote_commands: list[list[str]] = []
        self.uploads: list[tuple[Path, str]] = []
        self.downloads: list[tuple[str, Path, tuple[str, ...]]] = []

    def workspace_path(self, local_path: Path, namespace: str) -> str:
        return f"/srv/envsolve/{namespace}/workspace"

    def sync_to_remote(self, local_path: Path, remote_path: str, *, timeout: int) -> None:
        self.uploads.append((local_path, remote_path))

    def sync_from_remote(
        self,
        remote_path: str,
        local_path: Path,
        *,
        timeout: int,
        excludes: tuple[str, ...] = (),
    ) -> None:
        self.downloads.append((remote_path, local_path, excludes))

    def checked_remote(self, command: list[str], *, timeout: int) -> str:
        return "1000"

    def requires_bind_mount_chown(self, *, timeout: int) -> bool:
        return True

    def run_remote(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.remote_commands.append(command)
        stdout = "container-1\n" if command[1] == "create" else ""
        return subprocess.CompletedProcess(command, 0, stdout, "")


class SshDockerTransportTest(unittest.TestCase):
    def test_remote_source_cache_acquires_and_downloads_exact_revision(self) -> None:
        revision = "a" * 40

        class SourceTransport(RecordingTransport):
            def checked_remote(self, command: list[str], *, timeout: int) -> str:
                self.remote_commands.append(command)
                if command[:2] == ["/bin/bash", "-lc"]:
                    return f"ENVSOLVE_REMOTE_SOURCE_V1=0|{revision}|{'b' * 40}"
                if command[:3] == ["git", "-C", "/srv/envsolve/source/workspace"]:
                    return revision
                return ""

            def sync_from_remote(
                self,
                remote_path: str,
                local_path: Path,
                *,
                timeout: int,
                excludes: tuple[str, ...] = (),
            ) -> None:
                local_path.mkdir(parents=True)
                self.downloads.append((remote_path, local_path, excludes))

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "checkout"
            transport = SourceTransport()

            receipt = RemoteExactRevisionSourceCache(
                transport,  # type: ignore[arg-type]
                timeout=30,
            ).acquire(
                repository="owner/repo",
                revision=revision,
                destination=destination,
            )

            self.assertEqual(receipt["commit"], revision)
            self.assertFalse(receipt["cache_hit"])
            self.assertEqual(receipt["acquisition_host_role"], "spark-execution-host")
            self.assertEqual(
                transport.downloads,
                [("/srv/envsolve/source/workspace", destination, ())],
            )
            populate = transport.remote_commands[0]
            self.assertEqual(populate[:2], ["/bin/bash", "-lc"])
            self.assertIn('"$flock_bin" 9', populate[2])

    def test_rebuildable_excludes_never_hide_tracked_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            subprocess.run(["git", "init", "-q", workspace], check=True)
            (workspace / ".venv").mkdir()
            (workspace / ".venv" / "tracked.txt").write_text("tracked\n")
            subprocess.run(
                ["git", "-C", str(workspace), "add", ".venv/tracked.txt"],
                check=True,
            )

            excludes = untracked_rebuildable_excludes(workspace)

            self.assertNotIn("/.venv/", excludes)
            self.assertIn("/env/", excludes)
            self.assertIn("/node_modules/", excludes)

    def test_tracked_env_directory_is_not_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            subprocess.run(["git", "init", "-q", workspace], check=True)
            (workspace / "env").mkdir()
            (workspace / "env" / "tracked.txt").write_text("tracked\n")
            subprocess.run(
                ["git", "-C", str(workspace), "add", "env/tracked.txt"],
                check=True,
            )

            excludes = untracked_rebuildable_excludes(workspace)

            self.assertNotIn("/env/", excludes)

    def test_remote_command_quotes_each_argument_once(self) -> None:
        transport = SshDockerTransport("user@spark", "/srv/envsolve")
        command = ["docker", "exec", "container", "bash", "-lc", "printf '%s' 'a b'"]

        rendered = transport.remote_command(command)

        self.assertEqual(rendered[:3], ["ssh", "-T", "user@spark"])
        self.assertEqual(
            rendered[3],
            shlex.join(
                [
                    "/usr/bin/env",
                    "PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                    *command,
                ]
            ),
        )

    def test_remote_command_exposes_homebrew_filter_processes(self) -> None:
        transport = SshDockerTransport("user@agenthub", "/srv/envsolve")

        rendered = transport.remote_command(
            ["git", "-C", "/srv/source", "checkout", "revision"]
        )

        self.assertIn("/opt/homebrew/bin", rendered[-1])
        self.assertTrue(rendered[-1].endswith("git -C /srv/source checkout revision"))

    def test_identity_and_port_are_shared_by_ssh_and_rsync(self) -> None:
        transport = SshDockerTransport(
            "user@executor",
            "/srv/envsolve",
            ssh_identity="/tmp/identity",
            ssh_port=2222,
        )

        self.assertEqual(
            transport.remote_command(["true"])[:8],
            [
                "ssh",
                "-i",
                "/tmp/identity",
                "-o",
                "IdentitiesOnly=yes",
                "-p",
                "2222",
                "-T",
            ],
        )
        self.assertEqual(
            transport._rsync_transport(),
            [
                "-e",
                "ssh -i /tmp/identity -o IdentitiesOnly=yes -p 2222",
            ],
        )

    def test_darwin_remote_skips_bind_mount_chown(self) -> None:
        commands: list[list[str]] = []

        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "Darwin\n", "")

        transport = SshDockerTransport(
            "user@agenthub",
            "/srv/envsolve",
            run_command=run,
        )

        self.assertFalse(transport.requires_bind_mount_chown(timeout=30))
        self.assertFalse(transport.requires_bind_mount_chown(timeout=30))
        self.assertEqual(len(commands), 1)

    def test_rejects_ambiguous_remote_identity_and_path(self) -> None:
        with self.assertRaises(ValueError):
            SshDockerTransport("user@spark;touch /tmp/x", "/srv/envsolve")
        with self.assertRaises(ValueError):
            SshDockerTransport("user@spark", "../envsolve")

    def test_adapter_rewrites_mount_and_syncs_after_exec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory).resolve()
            transport = RecordingTransport()
            adapter = RemoteDockerCommandAdapter(
                transport,  # type: ignore[arg-type]
                sync_timeout=30,
                expose_gpus=True,
            )

            created = adapter(
                [
                    "docker",
                    "create",
                    "--mount",
                    f"type=bind,src={local},dst=/data/project",
                    "image",
                ],
                capture_output=True,
                text=True,
            )
            adapter(
                ["docker", "start", created.stdout.strip()],
                capture_output=True,
                text=True,
            )
            adapter(
                [
                    "docker",
                    "exec",
                    "--workdir",
                    "/data/project",
                    created.stdout.strip(),
                    "true",
                ],
                capture_output=True,
                text=True,
            )

            create_command = transport.remote_commands[0]
            self.assertEqual(create_command[:4], ["docker", "create", "--gpus", "all"])
            self.assertIn(
                "type=bind,src=/srv/envsolve/replay/workspace,dst=/data/project",
                create_command,
            )
            self.assertEqual(transport.uploads, [(local, "/srv/envsolve/replay/workspace")])
            self.assertEqual(
                transport.downloads,
                [("/srv/envsolve/replay/workspace", local, ())],
            )
            ownership_commands = [
                command
                for command in transport.remote_commands
                if command[:3] == ["docker", "exec", "--user"]
            ]
            self.assertEqual(ownership_commands[0][-2:], ["0:0", "/data/project"])
            self.assertEqual(ownership_commands[-1][-2:], ["1000:1000", "/data/project"])

    def test_adapter_uses_configured_remote_docker_executable(self) -> None:
        transport = RecordingTransport()
        transport.docker_executable = "/usr/local/bin/docker"
        adapter = RemoteDockerCommandAdapter(
            transport,  # type: ignore[arg-type]
            sync_timeout=30,
        )

        adapter(
            ["docker", "image", "inspect", "example"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            transport.remote_commands,
            [["/usr/local/bin/docker", "image", "inspect", "example"]],
        )


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_REMOTE_DOCKER_TEST_TARGET"),
    "set ENVSOLVE_REMOTE_DOCKER_TEST_TARGET to run the SSH Docker bridge test",
)
class SshDockerTransportIntegrationTest(unittest.TestCase):
    def _transport(self) -> SshDockerTransport:
        return SshDockerTransport(
            os.environ["ENVSOLVE_REMOTE_DOCKER_TEST_TARGET"],
            os.environ.get(
                "ENVSOLVE_REMOTE_DOCKER_TEST_ROOT",
                "/home/avdpro/work/envsolve-remote-smoke",
            ),
            docker_executable=os.environ.get(
                "ENVSOLVE_REMOTE_DOCKER_TEST_EXECUTABLE", "docker"
            ),
            ssh_identity=os.environ.get("ENVSOLVE_REMOTE_DOCKER_TEST_IDENTITY"),
        )

    def test_remote_shell_persists_and_workspace_round_trips(self) -> None:
        target = os.environ["ENVSOLVE_REMOTE_DOCKER_TEST_TARGET"]
        image = os.environ.get(
            "ENVSOLVE_REMOTE_DOCKER_TEST_IMAGE",
            "ghcr.io/jetbrains-research/envbench-python:latest",
        )
        transport = self._transport()
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            (local / "probe.txt").write_text("before\n", encoding="utf-8")
            remote = transport.workspace_path(local, "integration")
            transport.sync_to_remote(local, remote, timeout=60)
            image_digest = transport.checked_docker(
                ["image", "inspect", "--format", "{{.Id}}", image],
                timeout=60,
            )
            container_id = transport.checked_docker(
                [
                    "create",
                    "--entrypoint",
                    "/bin/bash",
                    "--mount",
                    f"type=bind,src={remote},dst=/data/project",
                    "--workdir",
                    "/data/project",
                    image_digest,
                    "-lc",
                    "while true; do sleep 1000; done",
                ],
                timeout=60,
            )
            transport.checked_docker(["start", container_id], timeout=60)
            shell = SshProcessTreeSafePersistentContainerShell(
                container_id,
                "/data/project",
                command_timeout=30,
                max_output_chars=16000,
                ssh_target=target,
                ssh_executable=shutil.which("ssh") or "ssh",
            )
            try:
                first = shell.execute("export ENVSOLVE_REMOTE_STATE=ready")
                second = shell.execute(
                    "printf '%s\\n' \"$ENVSOLVE_REMOTE_STATE\"; "
                    "printf 'after\\n' > probe.txt"
                )
                self.assertEqual(first.exit_code, 0, first)
                self.assertEqual(second.exit_code, 0, second)
                self.assertEqual(second.output.strip(), "ready")
                transport.sync_from_remote(remote, local, timeout=60)
                self.assertEqual(
                    (local / "probe.txt").read_text(encoding="utf-8"),
                    "after\n",
                )
            finally:
                shell.close()
                transport.run_docker(
                    ["rm", "-f", container_id],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                )

    def test_remote_timeout_removes_container_descendants(self) -> None:
        target = os.environ["ENVSOLVE_REMOTE_DOCKER_TEST_TARGET"]
        image = os.environ.get(
            "ENVSOLVE_REMOTE_DOCKER_TEST_IMAGE",
            "ghcr.io/jetbrains-research/envbench-python:latest",
        )
        transport = self._transport()
        container_id = transport.checked_docker(
            [
                "run",
                "-d",
                "--entrypoint",
                "/bin/bash",
                image,
                "-lc",
                "while true; do sleep 1000; done",
            ],
            timeout=60,
        )
        shell = SshProcessTreeSafePersistentContainerShell(
            container_id,
            "/tmp",
            command_timeout=10,
            max_output_chars=16000,
            ssh_target=target,
            ssh_executable=shutil.which("ssh") or "ssh",
            docker_executable=os.environ.get(
                "ENVSOLVE_REMOTE_DOCKER_TEST_EXECUTABLE", "docker"
            ),
            ssh_identity=os.environ.get("ENVSOLVE_REMOTE_DOCKER_TEST_IDENTITY"),
        )
        try:
            baseline = shell.execute(
                "nohup sleep 60 >/tmp/baseline.log 2>&1 & "
                "echo $! >/tmp/baseline.pid"
            )
            result = shell.execute(
                "setsid /bin/bash -c 'trap \"\" TERM; sleep 60' "
                ">/tmp/new.log 2>&1 & echo $! >/tmp/new.pid; wait",
                timeout_seconds=5,
            )
            self.assertEqual(baseline.exit_code, 0, baseline)
            self.assertTrue(result.timed_out, result)
            self.assertIsNone(result.infrastructure_error, result)
            for name, expected_alive in (("baseline", True), ("new", False)):
                pid = transport.checked_docker(
                    ["exec", container_id, "cat", f"/tmp/{name}.pid"],
                    timeout=30,
                )
                alive = transport.run_docker(
                    [
                        "exec",
                        container_id,
                        "/bin/bash",
                        "-c",
                        "kill -0 \"$1\" 2>/dev/null",
                        "--",
                        pid,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                self.assertEqual(alive.returncode == 0, expected_alive, name)
        finally:
            shell.close()
            transport.run_docker(
                ["rm", "-f", container_id],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )

    def test_rebuildable_environment_is_not_downloaded(self) -> None:
        transport = self._transport()
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            subprocess.run(["git", "init", "-q", local], check=True)
            (local / "probe.txt").write_text("before\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(local), "add", "probe.txt"],
                check=True,
            )
            remote = transport.workspace_path(local, "exclude-integration")
            transport.sync_to_remote(local, remote, timeout=60)
            transport.checked_remote(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"p=Path({remote!r}); "
                        "(p/'.venv').mkdir(exist_ok=True); "
                        "(p/'.venv'/'payload.bin').write_bytes(b'x' * 1000000); "
                        "(p/'probe.txt').write_text('after\\n')"
                    ),
                ],
                timeout=60,
            )

            transport.sync_from_remote(
                remote,
                local,
                timeout=60,
                excludes=untracked_rebuildable_excludes(local),
            )

            self.assertFalse((local / ".venv").exists())
            self.assertEqual(
                (local / "probe.txt").read_text(encoding="utf-8"),
                "after\n",
            )


if __name__ == "__main__":
    unittest.main()
