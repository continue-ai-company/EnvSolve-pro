from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from envsolve_harness.adapters.envbench import EnvBenchEvaluator
from envsolve_harness.adapters.infrastructure import (
    envbench_bootstrap_infrastructure_signature,
    envbench_evaluation_infrastructure_signature,
)
from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import write_jsonl
from envsolve_harness.core.models import BenchmarkConfig, Case, HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest


REAL_SUBPROCESS_RUN = subprocess.run


class EvaluatorInfrastructureClassifierTest(unittest.TestCase):
    def test_classifies_adapter_recorded_bootstrap_network_censoring(self) -> None:
        self.assertEqual(
            envbench_evaluation_infrastructure_signature(
                {
                    "evaluation_completed": False,
                    "metadata": {
                        "adapter_error": (
                            "EnvBench bootstrap was censored by infrastructure "
                            "failure: read-timeout"
                        ),
                        "termination": {
                            "kind": "infrastructure_unknown",
                            "scope": "evaluator_bootstrap",
                            "signature": "read-timeout",
                        },
                    },
                }
            ),
            "read-timeout",
        )

    def test_rejects_inconsistent_adapter_recorded_network_censoring(self) -> None:
        self.assertIsNone(
            envbench_evaluation_infrastructure_signature(
                {
                    "evaluation_completed": False,
                    "metadata": {
                        "adapter_error": (
                            "EnvBench bootstrap was censored by infrastructure "
                            "failure: connection-error"
                        ),
                        "termination": {
                            "kind": "infrastructure_unknown",
                            "scope": "evaluator_bootstrap",
                            "signature": "read-timeout",
                        },
                    },
                }
            )
        )

    def test_classifies_missing_official_launcher_on_evaluator_host(self) -> None:
        self.assertEqual(
            envbench_evaluation_infrastructure_signature(
                {
                    "evaluation_completed": False,
                    "metadata": {
                        "adapter_error": (
                            "FileNotFoundError: [Errno 2] "
                            "No such file or directory: 'uv'"
                        )
                    },
                }
            ),
            "evaluator-host-missing-uv",
        )

    def test_does_not_classify_an_arbitrary_missing_host_command(self) -> None:
        self.assertIsNone(
            envbench_evaluation_infrastructure_signature(
                {
                    "metadata": {
                        "adapter_error": (
                            "FileNotFoundError: [Errno 2] "
                            "No such file or directory: 'python'"
                        )
                    }
                }
            )
        )

    def test_classifies_network_censoring_before_pyright(self) -> None:
        cases = {
            "ReadTimeoutError while downloading": "read-timeout",
            (
                "WARNING: Connection timed out while downloading.\n"
                "error: incomplete-download"
            ): "connection-timeout",
            (
                "CondaHTTPError: HTTP 000 CONNECTION FAILED for url "
                "<https://repo.anaconda.com/pkgs/main/linux-aarch64/repodata.json>"
            ): "conda-http-connection-failed",
            "502 Bad Gateway [IP: 198.18.0.1 80]": "upstream-http-5xx",
            "Connection failed [IP: 198.18.0.1 80]": "apt-connection-failed",
            (
                "ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE "
                "REQUIREMENTS FILE.\n"
                "    unknown package:\n"
                "        Expected sha256 " + "a" * 64 + "\n"
                "             Got        " + "b" * 64
            ): "package-download-hash-mismatch",
            (
                'File "/opt/conda/lib/python3.13/site-packages/pip/'
                '_internal/index/collector.py", line 231, in parse_links\n'
                "    data = json.loads(page.content)\n"
                "json.decoder.JSONDecodeError: Unterminated string starting at: "
                "line 1 column 335383 (char 335382)"
            ): "package-index-json-truncation",
            (
                "error: RPC failed; curl 56 GnuTLS recv error (-9): "
                "Error decoding the received TLS packet.\n"
                "fetch-pack: unexpected disconnect while reading sideband packet\n"
                "fatal: early EOF\n"
                "fatal: fetch-pack: invalid index-pack output"
            ): "git-rpc-tls-truncation",
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

    def test_classifies_exhausted_package_index_dns_before_pip_terminal_error(
        self,
    ) -> None:
        self.assertEqual(
            envbench_bootstrap_infrastructure_signature(
                {
                    "exit_code": 1,
                    "container_logs": (
                        "Retrying after NewConnectionError: [Errno -2] "
                        "Name or service not known: /simple/wheel/\n"
                        "ERROR: Could not find a version that satisfies the "
                        "requirement wheel\n"
                        "ERROR: No matching distribution found for wheel\n"
                    ),
                    "pyright": {},
                }
            ),
            "package-index-dns-exhaustion",
        )

    def test_does_not_censor_a_named_requirement_with_a_bad_hash(self) -> None:
        self.assertIsNone(
            envbench_bootstrap_infrastructure_signature(
                {
                    "exit_code": 1,
                    "container_logs": (
                        "ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE "
                        "REQUIREMENTS FILE.\n"
                        "    requests==2.0:\n"
                        "        Expected sha256 " + "a" * 64 + "\n"
                        "             Got        " + "b" * 64
                    ),
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

    def test_recovered_network_error_does_not_override_terminal_build_failure(
        self,
    ) -> None:
        self.assertIsNone(
            envbench_bootstrap_infrastructure_signature(
                {
                    "exit_code": 1,
                    "container_logs": (
                        "Retrying after ReadTimeoutError while downloading torch\n"
                        "Successfully installed torch\n"
                        "Preparing metadata finished with status error\n"
                        "error: metadata-generation-failed\n"
                    ),
                    "pyright": {},
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

    @mock.patch(
        "envsolve_harness.adapters.envbench.docker_image_provenance",
        return_value={"reference": "test:image"},
    )
    @mock.patch(
        "envsolve_harness.adapters.envbench.git_provenance",
        return_value={"commit": "test"},
    )
    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_adapter_rejects_zero_issue_result_without_pyright(
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
                        "exit_code": 0,
                        "issues_count": 0,
                        "container_logs": "python: No module named pyright",
                        "pyright": None,
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
                "test",
                "1",
                "envbench",
                "python",
                (
                    SuccessCriteria("exit_code", "eq", 0),
                    SuccessCriteria("issues_count", "eq", 0),
                ),
                (),
            )
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("missing-pyright", "test-method")
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
                    "kind": "measurement_integrity_unknown",
                    "scope": "evaluator_diagnostics",
                    "signature": "missing-pyright-summary",
                },
            )
            self.assertTrue(audit_run(artifacts.root).valid)


if __name__ == "__main__":
    unittest.main()
