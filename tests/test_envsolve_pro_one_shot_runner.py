from __future__ import annotations

import tempfile
from pathlib import Path

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.core.io import read_json
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.envsolve_pro_one_shot import (
    METHOD,
    QualifiedEnvSolveProOneShotCertificationRunner,
)
from envsolve_harness.utils.provenance import sha256_file


def _runner(root: Path) -> QualifiedEnvSolveProOneShotCertificationRunner:
    return QualifiedEnvSolveProOneShotCertificationRunner(
        codex_executable=root / "codex",
        harness_root=root,
        source_cache_root=root / "source-cache",
        image="sha256:image",
        timeout=120,
        command_timeout=30,
        container_create_timeout=10,
        git_fetch_timeout=20,
        reasoning_effort="high",
        goal_contract=ExecutableGoalContract(
            "public-goal",
            "Require success",
            "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
        ),
    )


def test_one_shot_runner_changes_only_the_replay_policy() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        runner = _runner(root)
        case = Case("case", "owner/repo", "abc123")
        prompt = runner._prompt(case, runner.goal_contract)
        arguments = runner._mcp_server_args(
            trace_path=root / "generation" / "container-commands.jsonl",
            container_id="container",
            case=case,
            image_digest="sha256:image",
        )

        assert runner._goal_contract_for_run(
            RunSpec("run", METHOD, "gpt-5.5")
        ) is runner.goal_contract
        assert "MUST call `submit_and_replay` exactly once" in prompt
        assert "There is no second clean replay" in prompt
        assert "call `submit_and_replay` repeatedly" not in prompt
        assert "envsolve_harness.codex.one_shot_mcp_qualified" in arguments
        assert runner.infrastructure_profile == "codex-qualified-infrastructure-v1"


def test_one_shot_implementation_freeze_hashes_match() -> None:
    root = Path(__file__).resolve().parents[1]
    freeze = read_json(
        root
        / "experiments"
        / "protocols"
        / "envsolve_pro_certification_repair_ablation_v1_implementation_freeze.json"
    )

    for reference in (
        freeze["design_freeze"],
        freeze["qualified_infrastructure_freeze"],
        freeze["minimal_b_parent_freeze"],
    ):
        assert sha256_file(root / reference["path"]) == reference["sha256"]
    for group in ("source_sha256", "test_sha256"):
        for relative_path, expected in freeze[group].items():
            assert sha256_file(root / relative_path) == expected, relative_path
