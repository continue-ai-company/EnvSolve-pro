from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from experiments.evaluate_only import _existing_retry, _prepare_evaluation_retry
from envsolve_harness.adapters.envbench import EnvBenchEvaluator
from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import write_json, write_jsonl, write_text_atomic
from envsolve_harness.core.models import (
    BenchmarkConfig,
    Case,
    HarnessConfig,
    RunSpec,
    SolverResult,
)
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest, update_manifest


REAL_SUBPROCESS_RUN = subprocess.run


class EvaluationRetryTest(unittest.TestCase):
    @mock.patch(
        "envsolve_harness.adapters.envbench.docker_image_provenance",
        return_value={"reference": "test:image"},
    )
    @mock.patch(
        "envsolve_harness.adapters.envbench.git_provenance",
        return_value={"commit": "test"},
    )
    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_exact_script_retry_is_linked_single_and_auditable(
        self,
        run: mock.Mock,
        git: mock.Mock,
        image: mock.Mock,
    ) -> None:
        del git, image
        calls = 0

        def run_command(
            command: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess:
            nonlocal calls
            if not command or command[0] != "uv":
                return REAL_SUBPROCESS_RUN(command, *args, **kwargs)
            calls += 1
            output_argument = next(
                item for item in command if item.startswith("operation.dirs.json_results=")
            )
            output_dir = Path(output_argument.split("=", 1)[1])
            raw = {
                "repo_name": "owner/repo",
                "commit_sha": "abc",
                "exit_code": 2,
                "issues_count": 0,
                "container_logs": "files.pythonhosted.org: ReadTimeoutError",
                "pyright": {},
            }
            if calls == 2:
                raw.update(
                    {
                        "exit_code": 0,
                        "container_logs": "bootstrap complete",
                        "pyright": {"summary": {"errorCount": 0, "warningCount": 0}},
                    }
                )
            write_jsonl(output_dir / "results.jsonl", [raw])
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = run_command
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            envbench = workspace / "EnvBench"
            (envbench / "evaluation/scripts").mkdir(parents=True)
            (envbench / "env_setup_utils").mkdir(parents=True)
            for relative in (
                "evaluation/main.py",
                "evaluation/scripts/python_build.sh",
                "env_setup_utils/repo_downloader.py",
            ):
                (envbench / relative).write_text("# fixture\n", encoding="utf-8")
            config = HarnessConfig(
                workspace_root=workspace,
                runs_root=workspace / "runs",
                benchmarks={
                    "envbench": BenchmarkConfig(
                        "envbench", "envbench", envbench, {"image": "test:image"}
                    )
                },
            )
            protocol = ExperimentProtocol(
                "test", "1", "envbench", "python",
                (
                    SuccessCriteria("exit_code", "eq", 0),
                    SuccessCriteria("issues_count", "eq", 0),
                ),
                (),
            )
            case = Case("owner/repo@abc", "owner/repo", "abc")
            source_spec = RunSpec("source", "envsolve-runtime-only")
            source = RunArtifacts.create(config.runs_root, source_spec.run_id, case.case_id)
            initialize_manifest(source, config, case, source_spec, protocol)
            write_text_atomic(source.generated_script, "python -m pip install -e .\n")
            solver = SolverResult(
                True,
                source_spec.method,
                script_path=str(source.generated_script.relative_to(source.root)),
            )
            write_json(source.solver_result, solver.to_dict())
            update_manifest(source, solver=solver.to_dict())
            first = EnvBenchEvaluator(config, protocol).evaluate(
                case, source.generated_script, source, source_spec
            )
            self.assertFalse(first.evaluation_completed)
            self.assertTrue(audit_run(source.root).valid)

            retry_spec = RunSpec("retry1", "envsolve-runtime-only-evaluation-retry")
            retry = RunArtifacts.create(config.runs_root, retry_spec.run_id, case.case_id)
            initialize_manifest(retry, config, case, retry_spec, protocol)
            _prepare_evaluation_retry(
                source.root,
                source.bootstrap_script,
                retry,
                case.case_id,
                retry_spec.method,
            )
            second = EnvBenchEvaluator(config, protocol).evaluate(
                case, retry.generated_script, retry, retry_spec
            )

            self.assertTrue(second.official_pass)
            report = audit_run(retry.root)
            self.assertTrue(report.valid, report.errors)
            self.assertTrue(report.checks["evaluation_retry_eligible"])
            self.assertTrue(report.checks["evaluation_retry_exact_script"])
            self.assertEqual(
                _existing_retry(config.runs_root, source_spec.run_id, case.case_id),
                retry_spec.run_id,
            )


if __name__ == "__main__":
    unittest.main()
