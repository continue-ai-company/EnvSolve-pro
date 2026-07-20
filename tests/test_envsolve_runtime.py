from __future__ import annotations

from pathlib import Path
import json
import subprocess
import tempfile
import unittest

from envsolve.constraints import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
    InitialConstraintEvidence,
    NormalizedConstraint,
)
from envsolve.runtime.docker import (
    BaseRuntimeObservation,
    DockerEnvironmentHandle,
    DockerFreshEnvironmentProvider,
)
from envsolve.runtime.import_probe import collect_source_imports
from envsolve.runtime.policy import StructuredModelDeploymentPolicy
from envsolve.runtime.profile import profile_python_repository
from envsolve.runtime.verifier import PythonDeploymentVerifier
from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    ProvisionedEnvironment,
    RecoverablePolicyError,
)
from envsolve.state import EnvironmentState
from envsolve_harness.core.models import (
    BenchmarkConfig,
    HarnessConfig,
    ModelPricing,
    RunSpec,
)
from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.runners.envsolve_p6 import METHOD_PROFILES, EnvSolveP6Runner
from envsolve_harness.runners.registry import create_solver_runner, registered_solver_runners
from envsolve_harness.scripts import TypedReplayCandidateValidator


class Response:
    def __init__(self, content: str) -> None:
        self.content = content


class DiagnosticResponse(Response):
    def __init__(self, content: str) -> None:
        super().__init__(content)
        self.response_metadata = {"finish_reason": "length"}
        self.usage_metadata = {
            "output_tokens": 16384,
            "output_token_details": {"reasoning": 16384},
        }
        self.additional_kwargs = {"reasoning_content": "not persisted"}


class RecordingModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return Response(self.response)


class DiagnosticModel(RecordingModel):
    def invoke(self, messages):
        self.messages = messages
        return DiagnosticResponse(self.response)


class FakeDockerGit:
    def __init__(self, revision: str) -> None:
        self.revision = revision
        self.containers = 0
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if command[:3] == ["git", "clone", "--shared"]:
            Path(command[-1]).mkdir(parents=True)
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["git", "-C"] and "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, self.revision + "\n", "")
        if command[:2] == ["git", "-C"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "sha256:image\n", "")
        if command[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(
                command,
                0,
                'ENVSOLVE_BASE_RUNTIME_V1={"python_implementation": "CPython", '
                '"python_version": "3.13.2"}\n',
                "",
            )
        if command[:2] == ["docker", "create"]:
            self.containers += 1
            return subprocess.CompletedProcess(
                command, 0, f"container-{self.containers}\n", ""
            )
        return subprocess.CompletedProcess(command, 0, "", "")


class EnvSolveRuntimeTest(unittest.TestCase):
    def test_model_policy_emits_strict_complete_candidate(self) -> None:
        model = RecordingModel(
            json.dumps(
                {
                    "script": "python -m pip install -e .",
                    "rationale": "Install declared project dependencies",
                }
            )
        )
        state = EnvironmentState(
            "case",
            case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
        )
        state.verifications.append(
            {
                "verification_id": "verification-1",
                "verifier": "test-verifier",
                "passed": False,
                "details": {"environment_facts": {"python_version": "3.13.5"}},
            }
        )
        policy = StructuredModelDeploymentPolicy(
            model,
            {"schema": "envsolve-python-repository-profile-v1", "files": []},
            candidate_language=TypedReplayCandidateValidator.prompt_contract,
        )

        candidate = policy.propose(state)

        self.assertEqual(candidate.candidate_id, "candidate-0001")
        self.assertEqual(candidate.script, "python -m pip install -e .")
        self.assertIn("complete candidate", model.messages[1][1].lower())
        self.assertIn("one replayable environment mutation per line", model.messages[0][1])
        self.assertIn("verification_feedback", model.messages[1][1])
        self.assertIn("3.13.5", model.messages[1][1])

    def test_model_policy_exposes_active_module_obligations(self) -> None:
        model = RecordingModel(
            json.dumps({"script": "python -m pip install -e .", "rationale": "install"})
        )
        state = EnvironmentState(
            "case",
            case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
        )
        requirement = NormalizedConstraint(
            ConstraintDomain.MODULE,
            "demo.runtime",
            ConstraintPredicate.PRESENT,
            True,
            ConstraintRole.REQUIREMENT,
            ("evidence-requirement",),
        )
        observation = NormalizedConstraint(
            ConstraintDomain.MODULE,
            "demo.runtime",
            ConstraintPredicate.PRESENT,
            False,
            ConstraintRole.FACT,
            ("evidence-observation",),
            scope_id="candidate-1",
        )
        state.constraints[requirement.constraint_id] = requirement.to_state_fields(
            "violated"
        )
        state.constraints[observation.constraint_id] = observation.to_state_fields(
            "violated"
        )
        policy = StructuredModelDeploymentPolicy(model, {"files": []})

        policy.propose(state)

        self.assertIn('"active_module_requirements": ["demo.runtime"]', model.messages[1][1])
        self.assertIn('"operation_plan"', model.messages[1][1])
        self.assertIn('"trigger": "conflict"', model.messages[1][1])
        self.assertIn('"allowed_operation_kinds"', model.messages[1][1])
        self.assertIn('"python_package_install"', model.messages[1][1])

    def test_operation_ablation_hides_plan_and_operation_instructions(self) -> None:
        model = RecordingModel(
            json.dumps({"script": "python -m pip install -e .", "rationale": "install"})
        )
        state = EnvironmentState(
            "case",
            case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
        )
        policy = StructuredModelDeploymentPolicy(
            model,
            {"files": []},
            operation_profile="free-form",
        )

        candidate = policy.propose(state)

        self.assertNotIn('"operation_plan"', model.messages[1][1])
        self.assertNotIn("machine-derived operation_plan", model.messages[0][1])
        self.assertEqual(candidate.metadata["operation_profile"], "free-form")

    def test_operation_ablation_methods_share_the_two_layer_verifier(self) -> None:
        self.assertEqual(
            METHOD_PROFILES["envsolve-operation"],
            ("two-layer", "constraint-driven"),
        )
        self.assertEqual(
            METHOD_PROFILES["envsolve-operation-ablation"],
            ("two-layer", "free-form"),
        )

    def test_model_policy_malformed_output_is_recoverable_and_auditable(self) -> None:
        policy = StructuredModelDeploymentPolicy(
            RecordingModel("not-json"),
            {"files": []},
        )
        state = EnvironmentState(
            "case",
            case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
        )

        with self.assertRaises(RecoverablePolicyError) as raised:
            policy.propose(state)

        self.assertEqual(raised.exception.category, "candidate-policy-output")
        self.assertEqual(raised.exception.details["response_excerpt"], "not-json")
        self.assertEqual(len(raised.exception.details["response_sha256"]), 64)

    def test_model_policy_empty_final_content_records_only_diagnostics(self) -> None:
        policy = StructuredModelDeploymentPolicy(
            DiagnosticModel(""),
            {"files": []},
        )
        state = EnvironmentState(
            "case",
            case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
        )

        with self.assertRaises(RecoverablePolicyError) as raised:
            policy.propose(state)

        details = raised.exception.details
        self.assertEqual(str(raised.exception), "Model candidate has no final content")
        self.assertTrue(details["final_content_empty"])
        self.assertEqual(details["finish_reason"], "length")
        self.assertEqual(details["output_tokens"], 16384)
        self.assertEqual(details["reasoning_tokens"], 16384)
        self.assertTrue(details["reasoning_content_present"])
        self.assertNotIn("not persisted", json.dumps(details))

    def test_repository_profile_is_bounded_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("x" * 100, encoding="utf-8")
            (root / "README.md").write_text("readme", encoding="utf-8")
            (root / "tests").mkdir()

            profile = profile_python_repository(
                root, max_file_chars=20, max_total_chars=25
            )

            self.assertTrue(profile["has_tests"])
            self.assertLessEqual(profile["total_content_chars"], 25)
            self.assertTrue(profile["files"][0]["truncated"])

    def test_provider_uses_unique_clean_checkout_and_container(self) -> None:
        revision = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            fake = FakeDockerGit(revision)
            provider = DockerFreshEnvironmentProvider(
                source_repository=source,
                worktrees_root=root / "worktrees",
                repository="owner/repo",
                revision=revision,
                image="test:image",
                run_command=fake,
            )
            candidate = DeploymentCandidate("candidate-1", "true", "test")

            first = provider.provision(candidate)
            second = provider.provision(candidate)

            self.assertNotEqual(
                first.receipt.environment_id, second.receipt.environment_id
            )
            self.assertNotEqual(first.handle.worktree, second.handle.worktree)
            provider.release(first)
            provider.release(second)
            self.assertFalse(first.handle.worktree.exists())

    def test_provider_observes_base_runtime_without_network_or_repository_mount(self) -> None:
        revision = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            fake = FakeDockerGit(revision)
            provider = DockerFreshEnvironmentProvider(
                source_repository=source,
                worktrees_root=root / "worktrees",
                repository="owner/repo",
                revision=revision,
                image="test:image",
                run_command=fake,
            )

            observation = provider.observe_base_runtime()

            self.assertIsInstance(observation, BaseRuntimeObservation)
            self.assertEqual(observation.python_version, "3.13.2")
            self.assertEqual(observation.image_digest, "sha256:image")
            evidence = observation.constraint_evidence()
            self.assertEqual(evidence.kind, "runtime-observation")
            docker_run = next(command for command in fake.commands if command[:2] == ["docker", "run"])
            self.assertIn("--network", docker_run)
            self.assertIn("none", docker_run)
            self.assertIn("--read-only", docker_run)
            self.assertFalse(any("mount" in item for item in docker_run))

    def test_verifier_records_the_exact_failed_candidate_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def fail(command, **kwargs):
                script = command[-1]
                self.assertIn("ENVSOLVE_ACTION_INDEX=1", script)
                return subprocess.CompletedProcess(
                    command,
                    1,
                    "",
                    "resolution failed\nENVSOLVE_FAILED_ACTION_V1=1:1\n",
                )

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=fail
            ).verify(
                DeploymentCandidate(
                    "candidate-1",
                    "python -m pip install prerequisite\npython -m pip install -e .",
                    "test",
                ),
                environment,
            )

            self.assertFalse(result.passed)
            self.assertEqual(
                result.details["failed_candidate_action"],
                {
                    "action_index": 1,
                    "command": "python -m pip install -e .",
                    "prefix_commands": [
                        "python -m pip install prerequisite",
                        "python -m pip install -e .",
                    ],
                    "exit_code": 1,
                },
            )

    def test_internal_check_failure_remains_a_grounded_hypothesis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def fail(command, **kwargs):
                return subprocess.CompletedProcess(
                    command,
                    1,
                    "",
                    "ModuleNotFoundError: No module named 'missing_dep'",
                )

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=fail
            ).verify(
                DeploymentCandidate("candidate-1", "python -m pip install -e .", "test"),
                environment,
            )

            self.assertFalse(result.passed)
            self.assertEqual(result.channel.value, "internal_execution")
            self.assertFalse(result.counterexamples)
            self.assertEqual(len(result.hypotheses), 1)
            self.assertIn("missing_dep", result.hypotheses[0].value["stderr"])

    def test_internal_verifier_stops_on_network_infrastructure_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def fail(command, **kwargs):
                return subprocess.CompletedProcess(
                    command,
                    2,
                    "",
                    "files.pythonhosted.org: ReadTimeoutError",
                )

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=fail
            ).verify(
                DeploymentCandidate("candidate-1", "python -m pip install -e .", "test"),
                environment,
            )

            self.assertIsNone(result.passed)
            self.assertFalse(result.counterexamples)
            self.assertEqual(
                result.details["infrastructure_signature"], "read-timeout"
            )

    def test_internal_verifier_stops_on_apt_mirror_infrastructure_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def fail(command, **kwargs):
                return subprocess.CompletedProcess(
                    command,
                    100,
                    "",
                    (
                        "Failed to fetch http://mirror.invalid/InRelease "
                        "502 Bad Gateway [IP: 198.18.0.1 80]\n"
                        "Connection failed [IP: 198.18.0.1 80]"
                    ),
                )

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=fail
            ).verify(
                DeploymentCandidate("candidate-1", "apt-get update", "test"),
                environment,
            )

            self.assertIsNone(result.passed)
            self.assertFalse(result.counterexamples)
            self.assertEqual(
                result.details["infrastructure_signature"], "upstream-http-5xx"
            )

    def test_internal_check_connection_error_is_candidate_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def fail(command, **kwargs):
                return subprocess.CompletedProcess(
                    command,
                    2,
                    "elastic_transport.ConnectionError: localhost connection refused",
                    "ENVSOLVE_FAILED_ACTION_V1=internal:2",
                )

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=fail
            ).verify(
                DeploymentCandidate("candidate-1", "python -m pip install -e .", "test"),
                environment,
            )

            self.assertFalse(result.passed)
            self.assertEqual(
                result.summary,
                "Complete candidate failed fixed internal Python checks",
            )
            self.assertNotIn("infrastructure_signature", result.details)

    def test_candidate_connection_error_remains_infrastructure_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def fail(command, **kwargs):
                return subprocess.CompletedProcess(
                    command,
                    1,
                    "",
                    (
                        "requests.ConnectionError: dependency index unavailable\n"
                        "ENVSOLVE_FAILED_ACTION_V1=0:1"
                    ),
                )

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=fail
            ).verify(
                DeploymentCandidate("candidate-1", "python -m pip install -e .", "test"),
                environment,
            )

            self.assertIsNone(result.passed)
            self.assertEqual(
                result.details["infrastructure_signature"],
                "connection-error",
            )
            self.assertEqual(
                result.details["failed_candidate_action"]["action_index"],
                0,
            )

    def test_internal_verifier_stops_on_artifact_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def fail(command, **kwargs):
                return subprocess.CompletedProcess(
                    command,
                    1,
                    "",
                    "ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE",
                )

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=fail
            ).verify(
                DeploymentCandidate("candidate-1", "python -m pip install -e .", "test"),
                environment,
            )

            self.assertIsNone(result.passed)
            self.assertEqual(
                result.details["infrastructure_signature"],
                "artifact-hash-mismatch",
            )

    def test_internal_verifier_treats_unsigned_timeout_as_candidate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def timeout(command, **kwargs):
                raise subprocess.TimeoutExpired(
                    command,
                    timeout=kwargs["timeout"],
                    output="partial stdout",
                    stderr="partial stderr",
                )

            result = PythonDeploymentVerifier(
                command_timeout=1,
                collect_tests=False,
                run_command=timeout,
            ).verify(
                DeploymentCandidate("candidate-1", "python -m pip install -e .", "test"),
                environment,
            )

            self.assertFalse(result.passed)
            self.assertFalse(result.counterexamples)
            self.assertEqual(result.bootstrap.exit_code, 124)
            self.assertTrue(result.details["execution_timeout"])
            self.assertEqual(result.details["command_timeout_seconds"], 1)
            self.assertNotIn("infrastructure_error", result.details)
            self.assertEqual(len(result.hypotheses), 1)

    def test_internal_verifier_keeps_network_signed_timeout_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )

            def timeout(command, **kwargs):
                raise subprocess.TimeoutExpired(
                    command,
                    timeout=kwargs["timeout"],
                    output="retrying dependency download",
                    stderr="Could not resolve host: pypi.org",
                )

            result = PythonDeploymentVerifier(
                command_timeout=1,
                collect_tests=False,
                run_command=timeout,
            ).verify(
                DeploymentCandidate("candidate-1", "python -m pip install -e .", "test"),
                environment,
            )

            self.assertIsNone(result.passed)
            self.assertEqual(
                result.details["infrastructure_signature"], "dns-resolution-failure"
            )
            self.assertEqual(
                result.details["infrastructure_error"],
                "dependency_acquisition_failure",
            )

    def test_model_feedback_truncation_preserves_terminal_error(self) -> None:
        value = "begin" + "x" * 100 + "terminal-error"

        bounded = StructuredModelDeploymentPolicy._bounded_value(value, 60)

        self.assertEqual(len(bounded), 60)
        self.assertTrue(bounded.startswith("begin"))
        self.assertTrue(bounded.endswith("terminal-error"))

    def test_model_projection_is_aggregate_bounded_on_high_cardinality_state(self) -> None:
        state = EnvironmentState(
            "case",
            case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
        )
        for index in range(300):
            subject = f"synthetic_dependency_{index:04d}"
            requirement = NormalizedConstraint(
                ConstraintDomain.MODULE,
                subject,
                ConstraintPredicate.PRESENT,
                True,
                ConstraintRole.REQUIREMENT,
                (f"requirement-evidence-{index}",),
            )
            observation = NormalizedConstraint(
                ConstraintDomain.MODULE,
                subject,
                ConstraintPredicate.PRESENT,
                False,
                ConstraintRole.FACT,
                (f"observation-evidence-{index}",),
                scope_id="candidate-1",
            )
            state.constraints[requirement.constraint_id] = requirement.to_state_fields(
                "violated"
            )
            state.constraints[observation.constraint_id] = observation.to_state_fields(
                "violated"
            )
        for index in range(3):
            candidate_id = f"candidate-{index}"
            state.actions[candidate_id] = {
                "action_id": candidate_id,
                "command": "python -m pip install -e .\n" + "x" * 20_000,
                "status": "failed",
                "exit_code": 1,
                "observation": {
                    "duration_seconds": 1.0,
                    "stdout": "stdout" * 10_000,
                    "stderr": "stderr" * 10_000,
                },
                "state_metadata": {"event_sequence": index},
            }
        state.verifications.append(
            {
                "verification_id": "verification-1",
                "verifier": "synthetic-verifier",
                "passed": False,
                "details": {
                    "candidate_id": "candidate-2",
                    "summary": "synthetic failure",
                    "verifier_details": {
                        "findings": [
                            {"subject": f"finding-{index}", "detail": "x" * 1_000}
                            for index in range(500)
                        ]
                    },
                },
            }
        )
        for index in range(20):
            evidence_id = f"hypothesis-evidence-{index}"
            hypothesis_id = f"hypothesis-{index}"
            state.evidence[evidence_id] = {"value": {"trace": "x" * 20_000}}
            state.hypotheses[hypothesis_id] = {
                "hypothesis_id": hypothesis_id,
                "statement": "synthetic hypothesis",
                "confidence": 0.5,
                "evidence_ids": [evidence_id],
                "status": "active",
            }

        common = {"files": [{"path": "pyproject.toml", "content": "x" * 20_000}]}
        full = StructuredModelDeploymentPolicy(
            RecordingModel("{}"),
            common,
            operation_profile="constraint-driven",
        )._state_projection(state)
        ablation = StructuredModelDeploymentPolicy(
            RecordingModel("{}"),
            common,
            operation_profile="free-form",
        )._state_projection(state)
        minimum_budget = StructuredModelDeploymentPolicy(
            RecordingModel("{}"),
            common,
            max_feedback_chars=4_096,
            operation_profile="constraint-driven",
        )._state_projection(state)

        self.assertLessEqual(len(json.dumps(full, sort_keys=True)), 64_000)
        self.assertLessEqual(len(json.dumps(ablation, sort_keys=True)), 64_000)
        self.assertLessEqual(len(json.dumps(minimum_budget, sort_keys=True)), 4_096)
        self.assertIn("operation_plan", full)
        self.assertNotIn("operation_plan", ablation)
        self.assertEqual(
            {key: value for key, value in full.items() if key != "operation_plan"},
            ablation,
        )
        self.assertNotIn("active_constraints", full)
        self.assertIn("constraint_conflicts", full)

    def test_aggregate_bounding_limits_nested_collections(self) -> None:
        value = {"findings": [{"detail": "x" * 1_000} for _ in range(100)]}

        bounded = StructuredModelDeploymentPolicy._bounded_json_value(value, 2_000)

        self.assertLessEqual(len(json.dumps(bounded, sort_keys=True)), 2_000)
        self.assertTrue(bounded["truncated"])
        self.assertEqual(bounded["original_chars"], len(json.dumps(value, sort_keys=True)))

    def test_import_inventory_is_bounded_to_external_project_obligations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            root.mkdir()
            (base / "outside_dependency.py").write_text("", encoding="utf-8")
            (root / "localpkg").mkdir()
            (root / "localpkg/__init__.py").write_text("", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested/local_settings.py").write_text("", encoding="utf-8")
            (root / "nested/worker.py").write_text(
                "import local_settings\nimport nested_dependency\n",
                encoding="utf-8",
            )
            (root / "docs").mkdir()
            (root / "docs/example.py").write_text(
                "import documentation_dependency\n", encoding="utf-8"
            )
            (root / "app.py").write_text(
                "import missing_dependency\n"
                "import outside_dependency\n"
                "from localpkg import value\n"
                "try:\n"
                "    import optional_dependency\n"
                "except ImportError:\n"
                "    optional_dependency = None\n"
                "try:\n"
                "    import modern_dependency\n"
                "except ImportError:\n"
                "    import legacy_dependency\n"
                "try:\n"
                "    import absent_modern_dependency\n"
                "except ImportError:\n"
                "    import absent_legacy_dependency\n",
                encoding="utf-8",
            )

            inventory = collect_source_imports(root)

            self.assertEqual(
                inventory.modules,
                (
                    "absent_legacy_dependency",
                    "absent_modern_dependency",
                    "documentation_dependency",
                    "legacy_dependency",
                    "missing_dependency",
                    "modern_dependency",
                    "nested_dependency",
                    "optional_dependency",
                    "outside_dependency",
                ),
            )
            self.assertEqual(inventory.excluded_occurrences, 0)
            legacy = next(
                item
                for item in inventory.occurrences
                if item.module == "legacy_dependency"
            )
            self.assertEqual(legacy.fallback_modules, ("modern_dependency",))

    def test_import_probe_turns_only_active_missing_module_into_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            (worktree / "app.py").write_text(
                "import missing_dependency\n"
                "try:\n"
                "    import optional_dependency\n"
                "except ImportError:\n"
                "    optional_dependency = None\n"
                "try:\n"
                "    import modern_dependency\n"
                "except ImportError:\n"
                "    import legacy_dependency\n"
                "try:\n"
                "    import absent_modern_dependency\n"
                "except ImportError:\n"
                "    import absent_legacy_dependency\n",
                encoding="utf-8",
            )
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )
            missing = {
                "status": "missing",
                "kind": "missing",
                "error": "module is absent",
            }
            payload = {
                "facts": {
                    "sys_platform": "linux",
                    "python_major": 3,
                    "platform_name": "Linux",
                },
                "runtime": {
                    "missing_dependency": missing,
                    "optional_dependency": missing,
                    "modern_dependency": {"status": "resolved", "kind": "import"},
                    "legacy_dependency": missing,
                    "absent_modern_dependency": missing,
                    "absent_legacy_dependency": missing,
                },
                "static": {
                    "missing_dependency": missing,
                    "optional_dependency": missing,
                    "modern_dependency": {
                        "status": "resolved",
                        "kind": "physical_file",
                    },
                    "legacy_dependency": missing,
                    "absent_modern_dependency": missing,
                    "absent_legacy_dependency": missing,
                },
            }

            def complete(command, **kwargs):
                stdout = "ENVSOLVE_IMPORT_PROBE_V3=" + json.dumps(payload) + "\n"
                return subprocess.CompletedProcess(command, 0, stdout, "")

            result = PythonDeploymentVerifier(
                collect_tests=False, run_command=complete
            ).verify(
                DeploymentCandidate("candidate-1", "true", "test"),
                environment,
            )

            self.assertFalse(result.passed)
            self.assertEqual(len(result.counterexamples), 10)
            self.assertEqual(len(result.observations), 1)
            self.assertEqual(result.observations[0].value["name"], "modern_dependency")
            self.assertTrue(result.observations[0].value["present"])
            self.assertTrue(
                all(
                    item.kind in {"module-requirement", "module-observation"}
                    for item in result.counterexamples
                )
            )
            dispositions = result.details["finding_dispositions"]
            self.assertEqual(
                sorted(dispositions.values()),
                ["active"] * 5 + ["satisfied"],
            )
            self.assertFalse(result.hypotheses)

    def test_package_probe_closes_initial_version_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )
            requirement = InitialConstraintEvidence(
                "repository-requirement-demo",
                "package-requirement",
                "repository-declaration:pyproject.toml",
                {"name": "Demo_Package", "specifier": ">=2"},
            )
            payload = {
                "facts": {
                    "sys_platform": "linux",
                    "python_major": 3,
                    "platform_name": "Linux",
                },
                "runtime": {},
                "static": {},
                "packages": {
                    "demo-package": {"status": "resolved", "version": "2.5"}
                },
            }

            def complete(command, **kwargs):
                stdout = "ENVSOLVE_IMPORT_PROBE_V3=" + json.dumps(payload) + "\n"
                return subprocess.CompletedProcess(command, 0, stdout, "")

            result = PythonDeploymentVerifier(
                collect_tests=False,
                package_requirements=(requirement,),
                run_command=complete,
            ).verify(DeploymentCandidate("candidate-1", "true", "test"), environment)

            self.assertTrue(result.passed)
            self.assertFalse(result.counterexamples)
            self.assertEqual(
                [item.kind for item in result.observations],
                ["package-observation", "package-observation"],
            )
            self.assertEqual(
                {item.value.get("version") for item in result.observations},
                {None, "2.5"},
            )

    def test_package_probe_distinguishes_missing_and_incompatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "test-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-16T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project/repo"),
            )
            requirement = InitialConstraintEvidence(
                "repository-requirement-demo",
                "package-requirement",
                "repository-declaration:requirements.txt",
                {"name": "demo-package", "specifier": ">=2"},
            )

            def verify(package_observation):
                payload = {
                    "facts": {
                        "sys_platform": "linux",
                        "python_major": 3,
                        "platform_name": "Linux",
                    },
                    "runtime": {},
                    "static": {},
                    "packages": {"demo-package": package_observation},
                }

                def complete(command, **kwargs):
                    stdout = "ENVSOLVE_IMPORT_PROBE_V3=" + json.dumps(payload) + "\n"
                    return subprocess.CompletedProcess(command, 0, stdout, "")

                return PythonDeploymentVerifier(
                    collect_tests=False,
                    package_requirements=(requirement,),
                    run_command=complete,
                ).verify(
                    DeploymentCandidate("candidate-1", "true", "test"), environment
                )

            missing = verify({"status": "missing"})
            incompatible = verify({"status": "resolved", "version": "1.5"})

            self.assertFalse(missing.passed)
            self.assertEqual(len(missing.counterexamples), 2)
            self.assertFalse(missing.counterexamples[1].value["present"])
            self.assertFalse(incompatible.passed)
            self.assertEqual(len(incompatible.observations), 1)
            self.assertTrue(incompatible.observations[0].value["present"])
            self.assertEqual(len(incompatible.counterexamples), 2)
            self.assertEqual(incompatible.counterexamples[0].value["specifier"], ">=2")
            self.assertEqual(incompatible.counterexamples[1].value["version"], "1.5")

    def test_registered_runner_constructs_without_envbench_coupling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = HarnessConfig(
                workspace_root=root,
                runs_root=root / "runs",
                benchmarks={
                    "synthetic": BenchmarkConfig(
                        "synthetic", "synthetic", root, {"image": "test:image"}
                    )
                },
                solver_roots={"envbench-agent": root / "EnvBench"},
                model_pricing={"test/model": ModelPricing("test/model", 1, 2)},
                envsolve_max_candidates=8,
                envsolve_max_environments=4,
                envsolve_max_commands=3,
                model_reasoning_effort="high",
                model_response_format="json_object",
            )
            protocol = ExperimentProtocol(
                "test", "1", "synthetic", "python", (SuccessCriteria("x", "eq", 1),), ()
            )

            runner = create_solver_runner(
                "envsolve",
                config,
                protocol,
                RunSpec("run", "envsolve-full", "test/model"),
            )

            self.assertIn("envsolve", registered_solver_runners())
            self.assertIsInstance(runner, EnvSolveP6Runner)
            self.assertEqual(
                runner.source_cache_root,
                config.runs_root / "_source_cache/envbench-python",
            )
            self.assertEqual(runner.max_candidates, 8)
            self.assertEqual(runner.max_environments, 4)
            self.assertEqual(runner.max_commands, 3)
            self.assertEqual(runner.model_reasoning_effort, "high")
            self.assertEqual(runner.model_response_format, "json_object")

    def test_runner_classifies_repository_download_timeout_as_infrastructure(self) -> None:
        log = (
            "requests.exceptions.ReadTimeout: huggingface.co\n"
            "RuntimeError: Unable to acquire the requested repository revision\n"
        )

        self.assertEqual(
            EnvSolveP6Runner._acquisition_infrastructure_failure(log),
            "repository-acquisition-network",
        )
        self.assertIsNone(
            EnvSolveP6Runner._acquisition_infrastructure_failure(
                "RuntimeError: candidate policy failed"
            )
        )

    def test_audit_checks_model_usage_even_when_envsolve_generation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inputs").mkdir()
            (root / "generation").mkdir()
            case = {
                "case_id": "case",
                "repository": "owner/repo",
                "revision": "abc",
                "language": "python",
                "split": "dev",
                "tags": [],
            }
            solver = {
                "generation_completed": False,
                "method": "envsolve-full",
                "script_path": "scripts/generated.sh",
                "trajectory_path": "generation/episode.jsonl",
                "error": "candidate rejected",
                "metadata": {
                    "audit_requirements": {"online_budget": True},
                    "launcher": {"runner": "envsolve-p6"},
                },
            }
            budget = {
                "limits": {
                    "max_model_requests": 30,
                    "max_total_tokens": 1_000_000,
                    "max_estimated_cost_usd": 5.0,
                },
                "pricing": None,
                "usage": {
                    "requests_started": 0,
                    "responses_completed": 0,
                    "total_tokens": 0,
                },
            }
            solver["metadata"]["online_budget"] = budget
            write_json(root / "inputs/case.json", case)
            write_json(root / "generation/budget_ledger.json", budget)
            write_json(root / "status.json", {"state": "failed"})
            write_json(
                root / "manifest.json",
                {
                    "schema_version": "0.6.0",
                    "protocol": {"benchmark": "envbench"},
                    "run": {"run_id": "run"},
                    "case": case,
                    "host": {},
                    "harness": {},
                    "resource_budget": {
                        "model_max_requests": 30,
                        "model_max_total_tokens": 1_000_000,
                        "model_max_estimated_cost_usd": 5.0,
                    },
                    "solver": solver,
                    "script": None,
                    "evaluator": None,
                    "result": None,
                },
            )

            report = audit_run(root)

            self.assertFalse(report.valid)
            self.assertFalse(report.checks["envsolve_model_usage_present"])

            budget["usage"].update(
                {
                    "requests_started": 1,
                    "responses_completed": 1,
                    "total_tokens": 10,
                }
            )
            solver["metadata"]["online_budget"] = budget
            manifest = read_json(root / "manifest.json")
            manifest["solver"] = solver
            write_json(root / "manifest.json", manifest)
            write_json(root / "generation/budget_ledger.json", budget)

            repaired = audit_run(root)

            self.assertTrue(repaired.valid)
            self.assertTrue(repaired.checks["envsolve_model_usage_present"])


if __name__ == "__main__":
    unittest.main()
