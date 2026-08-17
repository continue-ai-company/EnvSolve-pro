#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from textwrap import dedent
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.adapters.envbench_goal import envbench_python_goal_contract
from envsolve_harness.codex.container_mcp import ContainerMcpServer
from envsolve_harness.compatibility_ledger import CompatibilityLedgerService
from envsolve_harness.execution.v2_container_shell import (
    V2ProcessTreeSafePersistentContainerShell,
)


def _run(arguments: list[str]) -> str:
    completed = subprocess.run(
        arguments,
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _synthetic_contract() -> ExecutableGoalContract:
    return ExecutableGoalContract(
        contract_id="compatibility-ledger-canary-v1",
        description="Require one synthetic Python module.",
        program=dedent(
            r"""
            command python - "$ENVSOLVE_GOAL_REPORT" <<'PY'
            import importlib.util
            import json
            from pathlib import Path
            import sys

            present = importlib.util.find_spec("envsolve_ledger_canary") is not None
            findings = [] if present else [{
                "domain": "module",
                "subject": "envsolve_ledger_canary",
                "predicate": "present",
                "required": True,
                "observed": False,
            }]
            Path(sys.argv[1]).write_text(
                json.dumps({
                    "schema": "envsolve-goal-report-v1",
                    "status": "pass" if present else "fail",
                    "finding_set_complete": True,
                    "findings": findings,
                }),
                encoding="utf-8",
            )
            PY
            """
        ).strip(),
    )


def _shell(server: ContainerMcpServer, call_id: str, command: str) -> dict[str, Any]:
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": "envbench_shell",
                "arguments": {"command": command},
            },
        }
    )
    if not isinstance(response, dict):
        raise RuntimeError("Container bridge returned no response")
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Container bridge failed: {response}")
    payload = result.get("structuredContent")
    if not isinstance(payload, dict):
        raise RuntimeError("Container bridge returned no structured content")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qualify the compatibility ledger in a real Docker container."
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--command-timeout", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace = args.workspace.resolve()
    output = args.output.resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist: {workspace}")
    output.parent.mkdir(parents=True, exist_ok=True)
    trace_path = output.with_suffix(".commands.jsonl")
    trace_path.unlink(missing_ok=True)

    create = [
        "docker",
        "create",
        "--entrypoint",
        "/bin/bash",
        "--workdir",
        "/data/project",
        "--volume",
        f"{workspace}:/data/project",
    ]
    if args.cache is not None:
        cache = args.cache.resolve()
        cache.mkdir(parents=True, exist_ok=True)
        create.extend(["--volume", f"{cache}:/root/.cache"])
    create.extend([args.image, "-lc", "sleep infinity"])

    container_id = _run(create)
    terminal: V2ProcessTreeSafePersistentContainerShell | None = None
    try:
        _run(["docker", "start", container_id])
        terminal = V2ProcessTreeSafePersistentContainerShell(
            container_id,
            "/data/project",
            args.command_timeout,
            16_000,
        )
        server = ContainerMcpServer(terminal, trace_path)
        synthetic = CompatibilityLedgerService(_synthetic_contract(), server)
        before = synthetic.check("synthetic-before")
        mutation = _shell(
            server,
            "synthetic-mutation",
            "mkdir -p /tmp/envsolve-ledger-canary && "
            "printf '# compatibility ledger canary\\n' "
            "> /tmp/envsolve-ledger-canary/envsolve_ledger_canary.py && "
            "export PYTHONPATH=/tmp/envsolve-ledger-canary${PYTHONPATH:+:$PYTHONPATH}",
        )
        after = synthetic.check("synthetic-after")

        real = CompatibilityLedgerService(envbench_python_goal_contract(), server)
        envbench = real.check("envbench-goal")
        result = {
            "schema": "envsolve-compatibility-ledger-canary-result-v1",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "platform": "docker",
            "image": args.image,
            "image_id": _run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", args.image]
            ),
            "workspace": str(workspace),
            "synthetic": {
                "before": before,
                "mutation": {
                    key: mutation.get(key)
                    for key in (
                        "exit_code",
                        "timed_out",
                        "infrastructure_error",
                    )
                },
                "after": after,
                "metadata": synthetic.metadata(),
            },
            "envbench": {
                "observation": envbench,
                "metadata": real.metadata(),
            },
            "qualification": {
                "synthetic_initial_fail": before.get("goal_status") == "fail",
                "synthetic_candidate_ready": after.get("candidate_ready") is True,
                "synthetic_delta_improved": (
                    after.get("delta_from_previous", {}).get("classification")
                    == "improved"
                ),
                "environment_fingerprint_changed": (
                    before.get("environment") != after.get("environment")
                ),
                "real_envbench_observation_complete": (
                    envbench.get("finding_set_complete") is True
                ),
                "no_operation_constraints_added": (
                    before.get("operation_constraints_added") is False
                    and after.get("operation_constraints_added") is False
                    and envbench.get("operation_constraints_added") is False
                ),
                "no_container_checkpoint_stored": (
                    synthetic.metadata().get("stores_container_checkpoint") is False
                    and real.metadata().get("stores_container_checkpoint") is False
                ),
            },
        }
        output.write_text(
            json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(output)
        return 0 if all(result["qualification"].values()) else 1
    finally:
        if terminal is not None:
            terminal.close()
        subprocess.run(
            ["docker", "rm", "--force", container_id],
            capture_output=True,
            check=False,
            text=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
