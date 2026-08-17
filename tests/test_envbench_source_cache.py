from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from envsolve_harness.adapters.envbench import EnvBenchEvaluator
from envsolve_harness.core.io import write_jsonl
from envsolve_harness.core.models import (
    BenchmarkConfig,
    Case,
    HarnessConfig,
    RunSpec,
)
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest


@mock.patch(
    "envsolve_harness.adapters.envbench.docker_image_provenance",
    return_value={"reference": "test:image"},
)
@mock.patch(
    "envsolve_harness.adapters.envbench.git_provenance",
    return_value={"commit": "test"},
)
@mock.patch("envsolve_harness.adapters.envbench._run_envbench_process")
@mock.patch("envsolve_harness.adapters.envbench.ExactRevisionSourceCache")
def test_official_evaluator_preseeds_exact_revision_checkout(
    cache_type: mock.Mock,
    run_process: mock.Mock,
    git: mock.Mock,
    image: mock.Mock,
) -> None:
    del git, image
    receipt = {
        "source": "immutable-exact-revision-cache-v1",
        "cache_hit": True,
        "commit": "abc",
        "tree": "tree",
        "fsck": "pass",
        "checkout": "independent-no-hardlinks",
    }
    cache_type.return_value.acquire.return_value = receipt

    def execute(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        output = next(
            Path(item.split("=", 1)[1])
            for item in command
            if item.startswith("operation.dirs.json_results=")
        )
        write_jsonl(
            output / "results.jsonl",
            [
                {
                    "repo_name": "owner/repo",
                    "commit_sha": "abc",
                    "exit_code": 0,
                    "issues_count": 0,
                    "pyright": {
                        "summary": {"errorCount": 0, "warningCount": 0}
                    },
                }
            ],
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    run_process.side_effect = execute
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        envbench = workspace / "EnvBench"
        for relative in (
            "evaluation/main.py",
            "evaluation/scripts/python_build.sh",
            "env_setup_utils/repo_downloader.py",
        ):
            path = envbench / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n", encoding="utf-8")
        config = HarnessConfig(
            workspace_root=workspace,
            runs_root=workspace / "runs",
            benchmarks={
                "envbench": BenchmarkConfig(
                    "envbench",
                    "envbench",
                    envbench,
                    {"image": "test:image", "preseed_source_cache": True},
                )
            },
            git_fetch_timeout=29,
        )
        protocol = ExperimentProtocol(
            "test",
            "1",
            "envbench",
            "python",
            (SuccessCriteria("exit_code", "eq", 0),),
            (),
        )
        case = Case("owner/repo@abc", "owner/repo", "abc")
        run_spec = RunSpec("cached-official", "test-method")
        artifacts = RunArtifacts.create(
            config.runs_root, run_spec.run_id, case.case_id
        )
        initialize_manifest(artifacts, config, case, run_spec, protocol)
        script = workspace / "bootstrap.sh"
        script.write_text("true\n", encoding="utf-8")

        result = EnvBenchEvaluator(config, protocol).evaluate(
            case, script, artifacts, run_spec
        )

        destination = (
            artifacts.evaluation_dir / "repos" / "owner__repo@abc"
        )
        cache_type.assert_called_once_with(
            config.runs_root / "_source_cache/envbench-python", 29
        )
        cache_type.return_value.acquire.assert_called_once_with(
            repository="owner/repo",
            revision="abc",
            destination=destination,
        )
        assert result.evaluation_completed
        assert result.official_pass
        assert result.metadata["repository_acquisition"] == receipt


def test_preseed_source_cache_setting_must_be_boolean() -> None:
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        config = HarnessConfig(
            workspace_root=workspace,
            runs_root=workspace / "runs",
            benchmarks={
                "envbench": BenchmarkConfig(
                    "envbench",
                    "envbench",
                    workspace / "EnvBench",
                    {"image": "test:image", "preseed_source_cache": "yes"},
                )
            },
        )
        protocol = ExperimentProtocol(
            "test",
            "1",
            "envbench",
            "python",
            (SuccessCriteria("exit_code", "eq", 0),),
            (),
        )

        try:
            EnvBenchEvaluator(config, protocol)
        except ValueError as exc:
            assert "must be a boolean" in str(exc)
        else:
            raise AssertionError("non-boolean preseed setting was accepted")
