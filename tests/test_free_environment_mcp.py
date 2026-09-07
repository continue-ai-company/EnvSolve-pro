import io
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from envsolve_harness.codex.container_mcp import ContainerCommandResult
from envsolve_harness.codex.free_environment_mcp import FreeEnvironmentMcpServer, FreeEnvironmentPool
from envsolve_harness.core.models import Case
from envsolve_harness.runners.free_agent_census import FreeAgentCensusRunner


class Transport:
    def __init__(self, translate_ownership=True):
        self.commands = []
        self.translate_ownership = translate_ownership

    def requires_bind_mount_chown(self, **kwargs):
        return self.translate_ownership

    def checked_remote(self, args, **kwargs):
        self.commands.append(args)
        return ""

    checked_docker = checked_remote

    def run_docker(self, args, **kwargs):
        self.commands.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    run_remote = run_docker


class Shell:
    def __init__(self):
        self.commands = []
        self.closed = False

    def execute(self, command, timeout=None):
        self.commands.append(command)
        return ContainerCommandResult(command, 7 if command == "false" else 0, "raw", 0.1)

    def close(self):
        self.closed = True


def call(server, tool, **arguments):
    return server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": tool, "arguments": arguments}})


class FreeEnvironmentTest(unittest.TestCase):
    def pool(self, transport):
        return FreeEnvironmentPool(transport=transport, source_cache="/cache/repo.git",
            revision="original-revision", image="original-image", root="/runs/probe", timeout=60,
            workspace_dirs=("build_output",))

    def test_independent_original_checkouts_and_scoped_cleanup(self):
        t = Transport()
        pool = self.pool(t)
        first, second = pool.create(), pool.create()
        self.assertNotEqual(first["source_path"], second["source_path"])
        self.assertNotEqual(first["container_id"], second["container_id"])
        clones = [c for c in t.commands if "clone" in c]
        self.assertEqual(len(clones), 2)
        self.assertTrue(
            all(
                c[:2] == ["env", "GIT_LFS_SKIP_SMUDGE=1"]
                and "--no-hardlinks" in c
                and "/cache/repo.git" in c
                for c in clones
            )
        )
        creates = [c for c in t.commands if c[0] == "create"]
        self.assertTrue(all("original-image" in c for c in creates))
        self.assertFalse(any("goal" in " ".join(c) or "pyright" in " ".join(c) for c in t.commands))
        with self.assertRaises(KeyError):
            pool.close("unrelated-container")
        pool.close(first["environment_id"])
        self.assertIn(second["environment_id"], pool.environments)
        cleanup = [c for c in t.commands if c[0] == "run"]
        self.assertEqual(len(cleanup), 1)
        self.assertIn("none", cleanup[0])
        self.assertIn(f"type=bind,src={first['source_path']},dst=/data/project", cleanup[0])

    def test_raw_shell_routing_no_automatic_retry_or_verifier(self):
        with TemporaryDirectory() as d:
            shells = []
            def factory(identity):
                shell = Shell()
                shells.append(shell)
                return shell
            construction = Shell()
            server = FreeEnvironmentMcpServer(construction, Path(d)/"commands.jsonl", self.pool(Transport()), factory)
            result = call(server, "envbench_environment", action="create")["result"]["structuredContent"]
            identity = result["environment_id"]
            response = call(server, "envbench_shell", environment_id=identity, command="false")
            self.assertEqual(response["result"]["structuredContent"]["exit_code"], 7)
            self.assertEqual(shells[0].commands, ["false"])
            self.assertEqual(construction.commands, [])
            call(server, "envbench_shell", command="construction-command")
            self.assertEqual(construction.commands, ["construction-command"])
            call(server, "envbench_environment", action="close", environment_id=identity)
            self.assertTrue(shells[0].closed)
            self.assertIn("error", call(server, "envbench_shell", environment_id=identity, command="whoami"))

    def test_docker_desktop_does_not_chmod_host_bind_mount(self):
        transport = Transport(translate_ownership=False)
        pool = self.pool(transport)
        environment = pool.create()
        create = next(command for command in transport.commands if command[0] == "create")
        self.assertNotIn("chmod", create[-1])
        pool.close(environment["environment_id"])
        self.assertFalse(any(command[0] == "run" for command in transport.commands))

    def test_session_eof_closes_all_owned_environments(self):
        with TemporaryDirectory() as d:
            pool = self.pool(Transport())
            pool.create()
            server = FreeEnvironmentMcpServer(Shell(), Path(d)/"commands.jsonl", pool, lambda _: Shell())
            server.serve(io.StringIO(""), io.StringIO())
            self.assertEqual(pool.environments, {})
            self.assertTrue(server.executor.closed)

    def test_tool_discovery_exposes_optional_environment_selection(self):
        with TemporaryDirectory() as d:
            server = FreeEnvironmentMcpServer(Shell(), Path(d)/"commands.jsonl", self.pool(Transport()), lambda _: Shell())
            tools = server.handle({"id": 1, "method": "tools/list"})["result"]["tools"]
            self.assertEqual([t["name"] for t in tools], ["envbench_shell", "envbench_environment"])
            self.assertIn("environment_id", tools[0]["inputSchema"]["properties"])
            self.assertEqual(tools[0]["inputSchema"]["required"], ["command"])

    def test_environment_action_arguments_are_unambiguous(self):
        with TemporaryDirectory() as d:
            server = FreeEnvironmentMcpServer(
                Shell(),
                Path(d) / "commands.jsonl",
                self.pool(Transport()),
                lambda _: Shell(),
            )
            response = call(
                server,
                "envbench_environment",
                action="create",
                environment_id="not-valid-for-create",
            )
            self.assertIn("error", response)


class FreeAgentCensusRunnerTest(unittest.TestCase):
    @staticmethod
    def runner(root: Path) -> FreeAgentCensusRunner:
        return FreeAgentCensusRunner(
            ssh_target="user@agenthub",
            remote_workspace_root="/srv/envsolve",
            docker_executable="docker",
            codex_executable=root / "codex",
            harness_root=root,
            source_cache_root=root / "cache",
            image="envbench:test",
            timeout=120,
            command_timeout=30,
            container_create_timeout=10,
            git_fetch_timeout=20,
        )

    def test_runner_exposes_generic_tools_without_replay_service(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self.runner(root)
            runner._fresh_source_cache = "/srv/cache/repo.git"
            case = Case("fixture", "owner/repo", "a" * 40)
            arguments = runner._mcp_server_args(
                trace_path=root / "trace.jsonl",
                container_id="construction",
                case=case,
                image_digest="sha256:fixture",
            )
            self.assertEqual(
                runner._mcp_tool_names(),
                ("envbench_shell", "envbench_environment"),
            )
            self.assertIn("envsolve_harness.codex.remote_container_mcp", arguments)
            self.assertIn("--fresh-source-cache", arguments)
            self.assertNotIn("--replay-trace", arguments)
            self.assertFalse(any("minimal_b_mcp" in value for value in arguments))

    def test_prompt_leaves_environment_use_voluntary(self):
        with TemporaryDirectory() as directory:
            runner = self.runner(Path(directory))
            prompt = runner._prompt(Case("fixture", "owner/repo", "a" * 40))
            self.assertIn("Whether and when to use additional environments is your choice", prompt)
            self.assertIn("No successful\nreplay certificate is required", prompt)
            self.assertIn("do not run a verifier automatically", prompt)
