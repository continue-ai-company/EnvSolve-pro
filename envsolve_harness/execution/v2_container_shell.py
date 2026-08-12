from __future__ import annotations

import subprocess

from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)


class V2ProcessTreeSafePersistentContainerShell(
    ProcessTreeSafePersistentContainerShell
):
    """Remove all processes created by a timed-out V2 tool command."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._baseline_pids: frozenset[int] | None = None

    def _start(self) -> subprocess.Popen[bytes]:
        process = super()._start()
        self._baseline_pids = self._snapshot_container_pids()
        return process

    def _snapshot_container_pids(self) -> frozenset[int] | None:
        completed = subprocess.run(
            [
                self.docker_executable,
                "exec",
                "--user",
                "0:0",
                self.container_id,
                "ps",
                "-eo",
                "pid=",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if completed.returncode != 0:
            return None
        try:
            return frozenset(int(item) for item in completed.stdout.split())
        except ValueError:
            return None

    def _terminate_container_process_tree(self) -> str | None:
        shell_pid = self._container_shell_pid
        baseline = self._baseline_pids
        if shell_pid is None:
            return "container shell PID was not observed before timeout"
        if baseline is None:
            return "container PID baseline was not observed before timeout"

        baseline_words = " ".join(str(pid) for pid in sorted(baseline))
        cleanup_script = r'''
baseline=" $1 "
shell_pid="$2"
cleanup_pid="$$"
cleanup_parent="$PPID"
targets=""
for pid in $(ps -eo pid=); do
    case " $pid " in
        " 1 "|" $cleanup_pid "|" $cleanup_parent ") continue ;;
    esac
    case "$baseline" in
        *" $pid "*) continue ;;
    esac
    targets="$targets $pid"
done
if [ -n "$targets" ]; then
    kill -TERM $targets 2>/dev/null || true
    sleep 1
    kill -KILL $targets 2>/dev/null || true
fi
kill -TERM "$shell_pid" 2>/dev/null || true
sleep 1
kill -KILL "$shell_pid" 2>/dev/null || true
'''.strip()
        try:
            completed = subprocess.run(
                [
                    self.docker_executable,
                    "exec",
                    "--user",
                    "0:0",
                    self.container_id,
                    "/bin/bash",
                    "-c",
                    cleanup_script,
                    "--",
                    baseline_words,
                    str(shell_pid),
                ],
                capture_output=True,
                text=True,
                timeout=7,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"container PID-delta cleanup failed: {type(exc).__name__}: {exc}"
        if completed.returncode != 0:
            return (
                "container PID-delta cleanup failed with "
                f"exit {completed.returncode}: {completed.stderr.strip()}"
            )
        return None
