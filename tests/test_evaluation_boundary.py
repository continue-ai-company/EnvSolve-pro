from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from envsolve_harness.adapters.envbench import (
    EnvBenchEvaluator,
    _run_envbench_process,
)
from envsolve_harness.audit import audit_run
from envsolve_harness.core.models import BenchmarkConfig, Case, HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest


class OfficialEvaluationBoundaryTest(unittest.TestCase):
    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_missing_path_uv_falls_back_to_envbench_venv(
        self,
        run: mock.Mock,
    ) -> None:
        missing = FileNotFoundError(2, "No such file or directory", "uv")
        completed = subprocess.CompletedProcess(["uv"], 0, "ok", "")
        run.side_effect = [missing, completed]
        with tempfile.TemporaryDirectory() as directory:
            envbench = Path(directory)
            local_uv = envbench / ".venv/bin/uv"
            local_uv.parent.mkdir(parents=True)
            local_uv.write_text("fixture\n", encoding="utf-8")
            command = ["uv", "run", "python", "evaluation/main.py"]

            result = _run_envbench_process(
                command,
                cwd=envbench,
                timeout=10,
                env={},
            )

        self.assertIs(result, completed)
        self.assertEqual(command[0], str(local_uv))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][0], "uv")
        self.assertEqual(run.call_args_list[1].args[0][0], str(local_uv))

    @mock.patch(
        "envsolve_harness.adapters.envbench.docker_image_provenance",
        return_value={"reference": "test:image"},
    )
    @mock.patch(
        "envsolve_harness.adapters.envbench.git_provenance",
        return_value={"commit": "test"},
    )
    @mock.patch("envsolve_harness.adapters.envbench.subprocess.run")
    def test_each_run_can_attempt_official_evaluation_only_once(
        self,
        run: mock.Mock,
        git: mock.Mock,
        image: mock.Mock,
    ) -> None:
        run.return_value = subprocess.CompletedProcess(
            ["uv"], 7, "", "evaluation failed"
        )
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
                        "envbench",
                        "envbench",
                        envbench,
                        {"image": "test:image"},
                    )
                },
            )
            protocol = ExperimentProtocol(
                "test-protocol",
                "1",
                "envbench",
                "python",
                (SuccessCriteria("exit_code", "eq", 0),),
                (),
            )
            case = Case("owner/repo@abc", "owner/repo", "abc")
            run_spec = RunSpec("one-shot", "test-method")
            artifacts = RunArtifacts.create(
                config.runs_root, run_spec.run_id, case.case_id
            )
            initialize_manifest(artifacts, config, case, run_spec, protocol)
            script = workspace / "bootstrap.sh"
            script.write_text("true\n", encoding="utf-8")
            evaluator = EnvBenchEvaluator(config, protocol)

            first = evaluator.evaluate(case, script, artifacts, run_spec)

            self.assertFalse(first.evaluation_completed)
            self.assertTrue(artifacts.evaluation_claim.is_file())
            self.assertTrue(audit_run(artifacts.root).valid)
            with self.assertRaisesRegex(RuntimeError, "already been recorded"):
                evaluator.evaluate(case, script, artifacts, run_spec)
            official_processes = [
                call
                for call in run.call_args_list
                if call.args and call.args[0] and call.args[0][0] == "uv"
            ]
            self.assertEqual(len(official_processes), 1)


if __name__ == "__main__":
    unittest.main()
