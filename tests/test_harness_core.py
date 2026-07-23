from __future__ import annotations

from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest import mock

from envsolve_harness.adapters.envbench import EnvBenchEvaluator
from envsolve_harness.adapters.registry import (
    create_benchmark_adapter,
    register_benchmark_adapter,
)
from envsolve_harness.audit import audit_run
from envsolve_harness.budget import BudgetLedger, BudgetLimits, TokenPricing, UsageDelta
from envsolve_harness.core.io import read_json
from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import load_case, read_jsonl, write_json, write_jsonl
from envsolve_harness.core.models import (
    BenchmarkConfig,
    Case,
    HarnessConfig,
    ModelPricing,
    RunSpec,
)
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.execution.batch import (
    BatchProcessController,
    container_ids_for_case,
    mark_case_interrupted,
)
from envsolve_harness.integrity.repository import (
    ALLOWED_GENERATED_PATH_SAMPLE_LIMIT,
    inspect_repository,
)
from envsolve_harness.runners.deterministic import DeterministicScriptRunner
from envsolve_harness.runners.envbench_agent import EnvBenchAgentRunner
from envsolve_harness.runners.envsolve_v0 import EnvSolveV0Runner
from envsolve_harness.runners.registry import (
    create_solver_runner,
    default_method_for,
    registered_solver_runners,
)
from envsolve_harness.runners.repo2run import Repo2RunRunner
from envsolve_harness.scripts.envbench_trajectory import (
    aggregate_token_usage,
    commands_from_trajectory,
    distill_envbench_commands,
)
from envsolve_harness.scripts.repo2run import distill_repo2run_commands
from envsolve_harness.storage.artifacts import RunArtifacts, safe_name
from envsolve_harness.storage.manifest import initialize_manifest
from envsolve_harness.utils.provenance import sha256_tree
from envsolve.v0.verification import V0VerifierResult

REAL_SUBPROCESS_RUN = subprocess.run


def make_config(
    workspace: Path,
    envbench: Path | None = None,
    image: str = "unused:test",
    **limits: object,
) -> HarnessConfig:
    envbench = envbench or workspace / "EnvBench"
    return HarnessConfig(
        workspace_root=workspace,
        runs_root=workspace / "runs",
        benchmarks={
            "envbench": BenchmarkConfig(
                "envbench",
                "envbench",
                envbench,
                {"image": image, "deterministic_script": "baseline.sh"},
            )
        },
        solver_roots={"envbench-agent": envbench, "repo2run": workspace / "Repo2Run"},
        model_pricing={
            model: ModelPricing(model, 1.0, 2.0, 0.1, "https://example.test", "2026-01-01")
            for model in ("test-model", "provider/model")
        },
        **limits,
    )


def make_protocol(benchmark: str = "envbench") -> ExperimentProtocol:
    return ExperimentProtocol(
        protocol_id="test",
        schema_version="1",
        benchmark=benchmark,
        language="python",
        success=(
            SuccessCriteria("exit_code", "eq", 0),
            SuccessCriteria("issues_count", "lte", 0),
        ),
        integrity_rules=(),
    )


class CoreIoTest(unittest.TestCase):
    def test_resource_budget_is_loaded_recorded_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            config_path = workspace / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "paths": {"runs": "runs"},
                        "benchmarks": {
                            "envbench": {
                                "adapter": "envbench",
                                "root": "EnvBench",
                                "settings": {"image": "unused:test"},
                            }
                        },
                        "generation": {
                            "timeout": 101,
                            "model_request_timeout": 11,
                            "model_max_retries": 0,
                            "model_max_output_tokens": 1234,
                            "model_reasoning_effort": "high",
                            "model_response_format": "json_object",
                            "max_iterations": 7,
                            "envsolve_max_candidates": 9,
                            "envsolve_max_environments": 4,
                            "envsolve_max_commands": 3,
                            "bash_timeout": 13,
                        },
                        "evaluation": {
                            "create_container_timeout": 17,
                            "container_timeout": 19,
                            "process_timeout": 23,
                            "git_fetch_timeout": 29,
                            "max_workers": 1,
                        },
                    }
                )
            )
            config = load_harness_config(config_path, workspace)
            self.assertEqual(config.resource_budget()["agent_max_iterations"], 7)
            self.assertEqual(config.model_reasoning_effort, "high")
            self.assertEqual(config.model_response_format, "json_object")
            self.assertEqual(
                config.resource_budget()["model_reasoning_effort"], "high"
            )
            self.assertEqual(
                config.resource_budget()["model_response_format"], "json_object"
            )
            self.assertEqual(config.resource_budget()["envsolve_max_candidates"], 9)
            self.assertEqual(config.resource_budget()["envsolve_max_environments"], 4)
            self.assertEqual(config.resource_budget()["envsolve_max_commands"], 3)
            self.assertEqual(config.resource_budget()["git_fetch_timeout_seconds"], 29)
            with self.assertRaises(ValueError):
                make_config(workspace, model_request_timeout=0)
            with self.assertRaises(ValueError):
                make_config(workspace, model_reasoning_effort="ultra")
            with self.assertRaises(ValueError):
                make_config(workspace, model_response_format="yaml")

    def test_legacy_candidate_budget_remains_the_execution_budget_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            config_path = workspace / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "paths": {"runs": "runs"},
                        "generation": {"envsolve_max_candidates": 7},
                        "evaluation": {
                            "create_container_timeout": 17,
                            "container_timeout": 19,
                            "max_workers": 1,
                        },
                    }
                )
            )

            config = load_harness_config(config_path, workspace)

            self.assertEqual(config.envsolve_max_candidates, 7)
            self.assertEqual(config.envsolve_max_environments, 7)
            self.assertEqual(config.envsolve_max_commands, 7)

    def test_case_round_trip(self) -> None:
        case = Case(
            case_id="owner/repo@abc",
            repository="owner/repo",
            revision="abc",
            tags=("native-build",),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            write_jsonl(path, [case.to_dict()])
            self.assertEqual(load_case(path), case)
            self.assertEqual(read_jsonl(path)[0]["tags"], ["native-build"])

    def test_artifact_layout_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = RunArtifacts.create(Path(directory), "run 1", "owner/repo@abc")
            self.assertTrue(artifacts.evaluation_dir.is_dir())
            self.assertEqual(artifacts.root.name, "owner__repo__abc")
            self.assertEqual(artifacts.root.parent.name, "run__1")
            with self.assertRaises(FileExistsError):
                RunArtifacts.create(Path(directory), "run 1", "owner/repo@abc")
            replacement = RunArtifacts.create(
                Path(directory), "run 1", "owner/repo@abc", overwrite=True
            )
            self.assertTrue(replacement.evaluation_dir.is_dir())

    def test_safe_name_rejects_path_separators(self) -> None:
        self.assertEqual(safe_name("../owner/repo"), "owner__repo")

    def test_source_tree_hash_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            file_path = source / "file.py"
            file_path.write_text("first\n")
            first = sha256_tree(root, [source])
            file_path.write_text("second\n")
            self.assertNotEqual(first, sha256_tree(root, [source]))

    def test_repository_integrity_rejects_mutation_and_injection_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            REAL_SUBPROCESS_RUN(["git", "init", "-q"], cwd=repo, check=True)
            REAL_SUBPROCESS_RUN(
                ["git", "config", "user.email", "test@example.test"], cwd=repo, check=True
            )
            REAL_SUBPROCESS_RUN(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "README.md").write_text("clean\n")
            (repo / ".gitignore").write_text("ignored_*.py\n")
            REAL_SUBPROCESS_RUN(["git", "add", "README.md", ".gitignore"], cwd=repo, check=True)
            REAL_SUBPROCESS_RUN(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            head = REAL_SUBPROCESS_RUN(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            generated = repo / ".venv/lib/python/site-packages"
            generated.mkdir(parents=True)
            (generated / "legitimate.pth").write_text("fixture\n")
            self.assertTrue(inspect_repository(repo, head).valid)

            runtime = repo / "runtime-output"
            runtime.mkdir()
            (runtime / "logfile").write_text("ordinary test output\n")
            runtime_report = inspect_repository(repo, head)
            self.assertTrue(runtime_report.valid)
            self.assertIn("runtime-output/logfile", runtime_report.allowed_generated_paths)

            for index in range(ALLOWED_GENERATED_PATH_SAMPLE_LIMIT + 10):
                (runtime / f"artifact-{index:04d}.txt").write_text("generated\n")
            bounded_report = inspect_repository(repo, head)
            self.assertTrue(bounded_report.valid)
            self.assertEqual(
                bounded_report.allowed_generated_path_count,
                ALLOWED_GENERATED_PATH_SAMPLE_LIMIT + 12,
            )
            self.assertEqual(
                len(bounded_report.allowed_generated_paths),
                ALLOWED_GENERATED_PATH_SAMPLE_LIMIT,
            )
            self.assertTrue(
                bounded_report.to_dict()["allowed_generated_paths_truncated"]
            )

            (repo / "fake_module.py").write_text("# fake\n")
            (repo / "ignored_fake.py").write_text("# hidden fake\n")
            (repo / "pyrightconfig.json").write_text("{}\n")
            (repo / "linked.py").symlink_to(repo / "fake_module.py")
            (repo / "README.md").write_text("changed\n")
            report = inspect_repository(repo, head)
            self.assertFalse(report.valid)
            kinds = {violation.kind for violation in report.violations}
            self.assertIn("tracked_change", kinds)
            self.assertIn("untracked_import_artifact", kinds)
            self.assertIn("untracked_configuration", kinds)
            self.assertIn("untracked_symlink", kinds)
            self.assertIn("ignored_fake.py", report.disallowed_untracked_paths)

    def test_repository_integrity_recognizes_a_real_venv_with_any_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            REAL_SUBPROCESS_RUN(["git", "init", "-q"], cwd=repo, check=True)
            REAL_SUBPROCESS_RUN(
                ["git", "config", "user.email", "test@example.test"], cwd=repo, check=True
            )
            REAL_SUBPROCESS_RUN(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "README.md").write_text("clean\n")
            REAL_SUBPROCESS_RUN(["git", "add", "README.md"], cwd=repo, check=True)
            REAL_SUBPROCESS_RUN(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            head = REAL_SUBPROCESS_RUN(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            environment = repo / "env"
            (environment / "bin").mkdir(parents=True)
            (environment / "bin/activate").write_text("# activation\n")
            (environment / "bin/python").symlink_to("/usr/bin/python3")
            (environment / "pyvenv.cfg").write_text(
                "home = /usr/bin\ninclude-system-site-packages = false\n"
            )
            site_packages = environment / "lib/python3/site-packages"
            site_packages.mkdir(parents=True)
            (site_packages / "installed_dependency.py").write_text("VALUE = 1\n")

            report = inspect_repository(repo, head)
            self.assertTrue(report.valid, report.violations)
            self.assertIn("env/", report.allowed_generated_paths)

            fake = repo / "fake-env"
            fake.mkdir()
            (fake / "pyvenv.cfg").write_text("home = /usr/bin\n")
            (fake / "injected.py").write_text("VALUE = 1\n")
            rejected = inspect_repository(repo, head)
            self.assertFalse(rejected.valid)
            self.assertIn("fake-env/injected.py", rejected.disallowed_untracked_paths)

    def test_repository_integrity_does_not_follow_venv_python_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            REAL_SUBPROCESS_RUN(["git", "init", "-q"], cwd=repo, check=True)
            REAL_SUBPROCESS_RUN(
                ["git", "config", "user.email", "test@example.test"], cwd=repo, check=True
            )
            REAL_SUBPROCESS_RUN(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "README.md").write_text("clean\n")
            REAL_SUBPROCESS_RUN(["git", "add", "README.md"], cwd=repo, check=True)
            REAL_SUBPROCESS_RUN(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            head = REAL_SUBPROCESS_RUN(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            environment = repo / "container-env"
            (environment / "bin").mkdir(parents=True)
            (environment / "bin/activate").write_text("# activation\n")
            python = environment / "bin/python"
            python.symlink_to("/container-only/python3.9")
            (environment / "pyvenv.cfg").write_text(
                "home = /usr/bin\ninclude-system-site-packages = false\n"
            )

            real_is_file = Path.is_file

            def guarded_is_file(path: Path) -> bool:
                if path == python:
                    raise PermissionError("host must not follow the container link")
                return real_is_file(path)

            with mock.patch.object(Path, "is_file", autospec=True, side_effect=guarded_is_file):
                report = inspect_repository(repo, head)

            self.assertTrue(report.valid, report.violations)
            self.assertIn("container-env/", report.allowed_generated_paths)

    def test_protocol_computes_official_pass(self) -> None:
        protocol = make_protocol()
        self.assertTrue(protocol.is_official_pass({"exit_code": 0, "issues_count": 0}))
        self.assertFalse(protocol.is_official_pass({"exit_code": 0, "issues_count": 1}))
        self.assertFalse(protocol.is_official_pass({"exit_code": None, "issues_count": 0}))

    def test_benchmark_registry_accepts_an_adapter_without_core_changes(self) -> None:
        class SyntheticAdapter:
            benchmark_id = "synthetic"

            def evaluate(self, *args: object, **kwargs: object) -> object:
                raise AssertionError("not needed for registry test")

        register_benchmark_adapter(
            "synthetic-test",
            lambda config, protocol: SyntheticAdapter(),
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            config = HarnessConfig(
                workspace_root=workspace,
                runs_root=workspace / "runs",
                benchmarks={
                    "synthetic": BenchmarkConfig(
                        "synthetic", "synthetic-test", workspace / "Synthetic"
                    )
                },
            )
            adapter = create_benchmark_adapter(config, make_protocol("synthetic"))
            self.assertEqual(adapter.benchmark_id, "synthetic")

    def test_solver_failure_is_recorded_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            artifacts = RunArtifacts.create(workspace / "runs", "solver-failure", "owner/repo@abc")
            config = make_config(workspace)
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("solver-failure", "deterministic")
            protocol = make_protocol()
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            result = DeterministicScriptRunner(workspace / "missing.sh").run(
                case, artifacts, run_spec
            )
            self.assertFalse(result.generation_completed)
            self.assertTrue(audit_run(artifacts.root).valid)

    def test_interrupted_run_is_recorded_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            artifacts = RunArtifacts.create(workspace / "runs", "interrupted", "owner/repo@abc")
            config = make_config(workspace)
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("interrupted", "test-method")
            protocol = make_protocol()
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            write_json(artifacts.status, {"state": "generating"})
            marked = mark_case_interrupted(artifacts.root, "test cancellation", -15, ("container",))
            self.assertTrue(marked)
            self.assertEqual(read_json(artifacts.status)["previous_state"], "generating")
            report = audit_run(artifacts.root)
            self.assertTrue(report.valid)
            self.assertTrue(report.checks["interruption_recorded"])

    def test_batch_controller_terminates_process_group(self) -> None:
        process = subprocess.Popen(["sleep", "30"], start_new_session=True, text=True)
        controller = BatchProcessController(termination_grace_seconds=0.5)
        try:
            controller.register("case", process)
            interrupted = controller.cancel("test")
            self.assertEqual(interrupted, ("case",))
            self.assertIsNotNone(process.poll())
            self.assertTrue(controller.was_interrupted("case"))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_container_ownership_uses_case_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "case"
            records = [
                {"Id": "owned", "Mounts": [{"Source": str(root / "evaluation/repos")}]},
                {"Id": "other", "Mounts": [{"Source": str(root.parent / "other")}]},
            ]
            self.assertEqual(container_ids_for_case(records, root), ("owned",))

    def test_repo2run_distillation_keeps_only_replayable_state_changes(self) -> None:
        result = distill_repo2run_commands(
            [
                {"command": "pip install old", "returncode": 0, "dir": "/repo"},
                {"command": "cat pyproject.toml", "returncode": 0, "dir": "/repo"},
                {"command": "change_python_version 3.11", "returncode": 0},
                {"command": "pip install -e .", "returncode": 0, "dir": "/repo"},
                {"command": "python /home/tools/runtest.py", "returncode": 0, "dir": "/repo"},
                {"command": "pip install broken", "returncode": 1, "dir": "/repo"},
            ]
        )
        self.assertNotIn("pip install old", result.script)
        self.assertIn("pyenv global", result.script)
        self.assertIn("pip install -e .", result.script)
        self.assertNotIn("runtest.py", result.script)
        self.assertFalse(result.unsupported_commands)
        self.assertEqual(
            [action.kind for action in result.actions],
            ["runtime_configure", "python_package_install"],
        )

    def test_repo2run_distillation_rejects_arbitrary_successful_mutations(self) -> None:
        result = distill_repo2run_commands(
            [
                {"command": "export PYTHONPATH=.", "returncode": 0, "dir": "/repo"},
                {"command": "ln -s /tmp/fake fake.py", "returncode": 0, "dir": "/repo"},
                {"command": "printf fake > helper.pth", "returncode": 0, "dir": "/repo"},
            ]
        )
        self.assertEqual(len(result.unsupported_commands), 3)
        self.assertFalse(result.actions)

    def test_repo2run_missing_key_is_recorded_without_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": ""}, clear=False
        ):
            workspace = Path(directory)
            repo2run = workspace / "Repo2Run"
            repo2run.mkdir()
            artifacts = RunArtifacts.create(workspace / "runs", "repo2run-no-key", "owner/repo@abc")
            config = make_config(workspace)
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("repo2run-no-key", "repo2run", "test-model")
            protocol = make_protocol()
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            result = Repo2RunRunner(repo2run).run(case, artifacts, run_spec)
            self.assertFalse(result.generation_completed)
            self.assertEqual(result.error, "OPENAI_API_KEY is not set")
            self.assertNotIn("sk-", artifacts.manifest.read_text())
            self.assertTrue(audit_run(artifacts.root).valid)

    def test_repo2run_removes_prior_case_output_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo2run = Path(directory) / "Repo2Run"
            stale = repo2run / "output" / "owner" / "repo"
            stale.mkdir(parents=True)
            (stale / "inner_commands.json").write_text("stale")
            runner = Repo2RunRunner(repo2run)

            output_root, removed = runner._prepare_output_root("owner/repo")

            self.assertTrue(removed)
            self.assertEqual(output_root, stale.resolve())
            self.assertFalse(output_root.exists())

    def test_repo2run_output_isolation_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = Repo2RunRunner(Path(directory) / "Repo2Run")

            with self.assertRaisesRegex(ValueError, "escaped the output root"):
                runner._prepare_output_root("../outside")

    def test_envbench_trajectory_distillation_and_usage(self) -> None:
        records = [
            {
                "node": "agent",
                "messages": [
                    {
                        "message_content": {
                            "usage_metadata": {
                                "input_tokens": 100,
                                "output_tokens": 20,
                                "total_tokens": 120,
                                "input_token_details": {"cache_read": 40},
                                "output_token_details": {"reasoning": 5},
                            }
                        }
                    }
                ],
            },
            {
                "node": "commands_history",
                "commands": [
                    {"command": "ls -la", "exit_code": 0},
                    {"command": "pip install -e .", "exit_code": 0},
                    {"command": "python -c \"import package\"", "exit_code": 0},
                    {"command": "pip install broken", "exit_code": 1},
                ],
            },
        ]
        result = distill_envbench_commands(commands_from_trajectory(records))
        self.assertEqual(result.script, "pip install -e .\n")
        self.assertFalse(result.unknown_commands)
        usage = aggregate_token_usage(records)
        self.assertEqual(usage["requests"], 1)
        self.assertEqual(usage["total_tokens"], 120)
        self.assertEqual(usage["input_token_details"]["cache_read"], 40)

    def test_envbench_distillation_maps_generation_root_and_drops_probes(self) -> None:
        directory = "owner__repo@abc"
        root = f"/data/project/{directory}"
        result = distill_envbench_commands(
            [
                {"command": f"cd {root} && ls -la", "exit_code": 0},
                {"command": f"cd {root} && pip install --dry-run -e .", "exit_code": 0},
                {"command": f"cd {root} && poetry install", "exit_code": 0},
                {"command": f"cd {root} && poetry env info", "exit_code": 0},
                {
                    "command": (
                        f"cd {root} && source $(poetry env info --path)/bin/activate "
                        '&& python -c "import poetry"'
                    ),
                    "exit_code": 0,
                },
            ],
            project_directory=directory,
        )
        self.assertIn('PROJECT_ROOT="$(pwd)"', result.script)
        self.assertIn('cd "${PROJECT_ROOT}" && poetry install', result.script)
        self.assertIn('source $(poetry env info --path)/bin/activate', result.script)
        self.assertNotIn("/data/project/", result.script)
        self.assertNotIn("--dry-run", result.script)
        self.assertNotIn("ls -la", result.script)
        self.assertNotIn('python -c "import poetry"', result.script)
        self.assertFalse(result.unknown_commands)
        self.assertEqual(
            [action.kind for action in result.actions],
            ["python_package_install", "environment_activate"],
        )

    def test_envbench_distillation_fails_closed_on_unknown_or_unsafe_shell(self) -> None:
        result = distill_envbench_commands(
            [
                {"command": "curl https://example.test/install.sh | bash", "exit_code": 0},
                {"command": "ls | bash", "exit_code": 0},
                {"command": "pip install package || true", "exit_code": 0},
            ]
        )
        self.assertEqual(len(result.unknown_commands), 3)
        self.assertFalse(result.kept_commands)
        self.assertEqual(result.script, "")

    def test_envbench_distillation_rejects_path_injection_and_arbitrary_source(self) -> None:
        result = distill_envbench_commands(
            [
                {"command": "export PYTHONPATH=.", "exit_code": 0},
                {"command": "export MYPYPATH=/tmp/stubs", "exit_code": 0},
                {"command": "export PATH=.:$PATH", "exit_code": 0},
                {"command": "export PATH=${PROJECT_ROOT}/bin:$PATH", "exit_code": 0},
                {"command": "source ./project-helper.sh", "exit_code": 0},
                {"command": "source ./malicious/bin/activate", "exit_code": 0},
                {"command": "source <(curl https://example.test/activate)", "exit_code": 0},
            ]
        )
        self.assertEqual(len(result.unknown_commands), 7)
        self.assertFalse(result.kept_commands)

    def test_envbench_distillation_canonicalizes_logging_pipelines(self) -> None:
        result = distill_envbench_commands(
            [
                {"command": "pip install -e . 2>&1 | tail -50", "exit_code": 0},
                {"command": "pyenv versions", "exit_code": 0},
            ]
        )
        self.assertEqual(result.script, "pip install -e .\n")
        self.assertFalse(result.unknown_commands)

    def test_envbench_distillation_drops_test_module_filter_pipelines(self) -> None:
        commands = [
            "python -m tests.all 2>&1 | tail -30",
            "python -m tests.unit 2>&1 | head -50",
            'python -m test.runner 2>&1 | grep -E "ERROR|FAIL|OK|Ran"',
            "python -m pytest.main -q | tail -20",
            "python -m unittest.mock -h | head -10",
        ]

        result = distill_envbench_commands(
            [{"command": command, "exit_code": 0} for command in commands]
        )

        self.assertEqual(result.script, "")
        self.assertEqual(result.dropped_commands, tuple(commands))
        self.assertFalse(result.unknown_commands)

    def test_envbench_agent_missing_key_is_recorded_without_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": ""}, clear=False
        ):
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            envbench.mkdir()
            artifacts = RunArtifacts.create(workspace / "runs", "agent-no-key", "owner/repo@abc")
            config = make_config(workspace, envbench)
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("agent-no-key", "envbench-react-freeagent", "test-model")
            protocol = make_protocol()
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            result = EnvBenchAgentRunner(envbench).run(case, artifacts, run_spec)
            self.assertFalse(result.generation_completed)
            self.assertEqual(result.error, "OPENAI_API_KEY is not set")
            self.assertNotIn("sk-", artifacts.manifest.read_text())
            self.assertTrue(audit_run(artifacts.root).valid)

    @mock.patch("envsolve_harness.runners.envbench_agent.cleanup_case_containers")
    @mock.patch("envsolve_harness.runners.envbench_agent.subprocess.run")
    def test_envbench_agent_classifies_empty_trajectory_as_initialization_failure(
        self, run: mock.Mock, cleanup: mock.Mock
    ) -> None:
        revision = "c" * 40

        def run_command(
            command: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess:
            if len(command) < 2 or "inference/main.py" not in command[1]:
                return REAL_SUBPROCESS_RUN(command, *args, **kwargs)
            logging_dir = Path(
                next(
                    item.split("=", 1)[1]
                    for item in command
                    if item.startswith("logging_dir=")
                )
            )
            logging_dir.mkdir(parents=True)
            (logging_dir / f"owner__repo@{revision}.jsonl").touch()
            return subprocess.CompletedProcess(command, 0, "internal error\n", "")

        run.side_effect = run_command
        cleanup.return_value = ("failed-owned-container",)
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False
        ):
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            envbench.mkdir()
            artifacts = RunArtifacts.create(
                workspace / "runs", "agent-empty", f"owner/repo@{revision}"
            )
            config = make_config(workspace, envbench)
            case = Case(f"owner/repo@{revision}", "owner/repo", revision)
            run_spec = RunSpec(
                "agent-empty", "envbench-react-freeagent", "test-model"
            )
            initialize_manifest(
                artifacts, config, case, run_spec, make_protocol()
            )

            result = EnvBenchAgentRunner(
                envbench, pricing=config.pricing_for("test-model")
            ).run(case, artifacts, run_spec)

            self.assertFalse(result.generation_completed)
            self.assertEqual(
                result.error,
                "EnvBench agent exited with 0; trajectory exists=True; bytes=0",
            )
            self.assertEqual(
                result.metadata["cleaned_container_ids"],
                ["failed-owned-container"],
            )

    def test_envsolve_v0_is_registered_with_explicit_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            envbench.mkdir()
            config = make_config(workspace, envbench, image="envbench:test")
            run_spec = RunSpec("v0-registry", "envsolve-v0", "test-model", seed=7)
            runner = create_solver_runner("envsolve-v0", config, make_protocol(), run_spec)
            self.assertIn("envsolve-v0", registered_solver_runners())
            self.assertEqual(default_method_for("envsolve-v0"), "envsolve-v0")
            self.assertIsInstance(runner, EnvSolveV0Runner)
            self.assertEqual(runner.image, "envbench:test")

    @mock.patch("envsolve_harness.runners.envbench_agent.cleanup_case_containers")
    @mock.patch("envsolve_harness.runners.envbench_agent.subprocess.run")
    def test_envsolve_v0_requires_verified_boundary_before_distillation(
        self, run: mock.Mock, cleanup: mock.Mock
    ) -> None:
        cleanup.return_value = ("v0-owned-container",)
        revision = "b" * 40

        def argument(command: list[str], name: str) -> str:
            return command[command.index(name) + 1]

        def run_command(
            command: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess:
            if command and command[0] == "git":
                if command[1:3] == ["rev-parse", "HEAD"]:
                    return subprocess.CompletedProcess(command, 0, f"{revision}\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")
            if len(command) < 2 or "envsolve/tools/run_v0_inference.py" not in command[1]:
                return REAL_SUBPROCESS_RUN(command, *args, **kwargs)
            self.assertIn("envsolve/tools/run_v0_inference.py", command[1])
            self.assertEqual(argument(command, "--repository"), "owner/repo")
            self.assertEqual(argument(command, "--revision"), revision)
            self.assertEqual(argument(command, "--image"), "envbench:test")
            trajectory_dir = Path(argument(command, "--trajectory-dir"))
            repos_dir = Path(argument(command, "--repos-dir"))
            trajectory_dir.mkdir(parents=True)
            (repos_dir / f"owner__repo@{revision}").mkdir(parents=True)
            verifier = V0VerifierResult(True, 0, "No broken requirements found").to_json()
            write_jsonl(
                trajectory_dir / f"owner__repo@{revision}.jsonl",
                [
                    {
                        "node": "agent",
                        "messages": [{"message_content": {
                            "usage_metadata": {
                                "input_tokens": 10,
                                "output_tokens": 2,
                                "total_tokens": 12,
                            },
                            "tool_calls": [
                                {"name": "execute_bash_command", "id": "bash"}
                            ],
                        }}],
                    },
                    {
                        "node": "agent",
                        "messages": [{"message_content": {"tool_calls": [
                            {"name": "verify_environment", "id": "verify"}
                        ]}}],
                    },
                    {
                        "node": "tools",
                        "messages": [{"message_content": {
                            "tool_call_id": "verify",
                            "content": verifier,
                        }}],
                    },
                    {
                        "node": "commands_history",
                        "commands": [
                            {"command": "python -m pip install -e .", "exit_code": 0}
                        ],
                    },
                ],
            )
            ledger = BudgetLedger(
                Path(argument(command, "--ledger")),
                BudgetLimits(30, 1_000_000, 5.0),
                TokenPricing(
                    "provider/model",
                    1.0,
                    2.0,
                    0.1,
                    "https://example.test",
                    "2026-01-01",
                ),
            )
            ledger.preflight()
            ledger.record_response(UsageDelta(10, 2))
            return subprocess.CompletedProcess(command, 0, "v0 completed\n", "")

        run.side_effect = run_command
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False
        ):
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            envbench.mkdir()
            artifacts = RunArtifacts.create(
                workspace / "runs", "v0-success", f"owner/repo@{revision}"
            )
            config = make_config(workspace, envbench, image="envbench:test")
            case = Case(f"owner/repo@{revision}", "owner/repo", revision)
            run_spec = RunSpec("v0-success", "envsolve-v0", "provider/model", seed=7)
            initialize_manifest(artifacts, config, case, run_spec, make_protocol())
            result = EnvSolveV0Runner(
                envbench,
                image="envbench:test",
                pricing=config.pricing_for("provider/model"),
            ).run(case, artifacts, run_spec)
            self.assertTrue(result.generation_completed)
            self.assertTrue(result.metadata["v0_completion"]["passed"])
            self.assertEqual(result.metadata["v0_completion"]["verifier_calls"], 1)
            self.assertEqual(artifacts.generated_script.read_text(), "python -m pip install -e .\n")
            self.assertNotIn("pip check", artifacts.generated_script.read_text())
            self.assertEqual(result.metadata["token_usage"]["total_tokens"], 12)
            self.assertEqual(
                result.metadata["cleaned_container_ids"], ["v0-owned-container"]
            )
            self.assertEqual(
                result.metadata["distillation"]["policy"],
                "envsolve-v0-typed-replay-ir-v9",
            )
            audit = audit_run(artifacts.root)
            self.assertTrue(audit.checks["repository_integrity"])
            self.assertTrue(audit.checks["online_budget_matches_solver"])
            self.assertTrue(audit.checks["online_budget_limits_match_manifest"])
            self.assertTrue(audit.checks["online_budget_pricing_matches_manifest"])

    @mock.patch("envsolve_harness.runners.envbench_agent.cleanup_case_containers")
    @mock.patch("envsolve_harness.runners.envbench_agent.subprocess.run")
    def test_envbench_agent_hard_timeout_is_structured_and_cleans_up(
        self, run: mock.Mock, cleanup: mock.Mock
    ) -> None:
        def run_command(command: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess:
            if "inference/main.py" in command:
                raise subprocess.TimeoutExpired(command, 401)
            return REAL_SUBPROCESS_RUN(command, *args, **kwargs)

        run.side_effect = run_command
        cleanup.return_value = ("owned-container",)
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False
        ):
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            envbench.mkdir()
            artifacts = RunArtifacts.create(
                workspace / "runs", "agent-timeout", "owner/repo@abc"
            )
            config = make_config(workspace, envbench)
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("agent-timeout", "envbench-react-freeagent", "test-model")
            protocol = make_protocol()
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            result = EnvBenchAgentRunner(
                envbench,
                timeout=101,
                pricing=config.pricing_for("test-model"),
            ).run(
                case, artifacts, run_spec
            )
            self.assertFalse(result.generation_completed)
            self.assertEqual(
                result.metadata["termination"]["scope"],
                "generation_process_hard_deadline",
            )
            self.assertEqual(
                result.metadata["termination"]["cleaned_container_ids"],
                ["owned-container"],
            )
            self.assertTrue(audit_run(artifacts.root).valid)

    @mock.patch("envsolve_harness.runners.envbench_agent.cleanup_case_containers")
    @mock.patch("envsolve_harness.runners.envbench_agent.subprocess.run")
    def test_envbench_agent_success_is_replayable_and_redacts_logs(
        self, run: mock.Mock, cleanup: mock.Mock
    ) -> None:
        cleanup.return_value = ("agent-owned-container",)
        secret = "sk-" + "test-secret-value-1234567890"
        revision = "a" * 40

        def run_command(command: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess:
            if command and command[0] == "git":
                if command[1:3] == ["rev-parse", "HEAD"]:
                    return subprocess.CompletedProcess(command, 0, f"{revision}\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")
            logging_dir = Path(next(item.split("=", 1)[1] for item in command if item.startswith("logging_dir=")))
            logging_dir.mkdir(parents=True)
            repos_dir = Path(next(item.split("=", 1)[1] for item in command if item.startswith("docker.output_dir=")))
            (repos_dir / f"owner__repo@{revision}").mkdir(parents=True)
            write_jsonl(
                logging_dir / f"owner__repo@{revision}.jsonl",
                [
                    {
                        "node": "agent",
                        "messages": [
                            {
                                "message_content": {
                                    "usage_metadata": {
                                        "input_tokens": 10,
                                        "output_tokens": 2,
                                        "total_tokens": 12,
                                    }
                                }
                            }
                        ],
                    },
                    {
                        "node": "commands_history",
                        "commands": [
                            {"command": "cat pyproject.toml", "exit_code": 0},
                            {"command": "python -m pip install -e .", "exit_code": 0},
                        ],
                    },
                ],
            )
            ledger_path = Path(
                next(
                    item.split("=", 1)[1]
                    for item in command
                    if item.startswith("+agent.model.budget_ledger_path=")
                )
            )
            ledger = BudgetLedger(
                ledger_path,
                BudgetLimits(30, 1_000_000, 5.0),
                TokenPricing(
                    "provider/model",
                    1.0,
                    2.0,
                    0.1,
                    "https://example.test",
                    "2026-01-01",
                ),
            )
            ledger.preflight()
            ledger.record_response(UsageDelta(10, 2))
            return subprocess.CompletedProcess(command, 0, f"provider log {secret}\n", "")

        run.side_effect = run_command
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": secret, "OPENAI_BASE_URL": "https://example.test/v1"}, clear=False
        ):
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            envbench.mkdir()
            artifacts = RunArtifacts.create(workspace / "runs", "agent-success", f"owner/repo@{revision}")
            config = make_config(workspace, envbench)
            case = Case(f"owner/repo@{revision}", "owner/repo", revision)
            run_spec = RunSpec("agent-success", "envbench-react-freeagent", "provider/model")
            protocol = make_protocol()
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            result = EnvBenchAgentRunner(
                envbench,
                pricing=config.pricing_for("provider/model"),
            ).run(case, artifacts, run_spec)
            self.assertTrue(result.generation_completed)
            self.assertEqual(artifacts.generated_script.read_text(), "python -m pip install -e .\n")
            self.assertEqual(result.metadata["token_usage"]["total_tokens"], 12)
            self.assertNotIn(secret, artifacts.solver_log.read_text())
            self.assertNotIn(secret, artifacts.manifest.read_text())
            inference_command = next(
                call.args[0]
                for call in run.call_args_list
                if "inference/main.py" in call.args[0]
            )
            self.assertIn("+agent.model.request_timeout=180", inference_command)
            self.assertIn("+agent.model.max_retries=2", inference_command)
            self.assertIn("+agent.model.max_tokens=16384", inference_command)
            self.assertIn(
                "agent.model._target_=envsolve_harness.budget.langchain.create_budgeted_chat_model",
                inference_command,
            )
            self.assertEqual(result.metadata["online_budget"]["usage"]["total_tokens"], 12)
            self.assertEqual(
                result.metadata["cleaned_container_ids"], ["agent-owned-container"]
            )
            integrity_audit = audit_run(artifacts.root)
            self.assertTrue(integrity_audit.checks["repository_integrity"])
            self.assertTrue(integrity_audit.checks["online_budget_matches_solver"])
            self.assertTrue(integrity_audit.checks["online_budget_limits_match_manifest"])
            self.assertTrue(integrity_audit.checks["online_budget_pricing_matches_manifest"])
            manifest = read_json(artifacts.manifest)
            manifest["solver"]["metadata"]["repository_integrity"]["valid"] = False
            write_json(artifacts.manifest, manifest)
            tampered_audit = audit_run(artifacts.root)
            self.assertFalse(tampered_audit.checks["repository_integrity"])
            self.assertIn(
                "Successful solver result lacks a valid repository integrity report",
                tampered_audit.errors,
            )

    @mock.patch("envsolve_harness.adapters.envbench.cleanup_case_containers")
    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_evaluator_hard_timeout_is_structured_and_auditable(
        self, run: mock.Mock, cleanup: mock.Mock
    ) -> None:
        cleanup.return_value = ("owned-container",)
        def run_command(command: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess:
            if command and command[0] == "uv":
                raise subprocess.TimeoutExpired(
                    cmd=command, timeout=23, output="partial output", stderr="partial error"
                )
            return REAL_SUBPROCESS_RUN(command, *args, **kwargs)

        run.side_effect = run_command
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            (envbench / "evaluation/scripts").mkdir(parents=True)
            (envbench / "env_setup_utils").mkdir(parents=True)
            for path in (
                envbench / "evaluation/main.py",
                envbench / "evaluation/scripts/python_build.sh",
                envbench / "env_setup_utils/repo_downloader.py",
            ):
                path.write_text("# fixture\n")
            config = make_config(workspace, envbench, evaluation_process_timeout=23)
            artifacts = RunArtifacts.create(config.runs_root, "eval-timeout", "owner/repo@abc")
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("eval-timeout", "test-method")
            protocol = make_protocol()
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            script = artifacts.root / "script.sh"
            script.write_text("true\n")
            result = EnvBenchEvaluator(config, protocol).evaluate(
                case, script, artifacts, run_spec
            )
            self.assertFalse(result.evaluation_completed)
            self.assertEqual(result.metadata["termination"]["kind"], "budget_exhausted")
            self.assertEqual(result.metadata["termination"]["scope"], "evaluation_process")
            self.assertEqual(
                result.metadata["termination"]["cleaned_container_ids"],
                ["owned-container"],
            )
            self.assertIn("partial output", artifacts.evaluation_log.read_text())
            self.assertTrue(audit_run(artifacts.root).valid)

    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_evaluator_diagnostics_do_not_change_official_score(
        self, run: mock.Mock
    ) -> None:
        def run_command(
            command: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess:
            if not command or command[0] != "uv":
                return REAL_SUBPROCESS_RUN(command, *args, **kwargs)
            output_argument = next(
                item
                for item in command
                if item.startswith("operation.dirs.json_results=")
            )
            output_dir = Path(output_argument.split("=", 1)[1])
            write_jsonl(
                output_dir / "results.jsonl",
                [
                    {
                        "repo_name": "owner/repo",
                        "commit_sha": "abc",
                        "exit_code": 0,
                        "issues_count": 0,
                        "execution_time": 1.5,
                        "pyright": {
                            "version": "1.2.3",
                            "summary": {
                                "errorCount": 1629,
                                "warningCount": 0,
                                "informationCount": 0,
                                "filesAnalyzed": 3,
                            },
                            "generalDiagnostics": [
                                {
                                    "severity": "error",
                                    "rule": "reportPrivateImportUsage",
                                    "message": "private import",
                                },
                            ],
                        },
                    }
                ],
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = run_command
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            (envbench / "evaluation/scripts").mkdir(parents=True)
            (envbench / "env_setup_utils").mkdir(parents=True)
            for path in (
                envbench / "evaluation/main.py",
                envbench / "evaluation/scripts/python_build.sh",
                envbench / "env_setup_utils/repo_downloader.py",
            ):
                path.write_text("# fixture\n")
            config = make_config(workspace, envbench)
            artifacts = RunArtifacts.create(
                workspace / "runs", "diagnostic-run", "owner/repo@abc"
            )
            script = workspace / "bootstrap.sh"
            script.write_text("python -m pip install -e .\n")
            result = EnvBenchEvaluator(config, make_protocol()).evaluate(
                Case("owner/repo@abc", "owner/repo", "abc"),
                script,
                artifacts,
                RunSpec("diagnostic-run", "test-method"),
            )

            self.assertTrue(result.evaluation_completed)
            self.assertTrue(result.official_pass)
            self.assertEqual(
                [item.channel for item in result.evidence],
                ["official", "diagnostic", "diagnostic"],
            )
            self.assertEqual(
                [item.passed for item in result.evidence],
                [True, True, None],
            )
            self.assertNotIn("error_count", result.evidence[0].metrics)
            self.assertEqual(result.raw_metrics["error_count"], 1629)
            report = audit_run(artifacts.root)
            self.assertTrue(report.valid)
            self.assertTrue(report.checks["diagnostic_evidence_schema"])

    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_evaluator_failure_is_recorded_and_auditable(self, run: mock.Mock) -> None:
        def run_command(command: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess:
            if command and command[0] == "uv":
                return subprocess.CompletedProcess(
                    args=command, returncode=7, stdout="partial output", stderr="evaluation failed"
                )
            return REAL_SUBPROCESS_RUN(command, *args, **kwargs)

        run.side_effect = run_command
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            (envbench / "evaluation/scripts").mkdir(parents=True)
            (envbench / "env_setup_utils").mkdir(parents=True)
            (envbench / "evaluation/main.py").write_text("# test evaluator\n")
            (envbench / "evaluation/scripts/python_build.sh").write_text("# test build\n")
            (envbench / "env_setup_utils/repo_downloader.py").write_text("# test downloader\n")
            script = workspace / "bootstrap.sh"
            script.write_text("python -m pip install -e .\n")

            artifacts = RunArtifacts.create(workspace / "runs", "failed-run", "owner/repo@abc")
            config = make_config(workspace, envbench, image="missing:test")
            protocol = make_protocol()
            result = EnvBenchEvaluator(config, protocol).evaluate(
                Case("owner/repo@abc", "owner/repo", "abc"),
                script,
                artifacts,
                RunSpec("failed-run", "test-method"),
            )

            self.assertFalse(result.evaluation_completed)
            self.assertFalse(result.official_pass)
            self.assertEqual(read_json(artifacts.status)["state"], "failed")
            self.assertTrue(artifacts.manifest.is_file())
            self.assertTrue(audit_run(artifacts.root).valid)
            artifacts.bootstrap_script.write_text("tampered\n")
            tampered_report = audit_run(artifacts.root)
            self.assertFalse(tampered_report.valid)
            self.assertIn("Bootstrap script SHA256 does not match manifest", tampered_report.errors)


if __name__ == "__main__":
    unittest.main()
