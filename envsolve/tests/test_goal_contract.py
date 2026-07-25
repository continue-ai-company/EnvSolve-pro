from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest

from envsolve.runtime import (
    ExecutableGoalContract,
    ExecutableGoalContractVerifier,
)
from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    ProvisionedEnvironment,
)


class ExecutableGoalContractTests(unittest.TestCase):
    def test_round_trip_and_content_hash(self) -> None:
        contract = ExecutableGoalContract(
            contract_id="imports-clean",
            description="No unresolved imports",
            program="python goal.py",
            protected_environment_prefixes=("PYRIGHT_",),
        )

        encoded = contract.to_dict()
        self.assertEqual(
            ExecutableGoalContract.from_dict(encoded),
            contract,
        )
        self.assertEqual(
            encoded["protected_environment_prefixes"],
            ["PYRIGHT_"],
        )
        tampered = {**encoded, "program": "python different.py"}
        with self.assertRaisesRegex(ValueError, "sha256"):
            ExecutableGoalContract.from_dict(tampered)

    def test_rejects_unknown_contract_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            ExecutableGoalContract.from_dict(
                {
                    "contract_id": "goal",
                    "description": "Goal",
                    "program": "true",
                    "private_evaluator_result": True,
                }
            )


class ExecutableGoalContractVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        worktree = Path(self.temp.name)
        self.environment = ProvisionedEnvironment(
            EnvironmentReceipt(
                environment_id="environment-1",
                provider_id="docker",
                image_digest="sha256:image",
                repository="owner/repo",
                revision="abc123",
                created_at="2026-07-24T00:00:00Z",
            ),
            DockerEnvironmentHandle(
                container_id="container-1",
                worktree=worktree,
                container_workdir="/data/project/owner__repo@abc123",
            ),
        )
        self.candidate = DeploymentCandidate(
            "candidate-1",
            "python -m pip install -e .",
            "Install the project",
        )
        self.contract = ExecutableGoalContract(
            contract_id="imports-clean",
            description="No unresolved imports",
            program='printf "{}" > "$ENVSOLVE_GOAL_REPORT"',
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _markers(command: list[str]) -> tuple[str, str, str]:
        shell = command[-1]
        nonce_match = re.search(
            r"ENVSOLVE_GOAL_REPORT_BEGIN_V1=(?P<nonce>[a-f0-9]+)",
            shell,
        )
        if nonce_match is None:
            raise AssertionError("Goal report nonce is missing")
        nonce = nonce_match.group("nonce")
        return (
            f"ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1={nonce}",
            f"ENVSOLVE_GOAL_REPORT_BEGIN_V1={nonce}",
            f"ENVSOLVE_GOAL_REPORT_END_V1={nonce}",
        )

    def _run_with_report(
        self,
        report: dict[str, object],
        *,
        exit_code: int = 0,
    ) -> ExecutableGoalContractVerifier:
        def run_command(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            completed, begin, end = self._markers(command)
            stdout = "\n".join(
                (
                    completed,
                    begin,
                    json.dumps(report, sort_keys=True),
                    end,
                )
            )
            return subprocess.CompletedProcess(command, exit_code, stdout, "")

        return ExecutableGoalContractVerifier(
            self.contract,
            run_command=run_command,
        )

    def test_pass_certifies_candidate(self) -> None:
        verifier = self._run_with_report(
            {
                "schema": "envsolve-goal-report-v1",
                "status": "pass",
                "finding_set_complete": True,
                "findings": [],
                "details": {"checked": 12},
            }
        )

        result = verifier.verify(self.candidate, self.environment)

        self.assertTrue(result.passed)
        self.assertEqual(result.counterexamples, ())
        self.assertEqual(
            result.details["report_details"]["goal_contract"]["contract_id"],
            "imports-clean",
        )
        self.assertEqual(
            result.details["evidence_scope_id"],
            f"goal-contract:imports-clean:{self.contract.sha256}",
        )
        self.assertEqual(
            result.details["report_details"]["goal_report"]["details"]["checked"],
            12,
        )
        self.assertTrue(result.details["finding_set_complete"])

    def test_fail_creates_authoritative_active_constraint(self) -> None:
        verifier = self._run_with_report(
            {
                "schema": "envsolve-goal-report-v1",
                "status": "fail",
                "finding_set_complete": True,
                "findings": [
                    {
                        "finding_id": "missing-tomli",
                        "domain": "module",
                        "subject": "tomli",
                        "predicate": "present",
                        "required": True,
                        "observed": False,
                        "provenance": {"rule": "reportMissingImports"},
                    }
                ],
            }
        )

        result = verifier.verify(self.candidate, self.environment)

        self.assertFalse(result.passed)
        self.assertTrue(result.details["finding_set_complete"])
        self.assertEqual(len(result.counterexamples), 2)
        self.assertEqual(
            {item.kind for item in result.counterexamples},
            {"module-requirement", "module-observation"},
        )
        self.assertEqual(
            {
                item.value["name"]
                for item in result.counterexamples
            },
            {"tomli"},
        )

    def test_malformed_or_failed_goal_is_unknown(self) -> None:
        verifier = self._run_with_report(
            {
                "schema": "wrong-schema",
                "status": "pass",
                "findings": [],
            }
        )

        result = verifier.verify(self.candidate, self.environment)

        self.assertIsNone(result.passed)
        self.assertIn("invalid schema", result.summary)

    def test_candidate_must_return_control(self) -> None:
        def run_command(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                2,
                "",
                "ENVSOLVE_GOAL_CANDIDATE_FAILED_V1=2\n",
            )

        result = ExecutableGoalContractVerifier(
            self.contract,
            run_command=run_command,
        ).verify(self.candidate, self.environment)

        self.assertFalse(result.passed)
        self.assertIn("did not return control", result.summary)

    def test_outer_workspace_mutation_is_rejected_before_goal(self) -> None:
        def run_command(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                253,
                "",
                (
                    "ENVSOLVE_GOAL_OUTER_WORKSPACE_VIOLATION_V1="
                    "/data/project/pyrightconfig.json\n"
                ),
            )

        result = ExecutableGoalContractVerifier(
            self.contract,
            run_command=run_command,
        ).verify(self.candidate, self.environment)

        self.assertFalse(result.passed)
        self.assertIn("outer workspace", result.summary)
        self.assertEqual(
            result.details["outer_workspace_violation"]["path"],
            "/data/project/pyrightconfig.json",
        )

    def test_goal_protected_environment_mutation_is_rejected(self) -> None:
        contract = ExecutableGoalContract(
            contract_id="imports-clean-protected",
            description="No unresolved imports",
            program='printf "{}" > "$ENVSOLVE_GOAL_REPORT"',
            protected_environment_prefixes=("PYRIGHT_",),
        )

        def run_command(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                254,
                "",
                (
                    "ENVSOLVE_GOAL_PROTECTED_ENVIRONMENT_VIOLATION_V1="
                    "PYRIGHT_CONFIG_FILE\n"
                ),
            )

        result = ExecutableGoalContractVerifier(
            contract,
            run_command=run_command,
        ).verify(self.candidate, self.environment)

        self.assertFalse(result.passed)
        self.assertIn("protected environment", result.summary)
        self.assertEqual(
            result.details["protected_environment_violation"]["name"],
            "PYRIGHT_CONFIG_FILE",
        )

    def test_rendered_contract_checks_outer_workspace_before_goal(self) -> None:
        verifier = self._run_with_report(
            {
                "schema": "envsolve-goal-report-v1",
                "status": "pass",
                "finding_set_complete": True,
                "findings": [],
            }
        )
        command, _, _ = verifier._command(
            self.candidate,
            self.environment.handle,
            "abc123",
        )

        self.assertIn("/usr/bin/find", command)
        self.assertIn("/data/project/owner__repo@abc123", command)
        self.assertLess(
            command.index("ENVSOLVE_GOAL_OUTER_WORKSPACE_VIOLATION_V1"),
            command.index("ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1"),
        )

    def test_rendered_shell_contract_executes(self) -> None:
        contract = ExecutableGoalContract(
            contract_id="shell-smoke",
            description="Exercise the rendered shell protocol",
            program=(
                "printf '%s' "
                "'{\"schema\":\"envsolve-goal-report-v1\","
                "\"status\":\"pass\",\"findings\":[]}' "
                '> "$ENVSOLVE_GOAL_REPORT"'
            ),
        )

        def run_command(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["/bin/bash", "-lc", command[-1]],
                cwd=self.temp.name,
                **kwargs,
            )

        result = ExecutableGoalContractVerifier(
            contract,
            run_command=run_command,
        ).verify(
            DeploymentCandidate("candidate-shell", "true", "Smoke test"),
            self.environment,
        )

        self.assertTrue(result.passed, result.bootstrap.stderr)


if __name__ == "__main__":
    unittest.main()
