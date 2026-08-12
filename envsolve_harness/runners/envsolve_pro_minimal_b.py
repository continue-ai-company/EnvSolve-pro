from __future__ import annotations

from collections import Counter
from pathlib import Path
import shutil
from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.codex.minimal_b_mcp import (
    CERTIFICATION_SCHEMA,
    REPLAY_SCHEMA,
    script_sha256,
)
from envsolve_harness.core.io import read_json, read_jsonl, write_json
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.codex_cli import CodexCliRunner
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file


METHOD = "envsolve-pro-minimal-b-v1"


class EnvSolveProMinimalBRunner(CodexCliRunner):
    """One active Agent session with repeatedly callable clean replay."""

    runner_name = "envsolve-pro-minimal-b"
    runner_version = "1.0.2"
    agent_interface = "continuous-agent+online-clean-replay-mcp-v1"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == METHOD else None

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        prompt = super()._prompt(case, goal_contract)
        if goal_contract is None:
            return prompt
        return (
            prompt
            + "\n"
            + """\
This is the frozen EnvSolve-Pro Minimal B interface. Keep all diagnosis and repair
inside this one conversation and the persistent construction container. Before
returning your final JSON, you MUST call `submit_and_replay` with the complete
self-contained bootstrap program. The tool runs that program in a distinct clean
checkout and container and returns only internal public-goal and integrity evidence
to this same session.

You may call `submit_and_replay` repeatedly. After Fail or Unknown, continue working
in this conversation, repair the complete program, and submit it again. Return a
final `bootstrap_script` only after the exact same program receives `status=pass` and
`certified=true`. Do not change a certified program before returning it. The terminal
Official evaluator remains unavailable.

The shared admissibility boundary rejects candidate-generated compatibility packages,
local distributions that expose modules absent from the repository, unowned import
artifacts, and deletion or falsification of installation metadata. Do not create a
module or stub solely to silence a missing-import finding.
"""
        )

    def _mcp_tool_names(self) -> tuple[str, ...]:
        return ("envbench_shell", "submit_and_replay")

    def _mcp_tool_timeout_seconds(self) -> int:
        return self.command_timeout + (2 * self.container_create_timeout) + 120

    @staticmethod
    def _minimal_b_root(trace_path: Path) -> Path:
        return trace_path.parent / "minimal-b"

    def _mcp_server_args(
        self,
        *,
        trace_path: Path,
        container_id: str,
        case: Case | None,
        image_digest: str | None,
    ) -> list[str]:
        if case is None:
            raise ValueError("Minimal B requires case identity for clean replay")
        if image_digest is None:
            raise ValueError("Minimal B requires a pinned image digest")
        if self.goal_contract is None:
            raise ValueError("Minimal B requires a public executable goal contract")
        root = self._minimal_b_root(trace_path)
        goal_path = root / "goal-contract.json"
        preconditions_path = root / "workspace-preconditions.json"
        write_json(goal_path, self.goal_contract.to_dict())
        write_json(
            preconditions_path,
            [item.to_dict() for item in self.workspace_preconditions],
        )
        return [
            "-m",
            "envsolve_harness.codex.minimal_b_mcp",
            "--container-id",
            container_id,
            "--workdir",
            "/data/project",
            "--command-trace",
            str(trace_path),
            "--replay-trace",
            str(root / "replays.jsonl"),
            "--certification",
            str(root / "certification.json"),
            "--programs-root",
            str(root / "programs"),
            "--source-repository",
            str(trace_path.parent / "workspace"),
            "--worktrees",
            str(root / "worktrees"),
            "--repository",
            case.repository,
            "--revision",
            case.revision,
            "--image",
            image_digest,
            "--goal-contract",
            str(goal_path),
            "--workspace-preconditions",
            str(preconditions_path),
            "--command-timeout",
            str(self.command_timeout),
            "--container-create-timeout",
            str(self.container_create_timeout),
            "--max-output-chars",
            "16000",
            "--docker",
            shutil.which("docker") or "docker",
        ]

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        root = artifacts.generation_dir / "minimal-b"
        replay_trace = root / "replays.jsonl"
        certification = root / "certification.json"
        records = read_jsonl(replay_trace) if replay_trace.is_file() else []
        statuses = Counter(str(item.get("status")) for item in records)
        metadata["minimal_b"] = {
            "design_freeze": "envsolve-pro-minimal-b-v1-design",
            "structured_state": False,
            "checkpointing": False,
            "hypothesis_search": False,
            "bootstrap_minimization": False,
            "replay_trace": {
                "path": str(replay_trace.relative_to(artifacts.root)),
                "sha256": sha256_file(replay_trace) if replay_trace.is_file() else None,
                "count": len(records),
                "status_counts": dict(sorted(statuses.items())),
            },
            "certification": {
                "path": str(certification.relative_to(artifacts.root)),
                "sha256": sha256_file(certification) if certification.is_file() else None,
            },
        }

    def _has_required_tool_activity(
        self,
        successful_command_count: int,
        metadata: dict[str, Any],
    ) -> bool:
        minimal_b = metadata.get("minimal_b", {})
        replay_trace = minimal_b.get("replay_trace", {})
        return replay_trace.get("count", 0) > 0

    def _required_tool_activity_error(self) -> str:
        return "Minimal B completed without an in-session clean replay submission"

    def _validate_additional_submission(
        self,
        script: str,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        certification_path = (
            artifacts.generation_dir / "minimal-b" / "certification.json"
        )
        if not certification_path.is_file():
            raise RuntimeError("Minimal B did not produce a certification record")
        certification = read_json(certification_path)
        if not isinstance(certification, dict) or certification.get("schema") != (
            CERTIFICATION_SCHEMA
        ):
            raise RuntimeError("Minimal B certification record is malformed")
        if self.goal_contract is None or certification.get(
            "goal_contract_sha256"
        ) != self.goal_contract.sha256:
            raise RuntimeError("Minimal B certificate goal contract does not match")
        if certification.get("revision") != metadata.get("checked_out_revision"):
            raise RuntimeError("Minimal B certificate revision does not match")
        if certification.get("image_digest") != metadata.get("image_digest"):
            raise RuntimeError("Minimal B certificate image does not match")
        certified = certification.get("certified_programs")
        if not isinstance(certified, list):
            raise RuntimeError("Minimal B certified program list is malformed")
        digest = script_sha256(script)
        matches = [
            item
            for item in certified
            if isinstance(item, dict)
            and item.get("program_sha256") == digest
            and isinstance(item.get("environment_receipt"), dict)
            and item["environment_receipt"].get("revision")
            == metadata.get("checked_out_revision")
            and item["environment_receipt"].get("image_digest")
            == metadata.get("image_digest")
        ]
        if not matches:
            raise RuntimeError(
                "Final bootstrap program did not pass in-session clean replay"
            )
        replay_trace = (
            artifacts.generation_dir / "minimal-b" / "replays.jsonl"
        )
        records = read_jsonl(replay_trace) if replay_trace.is_file() else []
        passing_ids = {
            str(record.get("replay_id"))
            for record in records
            if record.get("schema") == REPLAY_SCHEMA
            and record.get("status") == "pass"
            and record.get("certified") is True
            and record.get("program_sha256") == digest
        }
        matching_ids = {
            str(item.get("replay_id")) for item in matches
        }
        if not passing_ids.intersection(matching_ids):
            raise RuntimeError(
                "Minimal B certificate has no matching passing replay trace"
            )
        metadata["minimal_b"]["accepted_certificate"] = matches[-1]
        metadata["minimal_b"]["final_program_sha256"] = digest
