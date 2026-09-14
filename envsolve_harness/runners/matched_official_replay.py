from __future__ import annotations

from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.boundary_v6 import REPOSITORY_POLICY
from envsolve_harness.codex.minimal_b_mcp import canonical_script
from envsolve_harness.core.io import read_jsonl
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.codex_cli import CodexCliRunner
from envsolve_harness.runners.official_path_replay import (
    RemoteOfficialPathMinimalBRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts

REAL_METHOD = "envsolve-pro-matched-envbench-replay-real-v2"
WITHHELD_METHOD = "envsolve-pro-matched-envbench-replay-withheld-v2"


class _RemoteOfficialPathMatchedReplayRunner(RemoteOfficialPathMinimalBRunner):
    feedback_mode: str
    expected_method: str
    runner_version = "2.0.0"
    agent_interface = "continuous-agent+matched-envbench-path-replay-mcp-v2"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == self.expected_method else None

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        prompt = CodexCliRunner._prompt(self, case, goal_contract)
        if goal_contract is None:
            return prompt
        return (
            prompt
            + "\n"
            + """\
Keep diagnosis, construction, and repair inside this one continuous Agent session.
When you have a complete self-contained bootstrap program, call
`submit_and_replay` with those exact bytes. The tool always returns the same schema.

If `status=fail`, use only the returned public target-state evidence to repair the
complete program, then submit the revised complete program again. If
`status=infrastructure_error`, retry the unchanged program once before deciding
whether any semantic repair is justified. If `status=pass`, return that exact
program. If `status=withheld`, no target-state evidence was disclosed; return the
submitted program unchanged. The terminal Official evaluator is not available in
this session and runs only after your final answer.
"""
        )

    def _mcp_server_args(self, **kwargs: Any) -> list[str]:
        arguments = super()._mcp_server_args(**kwargs)
        arguments.extend(["--feedback-mode", self.feedback_mode])
        return arguments

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        metadata["matched_replay"] = {
            "feedback_mode": self.feedback_mode,
            "prompt_and_tool_schema_matched": True,
            "replay_executor_path": "envbench-candidate-executor",
            "target_state_feedback_returned_to_agent": self.feedback_mode == "real",
            "official_feedback_returned_to_agent": False,
            "final_program_matches_last_submission": None,
        }

    def _validate_additional_submission(
        self,
        script: str,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        replay_root = artifacts.generation_dir / "minimal-b"
        trace_path = replay_root / "replays.jsonl"
        records = read_jsonl(trace_path) if trace_path.is_file() else []
        last_program: str | None = None
        if records:
            artifact = records[-1].get("program_artifact")
            if isinstance(artifact, str):
                path = replay_root / artifact
                if path.is_file():
                    last_program = path.read_text(encoding="utf-8")
        matched = (
            last_program is not None
            and canonical_script(last_program) == canonical_script(script)
        )
        metadata["matched_replay"].update(
            {
                "submission_count": len(records),
                "last_feedback_status": records[-1].get("status") if records else None,
                "final_program_matches_last_submission": matched,
            }
        )

    def _qualify_submission_integrity(
        self,
        script: str,
        case: Case,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        del script, case, artifacts, metadata
        return {
            "policy": REPOSITORY_POLICY,
            "valid": True,
            "qualification": "postepisode-primary-endpoint-candidate",
            "feedback_returned_to_agent": self.feedback_mode == "real",
            "violations": [],
        }


class RemoteOfficialPathMatchedReplayRealRunner(
    _RemoteOfficialPathMatchedReplayRunner
):
    runner_name = "envsolve-pro-matched-envbench-replay-real-remote-v2"
    feedback_mode = "real"
    expected_method = REAL_METHOD


class RemoteOfficialPathMatchedReplayWithheldRunner(
    _RemoteOfficialPathMatchedReplayRunner
):
    runner_name = "envsolve-pro-matched-envbench-replay-withheld-remote-v2"
    feedback_mode = "withheld"
    expected_method = WITHHELD_METHOD
