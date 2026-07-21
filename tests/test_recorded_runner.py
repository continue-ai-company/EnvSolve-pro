from __future__ import annotations

from pathlib import Path
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
from envsolve_harness.runners.recorded_envbench import (
    RecordedEnvBenchTrajectoryRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest, update_manifest


class RecordedTrajectoryRunnerTest(unittest.TestCase):
    def test_redistills_an_audited_distillation_only_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            runs = workspace / "runs"
            config = HarnessConfig(
                workspace_root=workspace,
                runs_root=runs,
                benchmarks={
                    "envbench": BenchmarkConfig(
                        "envbench", "envbench", workspace / "EnvBench"
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
            case = Case("owner/repo@abc", "owner/repo", "abc")
            source_spec = RunSpec(
                "source-run", "freeagent", "provider/model", seed=0
            )
            source = RunArtifacts.create(runs, source_spec.run_id, case.case_id)
            initialize_manifest(source, config, case, source_spec, protocol)
            write_jsonl(
                source.trajectory_jsonl,
                [
                    {
                        "node": "commands_history",
                        "commands": [
                            {
                                "command": (
                                    "cat optional.toml 2>/dev/null || echo missing"
                                ),
                                "exit_code": 0,
                            },
                            {"command": "pip install -e .", "exit_code": 0},
                        ],
                    }
                ],
            )
            source_result = SolverResult(
                False,
                source_spec.method,
                error=(
                    "EnvBench trajectory contains unsupported commands: "
                    "['synthetic old-policy rejection']"
                ),
                metadata={
                    "audit_requirements": {"repository_integrity": True},
                    "process_exit_code": 0,
                    "checked_out_revision": case.revision,
                    "repository_integrity": {"valid": True},
                },
            )
            write_json(source.solver_result, source_result.to_dict())
            update_manifest(source, solver=source_result.to_dict())
            write_json(source.status, {"state": "failed"})
            self.assertTrue(audit_run(source.root).valid)

            target_spec = RunSpec(
                "target-run", "recorded-freeagent", "provider/model", seed=0
            )
            target = RunArtifacts.create(runs, target_spec.run_id, case.case_id)
            initialize_manifest(target, config, case, target_spec, protocol)
            result = RecordedEnvBenchTrajectoryRunner(
                runs / source_spec.run_id
            ).run(case, target, target_spec)

            self.assertTrue(result.generation_completed)
            self.assertEqual(target.generated_script.read_text(), "pip install -e .\n")
            self.assertTrue(result.metadata["source_audit_valid"])
            self.assertTrue(result.metadata["source_distillation_only_failure"])
            self.assertEqual(
                result.metadata["distillation"]["policy"],
                "envbench-typed-replay-ir-v9",
            )
            generation_audit = audit_run(target.root)
            self.assertTrue(generation_audit.checks["repository_integrity"])

    def test_redistills_a_verified_envsolve_v0_distillation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            runs = workspace / "runs"
            config = HarnessConfig(
                workspace_root=workspace,
                runs_root=runs,
                benchmarks={
                    "envbench": BenchmarkConfig(
                        "envbench", "envbench", workspace / "EnvBench"
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
            case = Case("owner/repo@abc", "owner/repo", "abc")
            source_spec = RunSpec("source-v0", "envsolve-v0", "provider/model", seed=0)
            source = RunArtifacts.create(runs, source_spec.run_id, case.case_id)
            initialize_manifest(source, config, case, source_spec, protocol)
            write_jsonl(
                source.trajectory_jsonl,
                [
                    {
                        "node": "commands_history",
                        "commands": [
                            {"command": "pyenv global 3.11.9", "exit_code": 0},
                            {"command": 'eval "$(pyenv init -)"', "exit_code": 0},
                            {"command": "pip install -e .", "exit_code": 0},
                        ],
                    }
                ],
            )
            source_result = SolverResult(
                False,
                source_spec.method,
                error=(
                    "trajectory contains unsupported commands: "
                    "['synthetic old-policy rejection']"
                ),
                metadata={
                    "runner": "envsolve-v0",
                    "audit_requirements": {"repository_integrity": True},
                    "process_exit_code": 0,
                    "checked_out_revision": case.revision,
                    "repository_integrity": {"valid": True},
                    "v0_completion": {"passed": True},
                },
            )
            write_json(source.solver_result, source_result.to_dict())
            update_manifest(source, solver=source_result.to_dict())
            write_json(source.status, {"state": "failed"})
            self.assertTrue(audit_run(source.root).valid)

            target_spec = RunSpec(
                "target-v0", "recorded-envsolve-v0", "provider/model", seed=0
            )
            target = RunArtifacts.create(runs, target_spec.run_id, case.case_id)
            initialize_manifest(target, config, case, target_spec, protocol)
            result = RecordedEnvBenchTrajectoryRunner(runs / source_spec.run_id).run(
                case, target, target_spec
            )

            self.assertTrue(result.generation_completed)
            self.assertEqual(
                target.generated_script.read_text(),
                "pyenv global 3.11.9\n"
                'export PATH="$(pyenv root)/shims:$PATH"\n'
                "pip install -e .\n",
            )
            self.assertTrue(result.metadata["source_distillation_only_failure"])

    def test_rejects_unverified_envsolve_v0_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            runs = workspace / "runs"
            config = HarnessConfig(
                workspace_root=workspace,
                runs_root=runs,
                benchmarks={
                    "envbench": BenchmarkConfig(
                        "envbench", "envbench", workspace / "EnvBench"
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
            case = Case("owner/repo@abc", "owner/repo", "abc")
            source_spec = RunSpec("source-v0", "envsolve-v0", "provider/model", seed=0)
            source = RunArtifacts.create(runs, source_spec.run_id, case.case_id)
            initialize_manifest(source, config, case, source_spec, protocol)
            write_jsonl(
                source.trajectory_jsonl,
                [{"node": "commands_history", "commands": []}],
            )
            source_result = SolverResult(
                False,
                source_spec.method,
                error="trajectory contains unsupported commands: ['synthetic']",
                metadata={
                    "runner": "envsolve-v0",
                    "audit_requirements": {"repository_integrity": True},
                    "process_exit_code": 0,
                    "checked_out_revision": case.revision,
                    "repository_integrity": {"valid": True},
                    "v0_completion": {"passed": False},
                },
            )
            write_json(source.solver_result, source_result.to_dict())
            update_manifest(source, solver=source_result.to_dict())
            write_json(source.status, {"state": "failed"})

            target_spec = RunSpec(
                "target-v0", "recorded-envsolve-v0", "provider/model", seed=0
            )
            target = RunArtifacts.create(runs, target_spec.run_id, case.case_id)
            initialize_manifest(target, config, case, target_spec, protocol)
            result = RecordedEnvBenchTrajectoryRunner(runs / source_spec.run_id).run(
                case, target, target_spec
            )

            self.assertFalse(result.generation_completed)
            self.assertFalse(result.metadata["source_identity_valid"])


if __name__ == "__main__":
    unittest.main()
