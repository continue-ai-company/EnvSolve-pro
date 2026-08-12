from __future__ import annotations

import os
import subprocess
import unittest

from envsolve_harness.execution.v2_container_shell import (
    V2ProcessTreeSafePersistentContainerShell,
)


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_CODEX_MCP_DOCKER_TEST") == "1",
    "set ENVSOLVE_CODEX_MCP_DOCKER_TEST=1 to run the real container bridge test",
)
class V2ContainerShellIntegrationTest(unittest.TestCase):
    def test_timeout_kills_detached_new_process_but_preserves_prior_service(self) -> None:
        image = "ghcr.io/jetbrains-research/envbench-python:latest"
        created = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--entrypoint",
                "/bin/bash",
                image,
                "-lc",
                "while true; do sleep 1000; done",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        container_id = created.stdout.strip()
        shell = V2ProcessTreeSafePersistentContainerShell(
            container_id,
            "/tmp",
            command_timeout=5,
            max_output_chars=16000,
        )
        try:
            baseline = shell.execute(
                "nohup sleep 60 >/tmp/baseline.log 2>&1 & "
                "echo $! >/tmp/baseline.pid"
            )
            timed_out = shell.execute(
                "setsid /bin/bash -c 'trap \"\" TERM; sleep 60' "
                ">/tmp/new.log 2>&1 & echo $! >/tmp/new.pid; wait",
                timeout_seconds=1,
            )

            self.assertEqual(baseline.exit_code, 0, baseline)
            self.assertTrue(timed_out.timed_out, timed_out)
            self.assertIsNone(timed_out.infrastructure_error, timed_out)
            for name, expected_alive in (("baseline", True), ("new", False)):
                checked = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_id,
                        "/bin/bash",
                        "-c",
                        'pid=$(cat "/tmp/$1.pid"); kill -0 "$pid" 2>/dev/null',
                        "--",
                        name,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(checked.returncode == 0, expected_alive, name)
        finally:
            shell.close()
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                text=True,
                check=False,
            )


if __name__ == "__main__":
    unittest.main()
