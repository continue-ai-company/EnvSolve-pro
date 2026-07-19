from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from envsolve_harness.adapters.envbench import EnvBenchEvaluator
from envsolve_harness.adapters.infrastructure import (
    envbench_bootstrap_infrastructure_signature,
)
from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import write_jsonl
from envsolve_harness.core.models import BenchmarkConfig, Case, HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest


REAL_SUBPROCESS_RUN = subprocess.run


class EvaluatorInfrastructureClassifierTest(unittest.TestCase):
    def test_classifies_network_censoring_before_pyright(self) -> None:
        cases = {
            "ReadTimeoutError while downloading": "read-timeout",
            "502 Bad Gateway [IP: 198.18.0.1 80]": "upstream-http-5xx",
            "Connection failed [IP: 198.18.0.1 80]": "apt-connection-failed",
        }
        for logs, expected in cases.items():
            with self.subTest(logs=logs):
                self.assertEqual(
                    envbench_bootstrap_infrastructure_signature(
                        {"exit_code": 2, "container_logs": logs, "pyright": {}}
                    ),
                    expected,
                )

    def test_does_not_classify_an_ordinary_bootstrap_failure(self) -> None:
        self.assertIsNone(
            envbench_bootstrap_infrastructure_signature(
                {
                    "exit_code": 2,
                    "container_logs": "ERROR: No matching distribution found",
                    "pyright": {},
                }
            )
        )

    def test_completed_pyright_is_not_censored_by_historical_log_text(self) -> None:
        self.assertIsNone(
            envbench_bootstrap_infrastructure_signature(
                {
                    "exit_code": 2,
                    "container_logs": "old diagnostic mentioned ReadTimeoutError",
                    "pyright": {"summary": {"errorCount": 1}},
                }
            )
        )

    @mock.patch(
        "envsolve_harness.adapters.envbench.docker_image_provenance",
        return_value={"reference": "test:image"},
    )
    @mock.patch(
        "envsolve_harness.adapters.envbench.git_provenance",
        return_value={"commit": "test"},
    )
    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_adapter_records_network_censoring_as_unknown(
        self,
        run: mock.Mock,
        git: mock.Mock,
        image: mock.Mock,
    ) -> None:
        del git, image

        def run_command(
            command: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess:
            if not command or command[0] != "uv":
                return REAL_SUBPROCESS_RUN(command, *args, **kwargs)
            output_argument = next(
                item for item in command if item.startswith("operation.dirs.json_results=")
            )
            output_dir = Path(output_argument.split("=", 1)[1])
            write_jsonl(
                output_dir / "results.jsonl",
                [
                    {
                        "repo_name": "owner/repo",
                        "commit_sha": "abc",
                        "exit_code": 2,
                        "issues_count": 0,
                        "container_logs": "files.pythonhosted.org: ReadTimeoutError",
                        "pyright": {},
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
                (SuccessCriteria("exit_code", "eq", 0),), (),
            )
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("network-unknown", "test-method")
            artifacts = RunArtifacts.create(config.runs_root, run_spec.run_id, case.case_id)
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            script = workspace / "bootstrap.sh"
            script.write_text("python -m pip install -e .\n", encoding="utf-8")

            result = EnvBenchEvaluator(config, protocol).evaluate(
                case, script, artifacts, run_spec
            )

            self.assertFalse(result.evaluation_completed)
            self.assertFalse(result.official_pass)
            self.assertIsNone(result.evidence[0].passed)
            self.assertEqual(
                result.metadata["termination"],
                {
                    "kind": "infrastructure_unknown",
                    "scope": "evaluator_bootstrap",
                    "signature": "read-timeout",
                },
            )
            self.assertTrue(audit_run(artifacts.root).valid)


if __name__ == "__main__":
    unittest.main()
