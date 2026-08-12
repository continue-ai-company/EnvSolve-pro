from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import (
    CommandResult,
    CounterexampleEvidence,
    DeploymentCandidate,
    EnvironmentReceipt,
    ExecutableVerification,
    FeedbackChannel,
    ProvisionedEnvironment,
)
from envsolve_harness.codex.container_mcp import ContainerCommandResult
from envsolve_harness.codex.minimal_b_mcp import (
    CERTIFICATION_SCHEMA,
    CleanReplayService,
    MinimalBExecutableGoalVerifier,
    MinimalBMcpServer,
    _novel_local_distribution_violations,
    script_sha256,
)
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.integrity.repository import inspect_repository


class FakeProvider:
    def __init__(self, image_digest: str = "sha256:image") -> None:
        self.provisioned: list[str] = []
        self.released: list[str] = []
        self.image_digest = image_digest

    def provision(self, candidate: DeploymentCandidate) -> ProvisionedEnvironment:
        environment_id = f"fresh-{len(self.provisioned) + 1}"
        self.provisioned.append(candidate.candidate_id)
        return ProvisionedEnvironment(
            EnvironmentReceipt(
                environment_id,
                "fake-fresh-provider",
                self.image_digest,
                "owner/repo",
                "abc123",
                "2026-08-04T00:00:00+00:00",
            ),
            handle=environment_id,
        )

    def release(self, environment: ProvisionedEnvironment) -> None:
        self.released.append(environment.receipt.environment_id)


class ScriptedVerifier:
    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
    ) -> ExecutableVerification:
        passed = (
            None
            if "UNKNOWN=1" in candidate.script
            else "READY=1" in candidate.script
        )
        return ExecutableVerification(
            verifier="fake-public-goal",
            check_profile="fake-v1",
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=passed,
            bootstrap=CommandResult(0, stdout=f"environment={environment.receipt.environment_id}"),
            summary=(
                "unknown"
                if passed is None
                else "pass"
                if passed
                else "one public-goal finding remains"
            ),
            counterexamples=(
                ()
                if passed is not False
                else (
                    CounterexampleEvidence(
                        "module-requirement",
                        {"name": "demo", "present": True},
                    ),
                )
            ),
            details={
                "goal_report": {
                    "status": (
                        "unknown" if passed is None else "pass" if passed else "fail"
                    )
                }
            },
        )


class FakeExecutor:
    def __init__(self) -> None:
        self.closed = False
        self.calls: list[str] = []

    def execute(
        self,
        command: str,
        timeout_seconds: int | None = None,
    ) -> ContainerCommandResult:
        self.calls.append(command)
        return ContainerCommandResult(command, 0, "ok", 0.01)

    def close(self) -> None:
        self.closed = True


class CleanReplayServiceTest(unittest.TestCase):
    def test_local_distribution_audit_reports_only_new_violations(self) -> None:
        existing = {"distribution": "base-local", "version": "1"}
        injected = {"distribution": "synthetic-shim", "version": "0"}

        self.assertEqual(
            _novel_local_distribution_violations(
                {"violations": [existing], "unowned_import_artifacts": []},
                {
                    "violations": [existing, injected],
                    "unowned_import_artifacts": [],
                },
            ),
            [injected],
        )

    def _service(
        self,
        root: Path,
        provider: FakeProvider | None = None,
    ) -> tuple[CleanReplayService, FakeProvider]:
        selected = provider or FakeProvider()
        return (
            CleanReplayService(
                provider=selected,
                verifier=ScriptedVerifier(),
                repository="owner/repo",
                revision="abc123",
                image_digest="sha256:image",
                goal_contract_sha256="goal-sha256",
                trace_path=root / "replays.jsonl",
                certification_path=root / "certification.json",
                programs_root=root / "programs",
            ),
            selected,
        )

    def test_failure_then_pass_uses_distinct_fresh_environments_and_certifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, provider = self._service(root)

            failed = service.submit("true")
            passed = service.submit("export READY=1")

            self.assertEqual(failed["status"], "fail")
            self.assertFalse(failed["certified"])
            self.assertEqual(passed["status"], "pass")
            self.assertTrue(passed["certified"])
            self.assertNotEqual(
                failed["environment_receipt"]["environment_id"],
                passed["environment_receipt"]["environment_id"],
            )
            self.assertEqual(provider.released, ["fresh-1", "fresh-2"])
            certification = read_json(root / "certification.json")
            self.assertEqual(certification["schema"], CERTIFICATION_SCHEMA)
            self.assertEqual(certification["replay_count"], 2)
            self.assertEqual(
                certification["certified_programs"][0]["program_sha256"],
                script_sha256("export READY=1"),
            )
            self.assertEqual(len(read_jsonl(root / "replays.jsonl")), 2)

    def test_candidate_rejection_does_not_provision_an_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, provider = self._service(root)

            result = service.submit("cp fake.py package/fake.py")

            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["phase"], "candidate-validation")
            self.assertEqual(provider.provisioned, [])
            self.assertEqual(provider.released, [])

    def test_unknown_remains_distinct_and_does_not_certify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, provider = self._service(root)

            result = service.submit("export UNKNOWN=1")

            self.assertEqual(result["status"], "unknown")
            self.assertFalse(result["certified"])
            self.assertEqual(provider.released, ["fresh-1"])
            self.assertEqual(
                read_json(root / "certification.json")["certified_programs"],
                [],
            )

    def test_provider_failure_is_infrastructure_not_task_failure(self) -> None:
        class FailingProvider(FakeProvider):
            def provision(self, candidate: DeploymentCandidate) -> ProvisionedEnvironment:
                raise RuntimeError("docker unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, _ = self._service(root, FailingProvider())

            result = service.submit("true")

            self.assertEqual(result["status"], "infrastructure_error")
            self.assertIn("docker unavailable", result["infrastructure_error"])
            self.assertFalse(result["certified"])

    def test_wrong_replay_image_is_rejected_before_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, provider = self._service(
                root,
                FakeProvider(image_digest="sha256:wrong-image"),
            )

            result = service.submit("export READY=1")

            self.assertEqual(result["status"], "infrastructure_error")
            self.assertIn("invalid receipt", result["infrastructure_error"])
            self.assertEqual(provider.released, ["fresh-1"])
            self.assertFalse(result["certified"])

    def test_mcp_server_keeps_one_service_alive_across_replay_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, _ = self._service(root)
            executor = FakeExecutor()
            server = MinimalBMcpServer(
                executor,
                root / "commands.jsonl",
                service,
            )
            tools = server.handle(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            )
            failed = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "submit_and_replay",
                        "arguments": {"program": "true"},
                    },
                }
            )
            passed = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "submit_and_replay",
                        "arguments": {"program": "export READY=1"},
                    },
                }
            )

            self.assertEqual(
                [tool["name"] for tool in tools["result"]["tools"]],
                ["envbench_shell", "submit_and_replay"],
            )
            self.assertEqual(
                failed["result"]["structuredContent"]["status"], "fail"
            )
            self.assertFalse(failed["result"]["isError"])
            self.assertEqual(
                passed["result"]["structuredContent"]["status"], "pass"
            )
            self.assertEqual(service.sequence, 2)
            self.assertEqual(executor.calls, [])


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_MINIMAL_B_DOCKER_TEST") == "1",
    "set ENVSOLVE_MINIMAL_B_DOCKER_TEST=1 to run clean replay integration",
)
class CleanReplayDockerIntegrationTest(unittest.TestCase):
    def test_real_clean_replay_fails_then_passes_in_distinct_environments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repository,
                check=True,
            )
            (repository / "README.md").write_text("minimal b\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "initial"],
                cwd=repository,
                check=True,
            )
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            pass_report = json.dumps(
                {
                    "schema": "envsolve-goal-report-v1",
                    "status": "pass",
                    "finding_set_complete": True,
                    "findings": [],
                    "details": {},
                },
                separators=(",", ":"),
            )
            fail_report = json.dumps(
                {
                    "schema": "envsolve-goal-report-v1",
                    "status": "fail",
                    "finding_set_complete": True,
                    "findings": [
                        {
                            "finding_id": "ready",
                            "domain": "module",
                            "subject": "demo",
                            "predicate": "present",
                            "required": True,
                            "observed": False,
                            "provenance": {},
                        }
                    ],
                    "details": {},
                },
                separators=(",", ":"),
            )
            goal_program = (
                'if [ "${READY:-}" = "1" ]; then\n'
                f"  printf '%s\\n' {shlex.quote(pass_report)} "
                '> "$ENVSOLVE_GOAL_REPORT"\n'
                "else\n"
                f"  printf '%s\\n' {shlex.quote(fail_report)} "
                '> "$ENVSOLVE_GOAL_REPORT"\n'
                "fi\n"
            )
            contract = ExecutableGoalContract(
                "minimal-b-test-goal",
                "Require READY=1",
                goal_program,
            )
            provider = DockerFreshEnvironmentProvider(
                source_repository=repository,
                worktrees_root=root / "worktrees",
                repository="owner/repo",
                revision=revision,
                image="ghcr.io/jetbrains-research/envbench-python:latest",
                create_timeout=300,
            )
            verifier = MinimalBExecutableGoalVerifier(
                contract,
                observation_timeout=120,
                effect_auditor=lambda worktree: inspect_repository(
                    worktree,
                    revision,
                ),
            )
            service = CleanReplayService(
                provider=provider,
                verifier=verifier,
                repository="owner/repo",
                revision=revision,
                image_digest=subprocess.run(
                    [
                        "docker",
                        "image",
                        "inspect",
                        "--format",
                        "{{.Id}}",
                        "ghcr.io/jetbrains-research/envbench-python:latest",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                goal_contract_sha256=contract.sha256,
                trace_path=root / "replays.jsonl",
                certification_path=root / "certification.json",
                programs_root=root / "programs",
            )

            failed = service.submit("true")
            passed = service.submit("export READY=1")

            self.assertEqual(failed["status"], "fail", failed)
            self.assertEqual(passed["status"], "pass", passed)
            self.assertNotEqual(
                failed["environment_receipt"]["environment_id"],
                passed["environment_receipt"]["environment_id"],
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=repository,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                "",
            )

    def test_real_clean_replay_rejects_generated_local_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repository,
                check=True,
            )
            (repository / "README.md").write_text("minimal b\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "initial"],
                cwd=repository,
                check=True,
            )
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            report = json.dumps(
                {
                    "schema": "envsolve-goal-report-v1",
                    "status": "pass",
                    "finding_set_complete": True,
                    "findings": [],
                    "details": {},
                },
                separators=(",", ":"),
            )
            contract = ExecutableGoalContract(
                "minimal-b-local-distribution-test",
                "Reject a generated local distribution",
                f"printf '%s\\n' {shlex.quote(report)} > \"$ENVSOLVE_GOAL_REPORT\"",
            )
            image = "ghcr.io/jetbrains-research/envbench-python:latest"
            image_digest = subprocess.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", image],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            provider = DockerFreshEnvironmentProvider(
                source_repository=repository,
                worktrees_root=root / "worktrees",
                repository="owner/repo",
                revision=revision,
                image=image,
                create_timeout=300,
            )
            verifier = MinimalBExecutableGoalVerifier(
                contract,
                observation_timeout=120,
                effect_auditor=lambda worktree: inspect_repository(
                    worktree,
                    revision,
                ),
            )
            service = CleanReplayService(
                provider=provider,
                verifier=verifier,
                repository="owner/repo",
                revision=revision,
                image_digest=image_digest,
                goal_contract_sha256=contract.sha256,
                trace_path=root / "replays.jsonl",
                certification_path=root / "certification.json",
                programs_root=root / "programs",
            )
            generated_distribution = """\
set -e
shim_dir=$(mktemp -d)
cat > "$shim_dir/setup.py" <<'PY'
from pathlib import Path
from setuptools import setup

name = "synthetic_dependency" + "." + "py"
(Path(__file__).parent / name).write_text("READY = True\\n")
setup(name="synthetic-dependency", version="0", py_modules=[name[:-3]])
PY
python -m pip install "$shim_dir"
"""

            result = service.submit(generated_distribution)

            self.assertEqual(result["status"], "fail", result)
            self.assertEqual(result["phase"], "clean-replay")
            self.assertIn(
                "inadmissible Python installation artifact",
                result["verification"]["summary"],
            )
            self.assertFalse(result["certified"])

            metadata_removed = generated_distribution + """\
python - <<'PY'
from pathlib import Path
import shutil
import sysconfig

root = Path(sysconfig.get_paths()["purelib"])
for metadata in root.glob("synthetic_dependency-*.dist-info"):
    shutil.rmtree(metadata)
PY
"""
            unowned = service.submit(metadata_removed)

            self.assertEqual(unowned["status"], "fail", unowned)
            findings = json.loads(
                unowned["verification"]["counterexamples"]["json"]
            )[0]["value"]["violations"]
            self.assertTrue(
                any(
                    item.get("audit_kind") == "unowned-import-artifact"
                    and item.get("relative_path") == "synthetic_dependency.py"
                    for item in findings
                ),
                findings,
            )
            self.assertFalse(unowned["certified"])


if __name__ == "__main__":
    unittest.main()
