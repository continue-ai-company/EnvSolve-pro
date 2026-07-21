from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import write_json, write_jsonl
from envsolve_harness.core.models import (
    BenchmarkConfig,
    Case,
    HarnessConfig,
    RunSpec,
    SolverResult,
)
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.runners.recorded_codex import RecordedCodexCliRunner
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest, update_manifest


class RecordedCodexCliRunnerTest(unittest.TestCase):
    def test_refinalizes_only_a_valid_completed_episode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            config = HarnessConfig(
                workspace_root=root,
                runs_root=runs,
                benchmarks={
                    "envbench": BenchmarkConfig(
                        "envbench", "envbench", root / "EnvBench"
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
            source_workspace = root / "source-workspace"
            source_workspace.mkdir()
            (source_workspace / "setup.py").write_text("# fixture\n")
            subprocess.run(["git", "init", "-q"], cwd=source_workspace, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.test"],
                cwd=source_workspace,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=source_workspace,
                check=True,
            )
            subprocess.run(["git", "add", "setup.py"], cwd=source_workspace, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "fixture"], cwd=source_workspace, check=True
            )
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source_workspace,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            case = Case("owner/repo@revision", "owner/repo", revision)
            source_spec = RunSpec("source-codex", "codex-cli-native", "gpt-5.5")
            source = RunArtifacts.create(runs, source_spec.run_id, case.case_id)
            initialize_manifest(source, config, case, source_spec, protocol)
            target_workspace = source.generation_dir / "workspace"
            subprocess.run(
                ["git", "clone", "-q", str(source_workspace), str(target_workspace)],
                check=True,
            )
            subprocess.run(
                ["git", "checkout", "--detach", revision],
                cwd=target_workspace,
                check=True,
                capture_output=True,
            )
            write_jsonl(
                source.trajectory_jsonl,
                [{"type": "turn.completed", "usage": {"input_tokens": 12}}],
            )
            write_jsonl(
                source.generation_dir / "container-commands.jsonl",
                [
                    {
                        "command": "python -m pip install -e .",
                        "exit_code": 0,
                        "timed_out": False,
                        "infrastructure_error": None,
                    }
                ],
            )
            output = source.generation_dir / "codex-control/final-output.json"
            write_json(
                output,
                {
                    "bootstrap_script": "python -m pip install -e .\n",
                    "summary": "Install the local project",
                },
            )
            source_result = SolverResult(
                False,
                source_spec.method,
                error=(
                    "RuntimeError: Codex CLI repository integrity failed: "
                    "synthetic old-policy rejection"
                ),
                metadata={
                    "runner": "codex-cli",
                    "process_exit_code": 0,
                    "checked_out_revision": revision,
                    "token_usage": {"input_tokens": 12},
                },
            )
            write_json(source.solver_result, source_result.to_dict())
            update_manifest(source, solver=source_result.to_dict())
            write_json(source.status, {"state": "failed"})
            self.assertTrue(audit_run(source.root).valid)

            target_spec = RunSpec(
                "target-codex", "codex-cli-native-recorded", "gpt-5.5"
            )
            target = RunArtifacts.create(runs, target_spec.run_id, case.case_id)
            initialize_manifest(target, config, case, target_spec, protocol)

            result = RecordedCodexCliRunner(runs / source_spec.run_id).run(
                case, target, target_spec
            )

            self.assertTrue(result.generation_completed, result.error)
            self.assertEqual(
                target.generated_script.read_text(), "python -m pip install -e .\n"
            )
            self.assertFalse(result.metadata["model_reexecuted"])
            self.assertTrue(result.metadata["source_identity_valid"])
            self.assertEqual(result.metadata["token_usage"], {"input_tokens": 12})


if __name__ == "__main__":
    unittest.main()
