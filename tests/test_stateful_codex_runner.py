from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import pytest

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.stateful_goal_verifier_v2 import (
    StatefulExecutableGoalVerifierV2,
    StatefulExecutableGoalVerifierV21,
)
from envsolve.runtime.stateful_goal_verifier_v23 import (
    StatefulExecutableGoalVerifierV23,
    python_same_environment_alias_audit_command,
)
from envsolve.runtime.stateful_goal_verifier_v24 import (
    StatefulExecutableGoalVerifierV24,
)
from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    EpisodeBudgetExhausted,
    ProvisionedEnvironment,
)
from envsolve.state import EnvironmentState
from envsolve_harness.core.models import (
    BenchmarkConfig,
    Case,
    HarnessConfig,
    RunSpec,
)
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.runners.registry import RunnerOptions
from experiments.run_stateful_codex_case import (
    RUNNER_METHODS,
    _factory,
)
from envsolve_harness.runners.stateful_codex import (
    CodexInteractivePolicy,
    ExecutionOnlyBudget,
    StatefulCodexCliRunner,
    state_projection,
)
from experiments import run_schedule
from experiments.extensible_schedule import install_runner_entrypoints


def _finding(name: str) -> dict[str, object]:
    return {
        "finding_id": f"missing-{name}",
        "domain": "module",
        "subject": name,
        "predicate": "present",
        "required": True,
        "observed": False,
        "provenance": {
            "file": f"/data/project/owner__repo@abc/src/{name}.py",
            "rule": "reportMissingImports",
        },
    }


def _state() -> EnvironmentState:
    state = EnvironmentState(
        "case",
        case={
            "case_id": "case",
            "repository": "owner/repo",
            "revision": "abc",
        },
    )
    state.actions["candidate-1"] = {
        "action_id": "candidate-1",
        "command": "python -m pip install alpha",
        "status": "failed",
        "exit_code": 1,
        "observation": {"stderr": "alpha remains unresolved"},
        "metadata": {
            "diagnostic_workspace_integrity": {
                "valid": True,
            }
        },
        "state_metadata": {"event_sequence": 3},
    }
    state.failures["failure-1"] = {
        "failure_id": "failure-1",
        "category": "executable-verification-failure",
        "message": "one unresolved import",
        "action_id": "candidate-1",
        "details": {"finding_count": 1},
        "state_metadata": {"event_sequence": 5},
    }
    state.verifications.append(
        {
            "verification_id": "verification-candidate-1",
            "passed": False,
            "details": {
                "candidate_id": "candidate-1",
                "reported_passed": False,
                "bootstrap_exit_code": 0,
                "summary": "one unresolved import",
                "candidate_assessment": {
                    "admissible": True,
                    "unresolved_constraints": 1,
                    "satisfied_constraints": 2,
                },
                "verifier_details": {
                    "goal_report": {
                        "schema": "envsolve-goal-report-v1",
                        "status": "fail",
                        "finding_set_complete": True,
                        "findings": [_finding("alpha")],
                    }
                },
            },
        }
    )
    return state


def test_structured_projection_adds_memory_without_removing_raw_evidence() -> None:
    state = _state()
    before = state.to_dict()

    raw = state_projection(state, "raw")
    structured = state_projection(state, "structured")

    for key in (
        "case",
        "prior_candidates",
        "recent_failures",
        "recent_verifications",
    ):
        assert structured[key] == raw[key]
    assert "active_goal_state" not in raw
    assert "best_integrity_valid_candidate" not in raw
    assert structured["active_goal_state"]["summary"][
        "active_finding_count"
    ] == 1
    assert structured["active_goal_state"]["raw_findings_retained"] is True
    assert (
        structured["best_integrity_valid_candidate"]["script"]
        == "python -m pip install alpha"
    )
    assert state.to_dict() == before


def test_state_projection_rejects_unknown_condition() -> None:
    with pytest.raises(ValueError, match="Unsupported stateful-agent mode"):
        state_projection(_state(), "compressed")


class _ScriptedPolicy(CodexInteractivePolicy):
    def __init__(self, root: Path, *, initial_probe: bool = False) -> None:
        contract = ExecutableGoalContract(
            "public-goal",
            "Require no missing imports",
            "python -m pyright . --outputjson",
        )
        runner = StatefulCodexCliRunner(
            codex_executable=root / "codex",
            harness_root=root,
            image="envbench:test",
            timeout=120,
            command_timeout=30,
            container_create_timeout=10,
            git_fetch_timeout=20,
            goal_contract=contract,
            max_rounds=3,
            feedback_mode="structured",
        )
        super().__init__(
            runner=runner,
            case=Case("case", "owner/repo", "abc"),
            run_spec=RunSpec(
                "run",
                "envsolve-pro-stateful-agent-v1",
                "gpt-5.5",
            ),
            container_id="fixture",
            workspace=root,
            rounds_root=root / "rounds",
            feedback_mode="structured",
            max_rounds=3,
            deadline=time.monotonic() + 60,
            initial_probe=initial_probe,
        )
        self.seen_projection: dict[str, object] | None = None

    def _invoke(self, projection):
        self.round_count += 1
        self.seen_projection = projection
        return {
            "bootstrap_script": "python -m pip install -e .",
            "summary": "install the checked-out project",
            "projection_sha256": "fixture-projection",
            "diagnostic_workspace_integrity": {"valid": True},
        }


def test_codex_operation_policy_returns_an_open_cumulative_program() -> None:
    with tempfile.TemporaryDirectory() as directory:
        policy = _ScriptedPolicy(Path(directory))

        candidate = policy.propose(_state())

    assert candidate.script == "python -m pip install -e ."
    assert candidate.metadata["feedback_mode"] == "structured"
    assert candidate.metadata["state_projection_sha256"] == "fixture-projection"
    assert policy.seen_projection is not None
    assert "active_goal_state" in policy.seen_projection
    assert "operation_contract" not in candidate.metadata


def test_v2_initial_probe_precedes_the_first_model_operation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        policy = _ScriptedPolicy(Path(directory), initial_probe=True)

        probe = policy.propose(
            EnvironmentState("case", case={"case_id": "case"})
        )
        candidate = policy.propose(_state())

    assert probe.candidate_id == "stateful-initial-observation"
    assert probe.script == ":"
    assert probe.metadata["execution_role"] == "initial-observation"
    assert probe.metadata["agent_round"] == 0
    assert candidate.candidate_id == "stateful-agent-0001"
    assert policy.round_count == 1
    assert policy.metadata()["initial_probe_submitted"] is True


def test_repair_prompt_uses_internal_feedback_not_official_evaluator() -> None:
    with tempfile.TemporaryDirectory() as directory:
        policy = _ScriptedPolicy(Path(directory))
        policy.round_count = 2

        prompt = policy._prompt(state_projection(_state(), "structured"))
        normalized = " ".join(prompt.split())

    assert '<solver_state mode="structured">' in prompt
    assert '"subject": "alpha"' in prompt
    assert "official evaluator result" in normalized
    assert "fresh checkout" in normalized
    assert "hard admissibility feedback" in normalized


def test_execution_budget_has_no_token_or_cost_limit() -> None:
    budget = ExecutionOnlyBudget(max_items=1, wall_clock_seconds=60)
    budget.reserve_candidate("candidate-1")
    budget.reserve_environment("candidate-1")
    budget.reserve_command("candidate-1")

    snapshot = budget.snapshot()

    assert snapshot["model_tokens_are_hard_limit"] is False
    assert snapshot["model_cost_is_hard_limit"] is False
    assert "tokens" not in snapshot["limits"]
    assert "cost" not in snapshot["limits"]
    with pytest.raises(EpisodeBudgetExhausted) as error:
        budget.reserve_candidate("candidate-2")
    assert error.value.scope == "candidates"


def test_stateful_experiment_factory_preserves_the_builtin_registry() -> None:
    builtin_methods = {
        "codex-stateful-raw": "codex-cli-goal-aware-raw-repair",
        "envsolve-pro-stateful-agent": "envsolve-pro-stateful-agent-v1",
        "codex-stateful-raw-v2": "codex-cli-goal-aware-raw-repair-v2",
        "envsolve-pro-stateful-agent-v2": "envsolve-pro-stateful-agent-v2",
        "codex-stateful-raw-v2.1": "codex-cli-goal-aware-raw-repair-v2.1",
        "envsolve-pro-stateful-agent-v2.1": "envsolve-pro-stateful-agent-v2.1",
        "codex-stateful-raw-v2.2": "codex-cli-goal-aware-raw-repair-v2.2",
        "envsolve-pro-stateful-agent-v2.2": "envsolve-pro-stateful-agent-v2.2",
    }
    assert RUNNER_METHODS.items() >= builtin_methods.items()
    assert RUNNER_METHODS["codex-stateful-raw-v2.3"] == (
        "codex-cli-goal-aware-raw-repair-v2.3"
    )
    assert RUNNER_METHODS["envsolve-pro-stateful-agent-v2.3"] == (
        "envsolve-pro-stateful-agent-v2.3"
    )
    assert RUNNER_METHODS["codex-stateful-raw-v2.4"] == (
        "codex-cli-goal-aware-raw-repair-v2.4"
    )
    assert RUNNER_METHODS["envsolve-pro-stateful-agent-v2.4"] == (
        "envsolve-pro-stateful-agent-v2.4"
    )

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = HarnessConfig(
            workspace_root=root,
            runs_root=root / "runs",
            benchmarks={
                "envbench": BenchmarkConfig(
                    "envbench",
                    "envbench",
                    root,
                    {"image": "envbench:test"},
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
        runner = _factory(
            config,
            protocol,
            RunSpec(
                "run",
                "envsolve-pro-stateful-agent-v1",
                "gpt-5.5",
            ),
            RunnerOptions(),
        )

    assert isinstance(runner, StatefulCodexCliRunner)
    assert runner.feedback_mode == "structured"
    assert runner.initial_probe is False

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = HarnessConfig(
            workspace_root=root,
            runs_root=root / "runs",
            benchmarks={
                "envbench": BenchmarkConfig(
                    "envbench",
                    "envbench",
                    root,
                    {"image": "envbench:test"},
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
        runner_v2 = _factory(
            config,
            protocol,
            RunSpec(
                "run-v2",
                "envsolve-pro-stateful-agent-v2",
                "gpt-5.5",
            ),
            RunnerOptions(),
        )

    assert isinstance(runner_v2, StatefulCodexCliRunner)
    assert runner_v2.feedback_mode == "structured"
    assert runner_v2.method_profile == "stateful-agent-v2"
    assert runner_v2.initial_probe is True
    assert runner_v2.enforce_project_namespace_provenance is True
    assert runner_v2.restore_shell_invariants is True

    runner_v21 = _factory(
        config,
        protocol,
        RunSpec(
            "run-v2.1",
            "envsolve-pro-stateful-agent-v2.1",
            "gpt-5.5",
        ),
        RunnerOptions(),
    )
    assert isinstance(runner_v21, StatefulCodexCliRunner)
    assert runner_v21.method_profile == "stateful-agent-v2.1"

    runner_v22 = _factory(
        config,
        protocol,
        RunSpec(
            "run-v2.2",
            "envsolve-pro-stateful-agent-v2.2",
            "gpt-5.5",
        ),
        RunnerOptions(),
    )
    assert isinstance(runner_v22, StatefulCodexCliRunner)
    assert runner_v22.method_profile == "stateful-agent-v2.2"

    runner_v23 = _factory(
        config,
        protocol,
        RunSpec(
            "run-v2.3",
            "envsolve-pro-stateful-agent-v2.3",
            "gpt-5.5",
        ),
        RunnerOptions(),
    )
    assert isinstance(runner_v23, StatefulCodexCliRunner)
    assert runner_v23.method_profile == "stateful-agent-v2.3"
    assert runner_v23.initial_probe is False
    assert runner_v23.enforce_project_namespace_provenance is False
    assert runner_v23.restore_shell_invariants is False

    runner_v24 = _factory(
        config,
        protocol,
        RunSpec(
            "run-v2.4",
            "envsolve-pro-stateful-agent-v2.4",
            "gpt-5.5",
        ),
        RunnerOptions(),
    )
    assert isinstance(runner_v24, StatefulCodexCliRunner)
    assert runner_v24.method_profile == "stateful-agent-v2.4"
    assert runner_v24.initial_probe is False
    assert runner_v24.enforce_project_namespace_provenance is False
    assert runner_v24.restore_shell_invariants is False


def test_v23_alias_audit_uses_the_goal_shell_python_resolution() -> None:
    command = python_same_environment_alias_audit_command(
        "/data/project/example"
    )

    assert command.startswith("python -c ")
    assert "command python" not in command
    assert " -I " not in command


def test_v23_verifier_compacts_only_the_structured_condition() -> None:
    contract = ExecutableGoalContract(
        "public-goal",
        "Require no missing imports",
        "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
    )

    raw = StatefulExecutableGoalVerifierV23(contract)
    structured = StatefulExecutableGoalVerifierV23(
        contract,
        compact_findings=True,
    )

    assert raw.finding_adapter.schema == "envsolve-structured-finding-adapter-v3"
    assert structured.finding_adapter.schema == (
        "envsolve-root-obligation-finding-adapter-v1"
    )


def _v24_result(
    *,
    observed_cwd: str,
    effect_valid: bool,
    import_alias_valid: bool = True,
) -> object:
    class EffectReport:
        valid = effect_valid

        def to_dict(self):
            return {
                "valid": self.valid,
                "policy": "fixture-effect-audit",
                "violations": (
                    []
                    if self.valid
                    else [
                        {
                            "kind": "untracked_configuration",
                            "path": "pyrightconfig.json",
                            "detail": "configuration must remain external",
                        }
                    ]
                ),
            }

    contract = ExecutableGoalContract(
        "public-goal",
        "Require no missing imports",
        "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
    )

    def run_command(command, **kwargs):
        nonce = re.search(
            r"ENVSOLVE_GOAL_REPORT_BEGIN_V1=([0-9a-f]+)",
            command[-1],
        ).group(1)
        payload = {
            "schema": contract.report_schema,
            "status": "pass",
            "finding_set_complete": True,
            "findings": [],
            "details": {"issues_count": 0},
        }
        stdout = "\n".join(
            [
                f"ENVSOLVE_CANDIDATE_CWD_V1={observed_cwd}",
                f"ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1={nonce}",
                "ENVSOLVE_IMPORT_ALIAS_AUDIT_V1="
                + json.dumps(
                    {
                        "valid": import_alias_valid,
                        "violations": (
                            []
                            if import_alias_valid
                            else [
                                {
                                    "alias": "synthetic_name",
                                    "target": "/tmp/generated.py",
                                }
                            ]
                        ),
                    }
                ),
                f"ENVSOLVE_GOAL_REPORT_BEGIN_V1={nonce}",
                json.dumps(payload),
                f"ENVSOLVE_GOAL_REPORT_END_V1={nonce}",
            ]
        )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    environment = ProvisionedEnvironment(
        EnvironmentReceipt(
            "container-1",
            "fixture-provider",
            "sha256:image",
            "owner/repo",
            "abc",
            "2026-07-30T00:00:00+00:00",
        ),
        DockerEnvironmentHandle(
            "container-1",
            Path("/tmp/worktree"),
            "/data/project",
        ),
    )
    return StatefulExecutableGoalVerifierV24(
        contract,
        compact_findings=True,
        effect_auditor=lambda _: EffectReport(),
        run_command=run_command,
    ).verify(
        DeploymentCandidate("candidate-1", ":", "No-op"),
        environment,
    )


def test_v24_preserves_goal_pass_across_an_exact_effect_failure() -> None:
    result = _v24_result(
        observed_cwd="/data/project",
        effect_valid=False,
    )

    assert result.passed is False
    assert result.details["goal_status"] == "satisfied"
    operation = result.details["operation_contract"]
    assert operation["status"] == "violated"
    assert operation["repository_effect_valid"] is False
    assert operation["violations"] == [
        {
            "kind": "untracked_configuration",
            "path": "pyrightconfig.json",
            "detail": "configuration must remain external",
        }
    ]
    assert result.candidate_assessment is None
    assert "untracked_configuration: pyrightconfig.json" in result.summary


def test_v24_rejects_a_goal_pass_that_breaks_the_caller_cwd() -> None:
    result = _v24_result(
        observed_cwd="/tmp/pyright-work",
        effect_valid=True,
    )

    assert result.passed is False
    assert result.details["goal_status"] == "satisfied"
    working_directory = result.details["operation_contract"][
        "shell_postconditions"
    ]["working_directory"]
    assert working_directory == {
        "required": "/data/project",
        "observed": "/tmp/pyright-work",
        "satisfied": False,
    }
    assert result.details["operation_contract"]["violations"][0]["kind"] == (
        "shell_postcondition"
    )


def test_v24_terminal_pass_has_no_false_inadmissible_assessment() -> None:
    result = _v24_result(
        observed_cwd="/data/project",
        effect_valid=True,
    )

    assert result.passed is True
    assert result.candidate_assessment is None
    assert result.details["operation_contract"]["status"] == "satisfied"


def test_v24_includes_existing_integrity_failures_in_operation_contract() -> None:
    result = _v24_result(
        observed_cwd="/data/project",
        effect_valid=True,
        import_alias_valid=False,
    )

    assert result.passed is False
    assert result.details["goal_status"] == "unknown"
    operation = result.details["operation_contract"]
    assert operation["status"] == "violated"
    assert operation["violations"] == [
        {
            "kind": "synthetic_import_alias",
            "alias": "synthetic_name",
            "target": "/tmp/generated.py",
        }
    ]


def test_v24_projection_keeps_goal_and_operation_status_separate() -> None:
    state = _state()
    state.verifications.append(
        {
            "verification_id": "verification-candidate-2",
            "passed": False,
            "details": {
                "candidate_id": "candidate-2",
                "verifier_details": {
                    "goal_status": "satisfied",
                    "operation_contract": {
                        "status": "violated",
                        "valid": False,
                        "goal_status": "satisfied",
                        "repository_effect_valid": False,
                        "shell_postconditions": {},
                        "violations": [
                            {
                                "kind": "untracked_configuration",
                                "path": "pyrightconfig.json",
                            }
                        ],
                    },
                },
            },
        }
    )

    projection = state_projection(
        state,
        "structured",
        compact=True,
        operation_feedback=True,
    )

    assert projection["schema"] == "envsolve-agent-state-v3"
    assert projection["operation_state"]["goal_status"] == "satisfied"
    assert projection["operation_state"]["operation_status"] == "violated"
    assert projection["operation_state"]["violations"][0] == {
        "kind": "untracked_configuration",
        "path": "pyrightconfig.json",
    }


def test_v2_goal_verifier_restores_shell_boundary_before_trusted_checks() -> None:
    contract = ExecutableGoalContract(
        "public-goal",
        "Require no missing imports",
        "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
    )
    verifier = StatefulExecutableGoalVerifierV2(contract)
    candidate = DeploymentCandidate(
        "candidate-1",
        "set +e\nset -u\nset -o pipefail\nIFS=:\ncd /tmp\n:",
        "Exercise candidate-owned shell state",
    )
    handle = DockerEnvironmentHandle(
        "container-1",
        Path("/tmp/worktree"),
        "/data/project",
    )

    command, _, _ = verifier._command(candidate, handle, "0" * 32)

    boundary = (
        "cd /tmp\n:\n"
        "set +u\n"
        "set +x\n"
        "set +o pipefail\n"
        "IFS=$' \\t\\n'\n"
        "trap - EXIT ERR RETURN DEBUG\n"
        "set -e\n"
        "cd -- /data/project"
    )
    assert boundary in command
    assert command.endswith('exit "$ENVSOLVE_GOAL_EXIT_CODE"')


def test_v2_goal_verifier_returns_namespace_provenance_feedback() -> None:
    def run_command(command, **kwargs):
        marker = re.search(
            r"ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1=[0-9a-f]+",
            command[-1],
        ).group(0)
        audit = {
            "valid": False,
            "provided_modules": ["micropy"],
            "violations": [
                {
                    "alias": "micropy",
                    "divergent_sources": ["cli.py"],
                    "path": "/tmp/old/micropy",
                    "search_root": "/tmp/old",
                    "reason": (
                        "external import search root contributes divergent "
                        "project source"
                    ),
                }
            ],
        }
        return subprocess.CompletedProcess(
            command,
            0,
            (
                marker
                + "\nENVSOLVE_IMPORT_ALIAS_AUDIT_V1="
                + json.dumps(audit)
                + "\n"
            ),
            "",
        )

    contract = ExecutableGoalContract(
        "public-goal",
        "Require no missing imports",
        "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
    )
    with tempfile.TemporaryDirectory() as directory:
        worktree = Path(directory)
        environment = ProvisionedEnvironment(
            EnvironmentReceipt(
                "container-1",
                "fixture-provider",
                "sha256:image",
                "owner/repo",
                "abc",
                "2026-07-29T00:00:00+00:00",
            ),
            DockerEnvironmentHandle(
                "container-1",
                worktree,
                "/data/project",
            ),
        )
        result = StatefulExecutableGoalVerifierV2(
            contract,
            run_command=run_command,
        ).verify(
            DeploymentCandidate("candidate-1", ":", "No-op"),
            environment,
        )

    assert result.passed is False
    assert result.check_profile == "executable-goal-contract-v3"
    assert "external source" in result.summary
    assert result.observations[0].value["kind"] == (
        "project-namespace-provenance"
    )


def test_v21_initial_probe_observes_goal_without_candidate_provenance() -> None:
    contract = ExecutableGoalContract(
        "public-goal",
        "Require no missing imports",
        "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
    )
    verifier = StatefulExecutableGoalVerifierV21(contract)
    handle = DockerEnvironmentHandle(
        "container-1",
        Path("/tmp/worktree"),
        "/data/project",
    )
    probe = DeploymentCandidate(
        "stateful-initial-observation",
        ":",
        "Observe the base goal",
        metadata={"execution_role": "initial-observation"},
    )
    candidate = DeploymentCandidate(
        "candidate-1",
        ":",
        "Verify a model candidate",
    )

    probe_command, _, _ = verifier._command(probe, handle, "0" * 32)
    candidate_command, _, _ = verifier._command(candidate, handle, "1" * 32)

    assert "python-import-source-provenance-v2" not in probe_command
    assert "python-import-source-provenance-v2" in candidate_command
    assert "set +o pipefail" not in probe_command
    assert "set +o pipefail" in candidate_command


def test_experimental_schedule_dispatch_does_not_modify_frozen_coordinator(
    monkeypatch,
) -> None:
    observed: list[list[object]] = []

    def execute(command, *, cwd, timeout_seconds):
        observed.append(command)
        return {"state": "process_finished", "process_exit_code": 0}

    monkeypatch.setattr(run_schedule, "run_scheduled_process", execute)
    install_runner_entrypoints(
        {
            "envsolve-pro-stateful-agent-v2": (
                "experiments/run_stateful_codex_case.py"
            )
        }
    )

    result = run_schedule.run_scheduled_process(
        [
            "python",
            str(run_schedule.ROOT / "experiments/run_case.py"),
            "--runner",
            "envsolve-pro-stateful-agent-v2",
        ],
        cwd=run_schedule.ROOT,
        timeout_seconds=60,
    )

    assert result["process_exit_code"] == 0
    assert observed[0][1] == str(
        run_schedule.ROOT / "experiments/run_stateful_codex_case.py"
    )
