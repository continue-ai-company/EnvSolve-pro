from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.context import build_repair_context
from envsolve.discovery import (
    AptFileDiscoveryPolicy,
    parse_apt_file_discovery,
    parse_provider_environment,
)
from envsolve.solver import CommandResult, SolverStateSession, StatefulSolverLoop


CASE = {
    "case_id": "synthetic:capability-discovery",
    "repository": "owner/repo",
    "revision": "abc",
    "language": "infrastructure",
    "split": "synthetic",
    "tags": [],
}
ENVIRONMENT_OUTPUT = (
    "path\t/usr/local/bin:/usr/bin:/bin\n"
    "architecture\tarm64\n"
    "os\tubuntu\tjammy\n"
)


class ScriptedExecutor:
    def __init__(self, search_output: str) -> None:
        self.search_output = search_output
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        if command.startswith("printf 'path"):
            return CommandResult(0, ENVIRONMENT_OUTPUT)
        if "command -v -- pg_config" in command:
            return CommandResult(0, "absent\n")
        if "command -v -- apt-file" in command:
            if any("apt-file" in item and "install" in item for item in self.commands):
                return CommandResult(0, "present\t/usr/bin/apt-file\n")
            return CommandResult(0, "absent\n")
        if "sha256sum" in command:
            return CommandResult(0, f"{'a' * 64}  /var/lib/apt/lists/index\n")
        if command.startswith("apt-file search"):
            return CommandResult(0, self.search_output)
        return CommandResult(0)


class AptFileParserTest(unittest.TestCase):
    def test_keeps_only_exact_path_reachable_candidates(self) -> None:
        environment = parse_provider_environment(ENVIRONMENT_OUTPUT)
        discovery = parse_apt_file_discovery(
            "pg_config",
            (
                "libpq-dev: /usr/bin/pg_config\n"
                "server-dev: /usr/lib/postgresql/15/bin/pg_config\n"
                "docs: /usr/share/doc/pg_config\n"
                "malformed output\n"
            ),
            environment,
        )

        self.assertEqual(discovery.packages, ("libpq-dev",))
        self.assertEqual(discovery.candidates[0].path, "/usr/bin/pg_config")
        self.assertEqual(
            {item["reason"] for item in discovery.rejected},
            {"malformed", "not_on_path"},
        )

    def test_environment_parser_rejects_incomplete_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete"):
            parse_provider_environment("path\t/usr/bin\n")


class AptFileDiscoveryPolicyTest(unittest.TestCase):
    @staticmethod
    def session(root: Path) -> SolverStateSession:
        session = SolverStateSession(root / "state.jsonl", root / "snapshot.json", CASE)
        session.record_evidence(
            "context-system-manager-observation",
            "synthetic",
            {"manager": "apt-get", "present": True, "path": "/usr/bin/apt-get"},
            evidence_id="evidence-context-system-manager-apt-get",
        )
        return session

    def test_policy_discovers_candidate_and_resumes_without_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            executor = ScriptedExecutor("libpq-dev: /usr/bin/pg_config\n")
            policy = AptFileDiscoveryPolicy(session, "pg_config")
            first = StatefulSolverLoop(
                session,
                executor,
                max_actions=10,
                goal_id="goal-discovery",
            ).run(policy)
            command_count = len(executor.commands)
            second = StatefulSolverLoop(
                session,
                executor,
                max_actions=10,
                goal_id="goal-discovery",
            ).run(policy)

            self.assertEqual(first.goal_status, "satisfied")
            self.assertEqual(first.actions_executed, 9)
            self.assertEqual(second.actions_executed, 0)
            self.assertEqual(len(executor.commands), command_count)
            context = build_repair_context(session.reconstruct()).context
            self.assertEqual(context.capability_packages, {"pg_config": ("libpq-dev",)})

    def test_policy_blocks_when_only_off_path_candidate_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            executor = ScriptedExecutor(
                "server-dev: /usr/lib/postgresql/15/bin/pg_config\n"
            )
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=10,
                goal_id="goal-discovery",
            ).run(AptFileDiscoveryPolicy(session, "pg_config"))

            self.assertEqual(result.goal_status, "blocked")
            self.assertIn("No PATH-reachable", result.stop_reason)
            self.assertEqual(
                build_repair_context(session.reconstruct()).context.capability_packages,
                {},
            )


if __name__ == "__main__":
    unittest.main()
