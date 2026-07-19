from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.context import (
    ContextAcquisitionPolicy,
    PYENV_PRESENCE,
    apt_file_capability_command,
    build_repair_context,
    parse_apt_file_capability,
)
from envsolve.solver import CommandResult, SolverStateSession, StatefulSolverLoop


CASE = {
    "case_id": "synthetic/context-acquisition@v1",
    "repository": "synthetic/context-acquisition",
    "revision": "v1",
    "language": "python",
    "split": "synthetic",
    "tags": [],
}


class QueueExecutor:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = list(results)
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        return self.results.pop(0)


class ContextTestCase(unittest.TestCase):
    def session(self, root: Path) -> SolverStateSession:
        return SolverStateSession(
            root / "state.jsonl",
            root / "snapshot.json",
            CASE,
        )

    @staticmethod
    def evidence(
        session: SolverStateSession,
        kind: str,
        value: object,
        confidence: float = 1.0,
    ) -> str:
        return session.record_evidence(
            kind,
            "synthetic-test",
            value,
            confidence=confidence,
        )


class ContextBuilderTest(ContextTestCase):
    def test_builder_selects_frozen_manager_priority_and_traces_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            pyenv_id = self.evidence(
                session,
                "context-tool-observation",
                {"tool": "pyenv", "present": True, "path": "/usr/bin/pyenv"},
            )
            inventory_id = self.evidence(
                session,
                "context-runtime-inventory",
                {"manager": "pyenv", "versions": ["3.11.9", "3.10.14"]},
            )
            root_id = self.evidence(
                session,
                "context-runtime-root",
                {"manager": "pyenv", "root": "/root/.pyenv"},
            )
            apt_id = self.evidence(
                session,
                "context-system-manager-observation",
                {
                    "manager": "apt-get",
                    "present": True,
                    "path": "/usr/bin/apt-get",
                },
            )
            self.evidence(
                session,
                "context-system-manager-observation",
                {"manager": "brew", "present": True, "path": "/opt/bin/brew"},
            )
            capability_id = self.evidence(
                session,
                "context-capability-package-candidate",
                {
                    "capability": "demo-config",
                    "manager": "apt-get",
                    "packages": ["libdemo-dev"],
                },
            )
            self.evidence(
                session,
                "context-capability-package-candidate",
                {
                    "capability": "demo-config",
                    "manager": "brew",
                    "packages": ["demo"],
                },
            )
            module_id = self.evidence(
                session,
                "context-module-distribution-candidate",
                {
                    "module": "demo_plugin",
                    "distributions": ["demo-plugin >= 1"],
                },
            )

            report = build_repair_context(session.reconstruct())
            context = report.context
            self.assertEqual(context.runtime_manager, "pyenv")
            self.assertEqual(
                context.available_python_versions,
                ("3.10.14", "3.11.9"),
            )
            self.assertEqual(context.system_package_manager, "apt-get")
            self.assertEqual(
                context.capability_packages,
                {"demo-config": ("libdemo-dev",)},
            )
            self.assertEqual(
                context.module_distributions,
                {"demo_plugin": ("demo-plugin>=1",)},
            )
            self.assertEqual(
                set(context.evidence_ids),
                {pyenv_id, root_id, inventory_id, apt_id, capability_id, module_id},
            )

    def test_low_confidence_context_is_provisional_not_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            evidence_id = self.evidence(
                session,
                "context-system-manager-observation",
                {
                    "manager": "apt-get",
                    "present": True,
                    "path": "/usr/bin/apt-get",
                },
                confidence=0.5,
            )

            report = build_repair_context(session.reconstruct())
            self.assertIsNone(report.context.system_package_manager)
            self.assertEqual(report.provisional_evidence_ids, (evidence_id,))

    def test_latest_presence_evidence_supersedes_older_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            old_id = self.evidence(
                session,
                "context-tool-observation",
                {"tool": "pyenv", "present": False, "path": None},
            )
            current_id = self.evidence(
                session,
                "context-tool-observation",
                {"tool": "pyenv", "present": True, "path": "/usr/bin/pyenv"},
            )

            report = build_repair_context(session.reconstruct())

            self.assertEqual(report.context.runtime_manager, "pyenv")
            self.assertIn(current_id, report.context.evidence_ids)
            self.assertNotIn(old_id, report.context.evidence_ids)

    def test_invalid_absent_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            self.evidence(
                session,
                "context-tool-observation",
                {"tool": "pyenv", "present": False, "path": "/usr/bin/pyenv"},
            )

            with self.assertRaisesRegex(ValueError, "cannot include a path"):
                build_repair_context(session.reconstruct())


class ContextAcquisitionPolicyTest(ContextTestCase):
    @staticmethod
    def absent_manager_results(apt_present: bool = True) -> list[CommandResult]:
        apt = (
            CommandResult(0, stdout="present\t/usr/bin/apt-get\n")
            if apt_present
            else CommandResult(0, stdout="absent\n")
        )
        return [
            apt,
            CommandResult(0, stdout="absent\n"),
            CommandResult(0, stdout="absent\n"),
            CommandResult(0, stdout="absent\n"),
            CommandResult(0, stdout="absent\n"),
        ]

    def test_missing_pyenv_is_evidence_without_command_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            executor = QueueExecutor(
                [CommandResult(0, stdout="absent\n"), *self.absent_manager_results()]
            )
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=7,
                goal_id="context-acquisition",
            ).run(ContextAcquisitionPolicy(session))

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.actions_executed, 6)
            state = session.reconstruct()
            self.assertEqual(state.failures, {})
            report = build_repair_context(state)
            self.assertIsNone(report.context.runtime_manager)
            self.assertEqual(report.context.system_package_manager, "apt-get")

    def test_present_pyenv_schedules_and_parses_version_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            executor = QueueExecutor(
                [
                    CommandResult(0, stdout="present\t/usr/local/bin/pyenv\n"),
                    CommandResult(0, stdout="/root/.pyenv\n"),
                    CommandResult(
                        0,
                        stdout="system\n3.10.14\n3.11.9\n3.11.9/envs/demo\n",
                    ),
                    *self.absent_manager_results(),
                ]
            )
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=9,
                goal_id="context-acquisition",
            ).run(ContextAcquisitionPolicy(session))

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.actions_executed, 8)
            context = build_repair_context(session.reconstruct()).context
            self.assertEqual(context.runtime_manager, "pyenv")
            self.assertEqual(context.runtime_root, "/root/.pyenv")
            self.assertEqual(
                context.available_python_versions,
                ("3.10.14", "3.11.9"),
            )

    def test_policy_resume_does_not_repeat_completed_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            setup = QueueExecutor([CommandResult(0, stdout="absent\n")])
            session.execute_action(PYENV_PRESENCE.action(), setup)
            resume = QueueExecutor(self.absent_manager_results())
            result = StatefulSolverLoop(
                session,
                resume,
                max_actions=6,
                goal_id="context-acquisition",
            ).run(ContextAcquisitionPolicy(session))

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.actions_executed, 5)
            self.assertNotIn(PYENV_PRESENCE.command, resume.commands)

    def test_malformed_probe_output_blocks_context_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory))
            executor = QueueExecutor([CommandResult(0, stdout="maybe\n")])
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=2,
                goal_id="context-acquisition",
            ).run(ContextAcquisitionPolicy(session))

            self.assertEqual(result.goal_status, "blocked")
            state = session.reconstruct()
            self.assertNotIn(PYENV_PRESENCE.evidence_id, state.evidence)
            self.assertIn(
                "context-probe-failed",
                {item["category"] for item in state.failures.values()},
            )


class AptFileProviderTest(unittest.TestCase):
    def test_command_is_anchored_and_rejects_shell_injection(self) -> None:
        self.assertEqual(
            apt_file_capability_command("pg_config"),
            "apt-file search --regexp '/pg_config$'",
        )
        with self.assertRaises(ValueError):
            apt_file_capability_command("pg_config; id")

    def test_parser_keeps_only_exact_capability_paths(self) -> None:
        value = parse_apt_file_capability(
            "pg_config",
            "\n".join(
                [
                    "libpq-dev: /usr/bin/pg_config",
                    "docs: /usr/share/doc/pg_config.txt",
                    "postgresql-dev: /opt/bin/pg_config",
                    "malformed output",
                ]
            ),
        )
        self.assertEqual(
            value,
            {
                "capability": "pg_config",
                "manager": "apt-get",
                "packages": ["libpq-dev", "postgresql-dev"],
            },
        )

    def test_parser_fails_when_provider_returns_no_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty list"):
            parse_apt_file_capability("pg_config", "docs: /doc/pg_config.txt")


if __name__ == "__main__":
    unittest.main()
