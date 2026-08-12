from __future__ import annotations

import subprocess
from pathlib import Path

from envsolve_harness.execution.batch import terminate_process_group


def checked_output(
    command: list[str],
    *,
    timeout: int,
    cwd: Path | None = None,
) -> str:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        terminate_process_group(process)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            command,
            timeout,
            output=stdout,
            stderr=stderr,
        ) from exc
    if process.returncode != 0:
        detail = stderr.strip() or stdout.strip()
        raise RuntimeError(f"{' '.join(command[:3])} failed: {detail}")
    return stdout.strip()
