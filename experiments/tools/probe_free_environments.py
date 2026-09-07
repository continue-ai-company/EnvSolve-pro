"""Exercise the real generic MCP routes without a model or Official evaluator."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

from envsolve_harness.codex.free_environment_mcp import FreeEnvironmentMcpServer, FreeEnvironmentPool
from envsolve_harness.codex.remote_container_mcp import SshProcessTreeSafePersistentContainerShell
from envsolve_harness.execution.remote_docker import SshDockerTransport


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", required=True)
    p.add_argument("--identity")
    p.add_argument("--docker", default="docker")
    p.add_argument("--source-cache", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--remote-root", required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)
    transport = SshDockerTransport(target=args.target, remote_root=args.remote_root,
        ssh_identity=args.identity, docker_executable=args.docker)
    pool = FreeEnvironmentPool(transport=transport, source_cache=args.source_cache,
        revision=args.revision, image=args.image, root=args.remote_root,
        timeout=180, workspace_dirs=("build_output",))
    def shell(identity):
        return SshProcessTreeSafePersistentContainerShell(identity, "/data/project", 180,
            16000, args.target, docker_executable=args.docker, ssh_identity=args.identity)
    checks = []
    construction = pool.create()
    server = FreeEnvironmentMcpServer(shell(construction["container_id"]),
        args.output_root / "construction-commands.jsonl", pool, shell)
    def call(tool, **arguments):
        response = server.handle({"jsonrpc": "2.0", "id": len(checks)+1, "method": "tools/call",
                                  "params": {"name": tool, "arguments": arguments}})
        checks.append({"tool": tool, "arguments": arguments, "response": response})
        (args.output_root / "calls.json").write_text(json.dumps(checks, indent=2))
        assert "error" not in response, response
        result = response["result"]
        assert not result.get("isError"), result
        return result["structuredContent"]
    try:
        r = call("envbench_shell", command="touch /opt/envsolve_probe_dirty .construction-only; export ENVSOLVE_PROBE_DIRTY=yes")
        assert r["exit_code"] == 0
        first = call("envbench_environment", action="create")["environment_id"]
        clean = "test ! -e /opt/envsolve_probe_dirty && test ! -e .construction-only && test -z \"${ENVSOLVE_PROBE_DIRTY-}\" && test ! -d .venv && test -d build_output"
        r = call("envbench_shell", environment_id=first, command=clean)
        assert r["exit_code"] == 0
        r = call("envbench_shell", environment_id=first, command="false")
        assert r["exit_code"] == 1
        program = """python -m venv .venv && . .venv/bin/activate && python - <<'PY'
import pathlib, sysconfig
pathlib.Path(sysconfig.get_paths()['purelib'], 'envsolve_capability_probe.py').write_text('VALUE = 42\\n')
PY
"""
        r = call("envbench_shell", environment_id=first, command=program)
        assert r["exit_code"] == 0
        r = call("envbench_shell", environment_id=first, command="python -c 'import envsolve_capability_probe as p; assert p.VALUE == 42; print(p.VALUE)'")
        assert r["exit_code"] == 0 and "42" in r["output"]
        second = call("envbench_environment", action="create")["environment_id"]
        r = call("envbench_shell", environment_id=second,
                 command=clean + " && python -c 'import importlib.util; assert importlib.util.find_spec(\"envsolve_capability_probe\") is None'")
        assert r["exit_code"] == 0
        r = call("envbench_shell", command="test -f /opt/envsolve_probe_dirty && test -f .construction-only && test \"$ENVSOLVE_PROBE_DIRTY\" = yes && test ! -d .venv")
        assert r["exit_code"] == 0
        for identity in [first, second]:
            call("envbench_environment", action="close", environment_id=identity)
    finally:
        server.serve(io.StringIO(""), io.StringIO())
    assert not pool.environments
    result = {"status": "pass", "host": args.target, "image": args.image,
        "original_revision": args.revision, "model_calls": 0, "official_calls": 0,
        "tool_calls": len(checks), "all_owned_environments_closed": True,
        "claims": ["construction filesystem and shell state not copied", "fresh environments mutually isolated",
                   "caller-supplied complete program executes", "raw failure returned without automatic repair",
                   "persistent per-environment shell", "construction retained while other environments run"],
        "limit": "Direct real MCP handler exercise, not an Agent efficacy result or Codex end-to-end discovery test."}
    (args.output_root / "result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
