from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Literal

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve.solver import DeploymentCandidate
from envsolve_harness.compatibility_ledger import (
    CompatibilityLedgerService,
    ScheduledCompatibilityObserver,
    model_visible_scheduled_observation,
)
from envsolve_harness.current_goal import CurrentGoalService
from envsolve_harness.codex.container_mcp import (
    ContainerMcpServer,
)
from envsolve_harness.execution.v2_container_shell import (
    V2ProcessTreeSafePersistentContainerShell,
)
from envsolve_harness.codex.minimal_b_mcp import (
    CleanReplayService,
    canonical_script,
    script_sha256,
)
from envsolve_harness.core.io import read_jsonl, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.execution.batch import cleanup_case_containers
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache
from envsolve_harness.integrity.minimal import (
    MinimalIntegrityGoalVerifier,
    inspect_minimal_repository_integrity,
)
from envsolve_harness.incremental_program import IncrementalProgram
from envsolve_harness.replay_feedback import normalize_replay_feedback
from envsolve_harness.replay_obligation_ledger import (
    ObligationSnapshotCleanReplayService,
    ReplayObligationLedger,
)
from envsolve_harness.runners.codex_cli import CodexCliRunner
from envsolve_harness.scripts.minimal_integrity import (
    MinimalIntegrityCandidateValidator,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file


DEEPSEEK_V4_PRO = "deepseek/deepseek-v4-pro"
DEEPSEEK_V4_FLASH_0731 = "deepseek/deepseek-v4-flash-0731"
DEEPSEEK_DIRECT_V4_FLASH = "deepseek-v4-flash"
SUPPORTED_DEEPSEEK_MODELS = frozenset(
    {
        DEEPSEEK_V4_PRO,
        DEEPSEEK_V4_FLASH_0731,
        DEEPSEEK_DIRECT_V4_FLASH,
    }
)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEEPSEEK_DIRECT_BASE_URL = "https://api.deepseek.com"
ReplayMode = Literal[
    "none",
    "atomic",
    "atomic-handoff",
    "soft",
    "incumbent",
    "current",
    "ledger",
    "scheduled",
    "operation-frontier",
    "handoff",
    "stateful",
    "incremental",
    "incremental-annotated",
    "incremental-editable",
    "incremental-transactional-editable",
]
ClientFactory = Callable[..., Any]
_PROVIDER_RETRY_DELAYS_SECONDS = (2, 10, 30, 60, 120, 240)


def _prepare_episode_package_cache(cache_root: Path) -> Path:
    cache_root = cache_root.resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    # Docker user-namespace mappings must be able to create package-manager subdirs.
    cache_root.chmod(0o777)
    return cache_root


def _certified_repository_integrity(
    replay_service: CleanReplayService,
    program_sha256: str,
) -> dict[str, Any]:
    if not any(
        item.get("program_sha256") == program_sha256
        for item in replay_service.certified_programs
    ):
        raise RuntimeError("submitted program has no clean-replay certificate")
    matching_replays = [
        item
        for item in read_jsonl(replay_service.trace_path)
        if item.get("program_sha256") == program_sha256
        and item.get("status") == "pass"
        and item.get("certified") is True
    ]
    if not matching_replays:
        raise RuntimeError("submitted program has no passing replay record")
    verification = matching_replays[-1].get("verification")
    bounded_details = (
        verification.get("details") if isinstance(verification, dict) else None
    )
    encoded_details = (
        bounded_details.get("json") if isinstance(bounded_details, dict) else None
    )
    try:
        details = json.loads(encoded_details) if isinstance(encoded_details, str) else None
    except json.JSONDecodeError as exc:
        raise RuntimeError("clean-replay repository audit is malformed") from exc
    integrity = details.get("repository_effect_audit") if isinstance(details, dict) else None
    if not isinstance(integrity, dict) and isinstance(details, dict):
        report_details = details.get("report_details")
        integrity = (
            report_details.get("repository_effect_audit")
            if isinstance(report_details, dict)
            else None
        )
    if not isinstance(integrity, dict) or integrity.get("valid") is not True:
        raise RuntimeError("clean replay has no valid repository audit")
    return integrity


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if isinstance(value, dict):
        return value
    raise ValueError(f"Provider response is not serializable: {type(value).__name__}")


def _tool_call_dict(call: Any) -> dict[str, Any]:
    function = call.function
    return {
        "id": str(call.id),
        "type": "function",
        "function": {
            "name": str(function.name),
            "arguments": str(function.arguments),
        },
    }


def _usage_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return _model_dump(usage)


def _accumulate_usage(total: dict[str, int | float], usage: dict[str, Any]) -> None:
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            total[name] = total.get(name, 0) + value
    cost = usage.get("cost")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        total["cost"] = float(total.get("cost", 0.0)) + float(cost)


def _trajectory_progress(path: Path) -> dict[str, Any]:
    progress: dict[str, Any] = {
        "model_requests": 0,
        "provider_attempts": 0,
        "provider_error_count": 0,
        "token_usage": {},
        "tool_counts": {},
        "shell_effect_counts": {},
        "replay_status_counts": {},
        "scheduled_observation_counts": {},
        "verifier_handoff_counts": {},
    }
    if not path.is_file():
        return progress
    usage_total: dict[str, int | float] = progress["token_usage"]
    tool_counts: dict[str, int] = progress["tool_counts"]
    shell_effect_counts: dict[str, int] = progress["shell_effect_counts"]
    replay_counts: dict[str, int] = progress["replay_status_counts"]
    scheduled_counts: dict[str, int] = progress["scheduled_observation_counts"]
    handoff_counts: dict[str, int] = progress["verifier_handoff_counts"]
    for event in read_jsonl(path):
        request_index = event.get("request_index")
        if isinstance(request_index, int) and not isinstance(request_index, bool):
            progress["model_requests"] = max(progress["model_requests"], request_index)
        event_name = event.get("event")
        if event_name in {"provider_response", "provider_error"}:
            progress["provider_attempts"] += 1
        if event_name == "provider_error":
            progress["provider_error_count"] += 1
        elif event_name == "provider_response":
            response = event.get("response")
            usage = response.get("usage") if isinstance(response, dict) else None
            if isinstance(usage, dict):
                _accumulate_usage(usage_total, usage)
        elif event_name == "tool_result":
            tool_name = event.get("tool_name")
            if isinstance(tool_name, str):
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
            result = event.get("result")
            declared_effect = (
                result.get("declared_effect") if isinstance(result, dict) else None
            )
            if tool_name == "envbench_shell" and isinstance(declared_effect, str):
                shell_effect_counts[declared_effect] = (
                    shell_effect_counts.get(declared_effect, 0) + 1
                )
            atomic_submission = (
                result.get("atomic_submission") if isinstance(result, dict) else None
            )
            if tool_name == "submit_and_replay" or (
                tool_name == "submit_bootstrap"
                and isinstance(atomic_submission, dict)
                and atomic_submission.get("replayed") is True
            ):
                status = result.get("status") if isinstance(result, dict) else None
                if isinstance(status, str):
                    replay_counts[status] = replay_counts.get(status, 0) + 1
            elif tool_name == "replay_current_program":
                status = result.get("status") if isinstance(result, dict) else None
                if isinstance(status, str):
                    replay_counts[status] = replay_counts.get(status, 0) + 1
            elif tool_name == "revise_program":
                status = result.get("status") if isinstance(result, dict) else None
                if isinstance(status, str):
                    replay_counts[status] = replay_counts.get(status, 0) + 1
            elif tool_name == "apply_environment_step":
                automatic = (
                    result.get("automatic_clean_replay")
                    if isinstance(result, dict)
                    else None
                )
                status = automatic.get("status") if isinstance(automatic, dict) else None
                if isinstance(status, str):
                    replay_counts[status] = replay_counts.get(status, 0) + 1
            elif tool_name == "envbench_shell" and declared_effect == "persist":
                automatic = (
                    result.get("automatic_clean_replay")
                    if isinstance(result, dict)
                    else None
                )
                status = automatic.get("status") if isinstance(automatic, dict) else None
                if isinstance(status, str):
                    replay_counts[status] = replay_counts.get(status, 0) + 1
        elif event_name == "compatibility_observation":
            trigger = event.get("trigger")
            if isinstance(trigger, str):
                scheduled_counts[trigger] = scheduled_counts.get(trigger, 0) + 1
        elif event_name == "verifier_handoff":
            transition = event.get("transition")
            if isinstance(transition, str):
                handoff_counts[transition] = handoff_counts.get(transition, 0) + 1
    return progress


def _retryable_provider_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    return type(exc).__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "EmptyProviderResponseError",
        "InternalServerError",
        "RateLimitError",
    }


def _request_contract(options: dict[str, Any]) -> dict[str, Any]:
    extra_body = options.get("extra_body")
    if not isinstance(extra_body, dict):
        extra_body = {}
    contract = {
        "model": options.get("model"),
        "seed": options.get("seed"),
        "seed_forwarded": "seed" in options,
        "max_tokens": options.get("max_tokens"),
        "tool_choice": options.get("tool_choice"),
        "reasoning": extra_body.get("reasoning"),
        "provider": extra_body.get("provider"),
    }
    thinking = extra_body.get("thinking")
    if thinking is not None:
        contract["thinking"] = thinking
        contract["reasoning_effort"] = options.get("reasoning_effort")
    return contract


def is_deepseek_direct_model(model: str) -> bool:
    return model == DEEPSEEK_DIRECT_V4_FLASH


def provider_connection(model: str) -> dict[str, str]:
    if is_deepseek_direct_model(model):
        return {
            "provider": "deepseek-direct",
            "base_url": DEEPSEEK_DIRECT_BASE_URL,
            "credential_variable": "DEEPSEEK_API_KEY",
        }
    return {
        "provider": "openrouter",
        "base_url": OPENROUTER_BASE_URL,
        "credential_variable": "OPENROUTER_API_KEY",
    }


class EmptyProviderResponseError(RuntimeError):
    """The provider returned a successful envelope without a completion choice."""


def _function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


class OpenRouterAgentRunner(CodexCliRunner):
    """One continuous OpenAI-compatible deployment session."""

    runner_name = "openrouter-continuous-agent"
    runner_version = "0.9.0"

    def __init__(
        self,
        *,
        harness_root: Path,
        source_cache_root: Path,
        image: str,
        timeout: int,
        command_timeout: int,
        container_create_timeout: int,
        git_fetch_timeout: int,
        max_iterations: int,
        model_request_timeout: int,
        model_max_retries: int,
        model_max_output_tokens: int,
        reasoning_effort: str,
        replay_mode: ReplayMode,
        public_goal_visible: bool = True,
        workspace_preconditions: tuple[WorkspacePrecondition, ...],
        goal_contract: ExecutableGoalContract,
        client_factory: ClientFactory | None = None,
    ) -> None:
        if replay_mode not in {
            "none",
            "atomic",
            "atomic-handoff",
            "soft",
            "incumbent",
            "current",
            "ledger",
            "scheduled",
            "operation-frontier",
            "handoff",
            "stateful",
            "incremental",
            "incremental-annotated",
            "incremental-editable",
            "incremental-transactional-editable",
        }:
            raise ValueError(
                "Replay mode must be none, atomic, atomic-handoff, soft, "
                "incumbent, current, ledger, scheduled, handoff, stateful, "
                "operation-frontier, incremental, incremental-annotated, "
                "incremental-editable, or incremental-transactional-editable"
            )
        if max_iterations <= 0:
            raise ValueError("Agent iterations must be positive")
        if model_max_retries < 0:
            raise ValueError("Provider retries cannot be negative")
        if not public_goal_visible and replay_mode != "none":
            raise ValueError("Clean replay requires a model-visible public goal")
        super().__init__(
            codex_executable=Path("/nonexistent/openrouter-agent"),
            harness_root=harness_root,
            image=image,
            timeout=timeout,
            command_timeout=command_timeout,
            container_create_timeout=container_create_timeout,
            git_fetch_timeout=git_fetch_timeout,
            reasoning_effort=reasoning_effort,
            workspace_preconditions=workspace_preconditions,
            goal_contract=goal_contract,
        )
        self.max_iterations = max_iterations
        self.source_cache_root = source_cache_root.resolve()
        self.model_request_timeout = model_request_timeout
        self.model_max_retries = model_max_retries
        self.model_max_output_tokens = model_max_output_tokens
        self.replay_mode = replay_mode
        self.public_goal_visible = public_goal_visible
        self.client_factory = client_factory
        self.validator = MinimalIntegrityCandidateValidator()

    def _acquire_repository(self, case: Case, destination: Path) -> dict[str, Any]:
        return ExactRevisionSourceCache(
            self.source_cache_root,
            self.git_fetch_timeout,
        ).acquire(
            repository=case.repository,
            revision=case.revision,
            destination=destination,
        )

    @property
    def agent_interface(self) -> str:
        if not self.public_goal_visible:
            return "free-repository-feedback-search-v1"
        if self.atomic_handoff_enabled:
            return (
                "free-feedback-search+scheduled-trusted-goal-observation+"
                "verified-atomic-handoff-v1"
            )
        if self.atomic_submission_enabled:
            return "free-feedback-search+atomic-submit-clean-replay-v1"
        if self.verifier_handoff_enabled:
            return (
                "free-feedback-search+scheduled-trusted-goal-observation+"
                "verifier-triggered-programization+soft-clean-replay-v1"
            )
        if self.stateful_replay_constraints_enabled:
            return (
                "free-feedback-search+scheduled-compatibility-observation+"
                "stateful-replay-obligation-ledger+soft-clean-replay-v1"
            )
        if self.annotated_incremental_program_enabled:
            if self.editable_incremental_program_enabled:
                if self.transactional_editable_incremental_program_enabled:
                    return (
                        "free-feedback-search+transactional-editable-incremental-"
                        "executable-program+target-replay-v4"
                    )
                return (
                    "free-feedback-search+editable-incremental-executable-program+"
                    "target-replay-v3"
                )
            return (
                "free-feedback-search+annotated-incremental-executable-program+"
                "target-replay-v2"
            )
        if self.incremental_program_enabled:
            return "free-feedback-search+incremental-executable-program+target-replay-v1"
        if self.current_goal_enabled:
            return (
                "free-feedback-search+current-goal-constraints+"
                "soft-clean-replay-v1"
            )
        if self.scheduled_observation_enabled:
            return (
                "free-feedback-search+scheduled-compatibility-observation+"
                "delta-evidence-frontier+soft-clean-replay-v1"
            )
        if self.operation_frontier_enabled:
            return (
                "free-feedback-search+operation-triggered-compatibility-frontier+"
                "soft-clean-replay-v1"
            )
        if self.compatibility_ledger_enabled:
            return "free-feedback-search+compatibility-delta-ledger+soft-clean-replay-v1"
        if self.replay_mode == "incumbent":
            return "free-feedback-search+goal-triggered-certified-incumbent-v1"
        if self.replay_mode == "soft":
            return "free-feedback-search+soft-clean-replay-v1"
        return "free-feedback-search-v1"

    @property
    def replay_enabled(self) -> bool:
        return self.replay_mode in {
            "atomic",
            "atomic-handoff",
            "soft",
            "incumbent",
            "current",
            "ledger",
            "scheduled",
            "operation-frontier",
            "handoff",
            "stateful",
            "incremental",
            "incremental-annotated",
            "incremental-editable",
            "incremental-transactional-editable",
        }

    @property
    def atomic_submission_enabled(self) -> bool:
        return self.replay_mode in {"atomic", "atomic-handoff"}

    @property
    def atomic_handoff_enabled(self) -> bool:
        return self.replay_mode == "atomic-handoff"

    @property
    def incumbent_enabled(self) -> bool:
        return self.replay_mode == "incumbent"

    @property
    def compatibility_ledger_enabled(self) -> bool:
        return self.replay_mode == "ledger"

    @property
    def current_goal_enabled(self) -> bool:
        return self.replay_mode == "current"

    @property
    def scheduled_observation_enabled(self) -> bool:
        return self.replay_mode in {
            "atomic-handoff",
            "scheduled",
            "handoff",
            "stateful",
        }

    @property
    def operation_frontier_enabled(self) -> bool:
        return self.replay_mode == "operation-frontier"

    @property
    def verifier_handoff_enabled(self) -> bool:
        return self.replay_mode in {"atomic-handoff", "handoff"}

    @property
    def stateful_replay_constraints_enabled(self) -> bool:
        return self.replay_mode == "stateful"

    @property
    def incremental_program_enabled(self) -> bool:
        return self.replay_mode in {
            "incremental",
            "incremental-annotated",
            "incremental-editable",
            "incremental-transactional-editable",
        }

    @property
    def annotated_incremental_program_enabled(self) -> bool:
        return self.replay_mode in {
            "incremental-annotated",
            "incremental-editable",
            "incremental-transactional-editable",
        }

    @property
    def editable_incremental_program_enabled(self) -> bool:
        return self.replay_mode in {
            "incremental-editable",
            "incremental-transactional-editable",
        }

    @property
    def transactional_editable_incremental_program_enabled(self) -> bool:
        return self.replay_mode == "incremental-transactional-editable"

    @property
    def compatibility_observation_enabled(self) -> bool:
        return (
            self.compatibility_ledger_enabled
            or self.scheduled_observation_enabled
            or self.operation_frontier_enabled
        )

    @property
    def mechanism_primitives(self) -> list[str]:
        if not self.public_goal_visible:
            return ["F", "minimal-H"]
        if self.atomic_handoff_enabled:
            return [
                "F",
                "scheduled-O",
                "verified-atomic-handoff",
                "soft-C",
                "R",
                "minimal-H",
            ]
        if self.atomic_submission_enabled:
            return ["F", "public-O", "soft-C", "R", "atomic-delivery", "minimal-H"]
        if self.verifier_handoff_enabled:
            return [
                "F",
                "scheduled-O",
                "verifier-triggered-programization",
                "R",
                "minimal-H",
            ]
        if self.stateful_replay_constraints_enabled:
            return [
                "F",
                "scheduled-O",
                "replay-obligation-ledger",
                "R",
                "minimal-H",
            ]
        if self.annotated_incremental_program_enabled:
            if self.editable_incremental_program_enabled:
                editable_state = (
                    "operation-annotated-transactional-editable-program-state"
                    if self.transactional_editable_incremental_program_enabled
                    else "operation-annotated-editable-program-state"
                )
                return [
                    "F",
                    editable_state,
                    "operation-triggered-O",
                    "soft-C",
                    "R",
                    "minimal-H",
                ]
            return [
                "F",
                "operation-annotated-program-state",
                "operation-triggered-O",
                "soft-C",
                "R",
                "minimal-H",
            ]
        if self.incremental_program_enabled:
            return [
                "F",
                "operation-linked-program-state",
                "operation-triggered-O",
                "soft-C",
                "R",
                "minimal-H",
            ]
        if self.current_goal_enabled:
            return ["F", "current-O", "current-C", "R", "minimal-H"]
        if self.scheduled_observation_enabled:
            return ["F", "scheduled-O", "delta-C", "R", "minimal-H"]
        if self.operation_frontier_enabled:
            return [
                "F",
                "operation-triggered-O",
                "compatibility-frontier-C",
                "R",
                "minimal-H",
            ]
        if self.compatibility_ledger_enabled:
            return ["F", "compatibility-delta-ledger", "S", "R", "minimal-H"]
        if self.incumbent_enabled:
            return ["F", "S", "R", "certified-incumbent", "minimal-H"]
        if self.replay_mode == "soft":
            return ["F", "public-O", "soft-C", "R", "minimal-H"]
        return ["F", "public-O", "minimal-H"]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _provider_policy(self) -> dict[str, Any]:
        policy: dict[str, Any] = {
            "require_parameters": True,
            "allow_fallbacks": False,
        }
        order = [
            item.strip()
            for item in os.environ.get("OPENROUTER_PROVIDER_ORDER", "").split(",")
            if item.strip()
        ]
        if order:
            policy["order"] = order
        return policy

    def _create_container_with_package_cache(
        self,
        workspace: Path,
        image_digest: str,
        cache_root: Path,
    ) -> str:
        cache_root = _prepare_episode_package_cache(cache_root)
        docker = os.environ.get("DOCKER_EXECUTABLE", "docker")
        container_id = self._checked(
            [
                docker,
                "create",
                "--init",
                "--entrypoint",
                "/bin/bash",
                "--mount",
                f"type=bind,src={workspace},dst=/data/project",
                "--mount",
                f"type=bind,src={cache_root.resolve()},dst=/root/.cache",
                "--workdir",
                "/data/project",
                image_digest,
                "-lc",
                "while true; do sleep 1000; done",
            ],
            timeout=self.container_create_timeout,
        )
        try:
            self._checked(
                [docker, "start", container_id],
                timeout=self.container_create_timeout,
            )
            self._checked(
                [
                    docker,
                    "exec",
                    "--user",
                    "0:0",
                    container_id,
                    "chown",
                    "0:0",
                    "/root/.cache",
                ],
                timeout=self.container_create_timeout,
            )
        except Exception:
            subprocess.run(
                [docker, "rm", "-f", container_id],
                capture_output=True,
                text=True,
                check=False,
            )
            raise
        return container_id

    def _create_replay_provider(
        self,
        workspace: Path,
        replay_root: Path,
        image_digest: str,
        case: Case,
    ) -> DockerFreshEnvironmentProvider:
        return DockerFreshEnvironmentProvider(
            source_repository=workspace,
            worktrees_root=replay_root / "worktrees",
            repository=case.repository,
            revision=case.revision,
            image=image_digest,
            workspace_preconditions=self.workspace_preconditions,
            create_timeout=self.container_create_timeout,
        )

    def request_options(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        seed: int | None = None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": self._tools(),
            "tool_choice": "auto",
            "max_tokens": self.model_max_output_tokens,
        }
        if is_deepseek_direct_model(model):
            options["reasoning_effort"] = self.reasoning_effort
            options["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            options["extra_body"] = {
                "reasoning": {"effort": self.reasoning_effort},
                "provider": self._provider_policy(),
            }
        if seed is not None and not is_deepseek_direct_model(model):
            options["seed"] = seed
        return options

    def _tools(self) -> list[dict[str, Any]]:
        if self.annotated_incremental_program_enabled:
            shell_description = (
                "Execute arbitrary Bash in the persistent construction container. "
                "Declare effect=inspect for observation or diagnosis whose effects do "
                "not belong in the final environment. Declare effect=persist for a "
                "reproducible environment change; a successful persist command is "
                "appended exactly to the deployment program and triggers goal checking."
            )
        elif self.operation_frontier_enabled:
            shell_description = (
                "Execute arbitrary Bash in the persistent construction container. "
                "Declare effect=inspect for diagnosis. Declare effect=change for an "
                "operation intended to alter environment compatibility; after every "
                "change, including a nonzero exit, the harness executes the complete "
                "public goal and returns a bounded compatibility delta with exact "
                "counts and explicit truncation metadata. Commands are never copied "
                "into the final deployment program."
            )
        elif self.incremental_program_enabled:
            shell_description = (
                "Inspect or diagnose the persistent construction container. Commands used "
                "here are not added to the deployment program; use apply_environment_step "
                "for every operation whose effect the final environment needs."
            )
        else:
            shell_description = (
                "Execute Bash in the persistent construction container. Shell state, "
                "files, installed packages, and working directory persist."
            )
        shell_properties: dict[str, Any] = {
            "command": {"type": "string"},
            "timeout_seconds": {"type": "integer", "minimum": 1},
        }
        shell_required = ["command"]
        if self.annotated_incremental_program_enabled:
            shell_properties["effect"] = {
                "type": "string",
                "enum": ["inspect", "persist"],
            }
            shell_required.append("effect")
        elif self.operation_frontier_enabled:
            shell_properties["effect"] = {
                "type": "string",
                "enum": ["inspect", "change"],
            }
            shell_required.append("effect")
        tools = [
            _function_tool(
                "envbench_shell",
                shell_description,
                {
                    "type": "object",
                    "properties": shell_properties,
                    "required": shell_required,
                    "additionalProperties": False,
                },
            )
        ]
        if self.incremental_program_enabled and not self.annotated_incremental_program_enabled:
            tools.append(
                _function_tool(
                    "apply_environment_step",
                    (
                        "Execute one model-selected environment operation and, only if it "
                        "succeeds, append that exact command to the current replayable "
                        "deployment program. The harness then observes the complete public "
                        "goal and automatically clean-replays the current program on Pass."
                    ),
                    {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "minLength": 1},
                            "timeout_seconds": {"type": "integer", "minimum": 1},
                        },
                        "required": ["command"],
                        "additionalProperties": False,
                    },
                )
            )
        if self.editable_incremental_program_enabled:
            if self.transactional_editable_incremental_program_enabled:
                revision_description = (
                    "Atomically revise the current replayable deployment program "
                    "without changing the active construction environment. Every "
                    "step_index is interpreted against the same pre-edit indexed "
                    "program. Use an empty replacement_command to delete a step. "
                    "The harness applies the complete batch and clean-replays the "
                    "resulting program once."
                )
                revision_parameters = {
                    "type": "object",
                    "properties": {
                        "edits": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step_index": {
                                        "type": "integer",
                                        "minimum": 1,
                                    },
                                    "replacement_command": {"type": "string"},
                                },
                                "required": [
                                    "step_index",
                                    "replacement_command",
                                ],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["edits"],
                    "additionalProperties": False,
                }
            else:
                revision_description = (
                    "Revise the current replayable deployment program without "
                    "changing the active construction environment. Replace one "
                    "one-based indexed step with replacement_command, or delete "
                    "that step by passing an empty string. Every edit immediately "
                    "clean-replays the complete revised program."
                )
                revision_parameters = {
                    "type": "object",
                    "properties": {
                        "step_index": {"type": "integer", "minimum": 1},
                        "replacement_command": {"type": "string"},
                    },
                    "required": ["step_index", "replacement_command"],
                    "additionalProperties": False,
                }
            tools.append(
                _function_tool(
                    "revise_program",
                    revision_description,
                    revision_parameters,
                )
            )
        if self.incremental_program_enabled:
            accumulated_by = (
                "successful effect=persist shell calls"
                if self.annotated_incremental_program_enabled
                else "successful apply_environment_step calls"
            )
            tools.append(
                _function_tool(
                    "replay_current_program",
                    (
                        "Clean-replay the deployment program accumulated by "
                        f"{accumulated_by}. A Pass finishes the episode; a Fail returns "
                        "executable evidence to this same session."
                    ),
                    {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                )
            )
        elif self.replay_enabled and not self.atomic_submission_enabled:
            tools.append(
                _function_tool(
                    "submit_and_replay",
                    (
                        "Run a complete bootstrap program in a new clean checkout and "
                        "container, execute the trusted public goal, destroy that replay "
                        "environment, and return advisory failure constraints plus raw evidence."
                    ),
                    {
                        "type": "object",
                        "properties": {"program": {"type": "string", "minLength": 1}},
                        "required": ["program"],
                        "additionalProperties": False,
                    },
                )
            )
        if self.compatibility_ledger_enabled:
            tools.insert(
                1,
                _function_tool(
                    "check_compatibility",
                    (
                        "Execute the trusted public goal in the current environment and "
                        "return a machine-maintained delta from the previous observation "
                        "plus the nondominated compatibility evidence frontier. This is "
                        "advisory and never blocks shell operations."
                    ),
                    {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                ),
            )
        if self.current_goal_enabled:
            tools.insert(
                1,
                _function_tool(
                    "check_current_goal",
                    (
                        "Execute the exact trusted public goal in the current "
                        "construction environment and return only the currently "
                        "active constraints. It retains no history or checkpoint "
                        "and never blocks shell operations."
                    ),
                    {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                ),
            )
        submit_description = (
            "Atomically submit the complete bootstrap program: validate it, replay it "
            "from a fresh checkout and container, return executable failure evidence to "
            "this same session, or finish when the clean replay passes."
            if self.atomic_submission_enabled
            else "Submit the final complete bootstrap program and a short summary."
        )
        if not self.incremental_program_enabled:
            tools.append(
                _function_tool(
                    "submit_bootstrap",
                    submit_description,
                    {
                        "type": "object",
                        "properties": {
                            "program": {"type": "string", "minLength": 1},
                            "summary": {"type": "string"},
                        },
                        "required": ["program", "summary"],
                        "additionalProperties": False,
                    },
                )
            )
        return tools

    def _prompt(self, case: Case, goal_contract: ExecutableGoalContract | None = None) -> str:
        contract = goal_contract or self.goal_contract
        if self.annotated_incremental_program_enabled:
            shell_instruction = (
                "Use the single `envbench_shell` for all work and declare each call's "
                "effect as `inspect` or `persist` as described below."
            )
        elif self.operation_frontier_enabled:
            shell_instruction = (
                "Use the single `envbench_shell` for all work and declare each call's "
                "effect as `inspect` or `change` as described below."
            )
        elif self.incremental_program_enabled:
            shell_instruction = (
                "Use `envbench_shell` for repository inspection and diagnosis. Use the "
                "operation-linked tool described below for installation and every other "
                "persistent environment change."
            )
        else:
            shell_instruction = (
                "Use `envbench_shell` for repository inspection, installation, and "
                "ordinary execution feedback."
            )
        prompt = f"""\
Set up the Python development environment for `{case.repository}` at exact revision
`{case.revision}`. Work as a strong general-purpose coding agent in one continuous
session. {shell_instruction} The construction shell is persistent and starts at
`/data/project` in the benchmark image.

Infer the intended Python version, dependency manager, project install, and
development dependencies from the repository. Diagnose failures through execution.
Do not use the official evaluator or any post-episode result. Do not modify tracked
source, tests, declarations, lockfiles, type-checker configuration, or
benchmark-owned state. Do not use sudo or interactive commands.
"""
        if self.public_goal_visible:
            prompt += f"""\

The public executable goal below is the only online success signal. It is not the
official evaluator. You may execute an equivalent command during construction.

Goal ID: {contract.contract_id}
Goal description: {contract.description}
Goal schema: {contract.report_schema}
Goal SHA-256: {contract.sha256}

<trusted_goal_program>
{contract.program}
</trusted_goal_program>
"""
        else:
            prompt += """\

The benchmark's public scoring goal and terminal Official evaluator are unavailable
during construction. Use repository-owned declarations, documentation, tests, and
ordinary execution feedback to infer a complete development environment.
"""
        if self.incremental_program_enabled:
            prompt += """\

The recorded deployment program is replayed from a fresh checkout with the repository
root as its starting working directory. That checkout's absolute path may differ from
`/data/project`. Derive repository paths from the starting working directory and do not
hardcode the construction path in persistent commands.
"""
        if self.annotated_incremental_program_enabled:
            prompt += """\

Use the single `envbench_shell` action channel for every command. Set `effect=inspect`
when the command only observes or diagnoses and its effects are not required by the final
environment. Set `effect=persist` when the command makes a reproducible change that the
final environment needs. A successful persist command is appended exactly to the current
deployment program; a failed persist command is not appended. After each append, the
harness runs the trusted public goal. Goal Pass immediately clean-replays the accumulated
program from the target initial state. Replay failure returns here for another persist
repair; replay success finishes the episode.

Do not reconstruct a bootstrap program from memory and do not optimize deployment
completeness or cost after the public goal passes. The command remains arbitrary Bash;
the effect annotation describes intent but does not restrict which command you may run.
You may call `replay_current_program` when an explicit target-state check is useful.
"""
            if self.editable_incremental_program_enabled:
                if self.transactional_editable_incremental_program_enabled:
                    prompt += """

The harness also exposes the current program as one-based indexed steps. When replay
evidence shows that recorded steps are wrong, call `revise_program` once with every
intended replacement or deletion. All indices refer to the same program shown before
the call; an empty replacement deletes that step. The batch edits only the candidate
program, not the active construction environment, and the harness clean-replays the
complete result once. Historical execution evidence remains available even though the
current plan may change.
"""
                else:
                    prompt += """

The harness also exposes the current program as one-based indexed steps. When replay
evidence shows that an earlier recorded step is wrong, use `revise_program` to replace
that step or delete it with an empty replacement. This edits only the candidate program,
not the active construction environment, and immediately clean-replays the revised whole.
Historical execution evidence remains available even though the current plan may change.
"""
            return prompt
        if self.incremental_program_enabled:
            prompt += """\

Use `envbench_shell` only for inspection and diagnosis. Use
`apply_environment_step` for every successful state change that the final deployment
needs. The harness executes the command in the active environment and appends the exact
successful command to the current deployment program. After each appended step it runs
the trusted public goal. If the goal passes, the harness immediately replays the current
program from the target initial state. Replay failure evidence returns here for another
model-selected repair step; replay success finishes the episode.

Do not reconstruct a bootstrap program from memory and do not optimize deployment
completeness or cost after the public goal passes. The accumulated program, Official
success, deployment completeness, and resource use are evaluated separately. You may
call `replay_current_program` when an explicit target-state check is useful.
"""
            return prompt
        prompt += f"""\

	Finish by calling `submit_bootstrap` with one self-contained Bash program that can
	be sourced from a fresh checkout in the same image. Keep only reproducible setup
	commands; omit inspection, diagnostics, tests, and failed attempts. The program
	must leave its selected Python environment active. In every fresh environment,
	the current working directory is the repository root, but its absolute path may
	differ from `/data/project`. Derive repository paths from the starting working
	directory; do not hardcode the construction path in the submitted program. Once
	the public goal is satisfied and the complete program is ready, submit it promptly.

<candidate_contract>
{self.validator.prompt_contract}
</candidate_contract>
"""
        if self.atomic_submission_enabled:
            prompt += """\

`submit_bootstrap` is the single atomic delivery action. Every call validates the
complete program and clean-replays that exact program from the target's initial state.
A Pass finishes the episode with that program. A Fail returns normalized executable
evidence to this same session so you can repair the whole program and submit again.
There is no separate replay action and no replay state is retained.
"""
        elif self.replay_mode in {
            "soft",
            "current",
            "ledger",
            "scheduled",
            "operation-frontier",
            "handoff",
            "stateful",
        }:
            prompt += """\

Before final submission, call `submit_and_replay` with the complete program. It
creates no checkpoint, does not reuse the construction package cache, and retains
no construction environment state. Treat its normalized
constraint as advisory evidence, inspect the accompanying raw evidence, repair the
whole program in this same session, and repeat as needed. `submit_bootstrap` accepts
only the exact hash of a program that passed a clean replay.
"""
        elif self.incumbent_enabled:
            prompt += """\

As soon as execution evidence indicates that the whole public goal is feasible,
compile the current environment into one complete bootstrap program and call
`submit_and_replay`. A replay-passed program becomes the harness-managed incumbent:
it remains available if the provider or a safety cap later stops the session. You
may continue in this same session only when there is a material runtime or
reproducibility improvement to make. Replace the incumbent only by clean-replaying
the improved complete program. `submit_bootstrap` accepts only a certified hash. The
incumbent stores the program and certificate, never a container checkpoint.
"""
        if self.current_goal_enabled:
            prompt += """\

Call `check_current_goal` after a material setup step or whenever you are unsure
whether the active environment satisfies the complete public goal. It reports only
the constraints active now: it has no history, frontier, checkpoint, automatic
cadence, package policy, or command restrictions. When it reports
`candidate_ready=true`, promptly compile the operations that produced the current
state into one complete bootstrap program and call `submit_and_replay`. If clean
replay fails, use that executable evidence to repair the program in this same
session.
"""
        elif self.compatibility_ledger_enabled:
            prompt += """\

Use `check_compatibility` after a material batch of environment changes and before
abandoning a near-feasible approach. It executes the complete public goal in the
current shell context, reports resolved and introduced obligations, and remembers
nondominated observations. A regression is evidence, not a forbidden state: continue
any exploration you judge useful. The ledger never selects packages, blocks commands,
or restores environments. When it reports `candidate_ready`, compile the current work
	into a complete program and call `submit_and_replay` promptly.
"""
        elif self.scheduled_observation_enabled:
            prompt += """\

The harness automatically executes the complete public goal before your first
request, after every 16 completed shell operations, and before clean replay when
the construction state changed after the latest observation. Scheduled feedback
reports complete identity-bound obligations and their delta in this same session.
It is advisory evidence: temporary regression remains allowed, and the harness
never selects packages, blocks commands, or restores an environment.
"""
        elif self.operation_frontier_enabled:
            prompt += """\

Set `effect=inspect` for diagnosis that should not trigger the public goal. Set
`effect=change` for every operation intended to change environment compatibility.
After each change, even when its shell exit code is nonzero, the harness executes
the complete public goal. The machine trajectory retains complete evidence; the model
receives exact counts plus a bounded identity list for current, resolved, and introduced
obligations, with explicit truncation metadata. You may inspect the raw goal when more
detail is useful. This compatibility frontier is advisory: it does not select packages,
block commands, restore an environment, or copy commands into the candidate program.

Use the frontier to distinguish an operation's verified effect from its exit status.
When the active environment is ready, synthesize one self-contained, path-portable
bootstrap program from the verified state and call `submit_and_replay`. Repair replay
failures in this same session, then submit the exact replay-certified program.
"""
        return prompt

    def _client(self, model: str) -> Any:
        connection = provider_connection(model)
        credential_variable = connection["credential_variable"]
        api_key = os.environ.get(credential_variable)
        if not api_key:
            raise RuntimeError(f"{credential_variable} is not set")
        factory = self.client_factory
        if factory is None:
            from openai import OpenAI

            factory = OpenAI
        return factory(
            api_key=api_key,
            base_url=connection["base_url"],
            timeout=self.model_request_timeout,
            max_retries=0,
        )

    def _append_event(self, path: Path, value: dict[str, Any]) -> None:
        encoded = self._redact(json.dumps(value, ensure_ascii=True, sort_keys=True))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _provider_request(
        self,
        client: Any,
        options: dict[str, Any],
        trajectory_path: Path,
        request_index: int,
    ) -> Any:
        last_error: Exception | None = None
        max_attempts = self.model_max_retries + 1
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.chat.completions.create(**options)
                choices = getattr(response, "choices", None)
                if not isinstance(choices, list) or not choices:
                    raise EmptyProviderResponseError(
                        "Provider response contains no choices"
                    )
                self._append_event(
                    trajectory_path,
                    {
                        "schema": "envsolve-openrouter-event-v1",
                        "event": "provider_response",
                        "request_index": request_index,
                        "attempt": attempt,
                        "request_contract": _request_contract(options),
                        "response": _model_dump(response),
                    },
                )
                return response
            except Exception as exc:
                last_error = exc
                retryable = _retryable_provider_error(exc)
                should_retry = attempt < max_attempts and retryable
                delay = (
                    _PROVIDER_RETRY_DELAYS_SECONDS[
                        min(attempt - 1, len(_PROVIDER_RETRY_DELAYS_SECONDS) - 1)
                    ]
                    if should_retry
                    else None
                )
                self._append_event(
                    trajectory_path,
                    {
                        "schema": "envsolve-openrouter-event-v1",
                        "event": "provider_error",
                        "request_index": request_index,
                        "attempt": attempt,
                        "retryable": retryable,
                        "next_retry_delay_seconds": delay,
                        "request_contract": _request_contract(options),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                if should_retry and delay is not None:
                    time.sleep(delay)
                    continue
                raise
        raise RuntimeError(f"Provider request failed: {last_error}")

    def _submit(
        self,
        arguments: dict[str, Any],
        replay_service: CleanReplayService | None,
    ) -> tuple[dict[str, Any], dict[str, str] | None]:
        program = arguments.get("program")
        summary = arguments.get("summary")
        if not isinstance(program, str) or not isinstance(summary, str):
            return {"accepted": False, "reason": "program and summary must be strings"}, None
        canonical = canonical_script(program)
        if not canonical:
            return {"accepted": False, "reason": "program must not be empty"}, None
        validation = self.validator.validate(
            DeploymentCandidate(
                candidate_id="openrouter-final-submission",
                script=canonical,
                rationale="continuous Agent final submission",
            )
        )
        if not validation.accepted:
            return {
                "accepted": False,
                "reason": validation.reason,
                "policy_id": validation.policy_id,
                "details": validation.details,
            }, None
        canonical = canonical_script(validation.normalized_script or canonical)
        digest = script_sha256(canonical)
        if replay_service is not None and digest not in {
            item.get("program_sha256") for item in replay_service.certified_programs
        }:
            return {
                "accepted": False,
                "reason": "final program hash has not passed clean replay",
                "program_sha256": digest,
            }, None
        submission = {"program": canonical, "summary": summary, "program_sha256": digest}
        return {"accepted": True, "program_sha256": digest}, submission

    def _atomic_submit(
        self,
        arguments: dict[str, Any],
        replay_service: CleanReplayService,
    ) -> tuple[dict[str, Any], dict[str, str] | None, str | None]:
        validation_payload, proposed = self._submit(arguments, None)
        if proposed is None:
            return {
                **validation_payload,
                "atomic_submission": {"accepted": False, "replayed": False},
            }, None, None

        raw_replay = replay_service.submit(proposed["program"])
        status = str(raw_replay.get("status", "unknown"))
        payload = {
            **normalize_replay_feedback(raw_replay),
            "atomic_submission": {
                "accepted": False,
                "replayed": True,
                "program_sha256": proposed["program_sha256"],
            },
        }
        if status != "pass":
            return payload, None, status

        acceptance_payload, submission = self._submit(proposed, replay_service)
        if submission is None:
            return {
                **payload,
                "atomic_submission": {
                    **payload["atomic_submission"],
                    "reason": acceptance_payload.get("reason"),
                },
            }, None, status
        return {
            **payload,
            "atomic_submission": {
                "accepted": True,
                "replayed": True,
                "program_sha256": submission["program_sha256"],
            },
        }, submission, status

    def _agent_loop(
        self,
        *,
        client: Any,
        model: str,
        prompt: str,
        terminal_server: ContainerMcpServer,
        replay_service: CleanReplayService | None,
        trajectory_path: Path,
        incremental_program: IncrementalProgram | None = None,
        current_goal_service: CurrentGoalService | None = None,
        compatibility_service: CompatibilityLedgerService | None = None,
        scheduled_observer: ScheduledCompatibilityObserver | None = None,
        seed: int | None = None,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        if self.scheduled_observation_enabled != (scheduled_observer is not None):
            raise ValueError(
                "Scheduled replay mode and scheduled observer must be configured together"
            )
        if self.operation_frontier_enabled and compatibility_service is None:
            raise ValueError(
                "Operation-frontier replay mode requires a compatibility service"
            )
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        usage_total: dict[str, int | float] = {}
        tool_counts = {
            "envbench_shell": 0,
            "apply_environment_step": 0,
            "replay_current_program": 0,
            "revise_program": 0,
            "check_current_goal": 0,
            "check_compatibility": 0,
            "submit_and_replay": 0,
            "submit_bootstrap": 0,
        }
        replay_status_counts: dict[str, int] = {}
        shell_effect_counts = (
            {"inspect": 0, "change": 0, "invalid": 0}
            if self.operation_frontier_enabled
            else {"inspect": 0, "persist": 0, "invalid": 0}
        )
        incumbent: dict[str, str] | None = None
        incumbent_updates: list[dict[str, Any]] = []
        first_certification_request: int | None = None
        handoff_pending = False
        handoff_forced_requests = 0
        handoff_events: list[dict[str, Any]] = []
        replay_obligation_ledger = (
            ReplayObligationLedger()
            if self.stateful_replay_constraints_enabled
            else None
        )
        started = time.monotonic()

        def record_scheduled_observation(
            observation: dict[str, Any],
            request_index: int,
            parent_tool_call_id: str | None = None,
        ) -> None:
            event = {
                "schema": "envsolve-openrouter-event-v1",
                "event": "compatibility_observation",
                "request_index": request_index,
                "observation_number": observation["observation_number"],
                "trigger": observation["trigger"],
                "shell_operations_completed": observation[
                    "shell_operations_completed"
                ],
                "feedback_delivery": observation["feedback_delivery"],
                "result": observation["result"],
            }
            if parent_tool_call_id is not None:
                event["parent_tool_call_id"] = parent_tool_call_id
            self._append_event(trajectory_path, event)

        def schedule_verifier_handoff(
            observation: dict[str, Any],
            request_index: int,
        ) -> bool:
            nonlocal handoff_pending
            if not self.verifier_handoff_enabled or handoff_pending:
                return False
            result = observation.get("result")
            if not isinstance(result, dict):
                return False
            candidate_ready = (
                result.get("ok") is True
                and result.get("finding_set_complete") is True
                and result.get("goal_status") == "pass"
                and result.get("candidate_ready") is True
            )
            if not candidate_ready:
                return False
            handoff_pending = True
            handoff_event = {
                "transition": "candidate-ready",
                "request_index": request_index,
                "observation_number": observation.get("observation_number"),
                "observation_trigger": observation.get("trigger"),
                "shell_operations_completed": observation.get(
                    "shell_operations_completed"
                ),
            }
            handoff_events.append(handoff_event)
            self._append_event(
                trajectory_path,
                {
                    "schema": "envsolve-openrouter-event-v1",
                    "event": "verifier_handoff",
                    **handoff_event,
                },
            )
            return True

        def handoff_message(observation: dict[str, Any]) -> dict[str, str]:
            delivery_action = (
                "call submit_bootstrap now; that single action will atomically "
                "clean-replay the program"
                if self.atomic_handoff_enabled
                else "call submit_and_replay now"
            )
            return {
                "role": "user",
                "content": (
                    "The harness trusted verifier has reported a complete public-goal "
                    "Pass (candidate_ready=true) in the active construction state. "
                    "Before any optional completeness work, compile the reproducible "
                    "operations that produced this state into one cumulative bootstrap "
                    f"program and {delivery_action}. If replay fails, its exact "
                    "evidence will return to this same session for free repair."
                ),
            }

        if scheduled_observer is not None:
            initial_observation = scheduled_observer.observe_initial()
            record_scheduled_observation(initial_observation, 0)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Harness-scheduled advisory compatibility observation before "
                        "the first model request:\n"
                        + json.dumps(
                            model_visible_scheduled_observation(initial_observation),
                            ensure_ascii=True,
                            sort_keys=True,
                        )
                    ),
                }
            )
            if schedule_verifier_handoff(initial_observation, 0):
                messages.append(handoff_message(initial_observation))

        if self.operation_frontier_enabled:
            assert compatibility_service is not None
            initial_result = compatibility_service.check(
                "operation-frontier-initial"
            )
            initial_observation = {
                "schema": "envsolve-operation-frontier-observation-v1",
                "trigger": "initial-baseline",
                "advisory_only": True,
                "result": initial_result,
            }
            projected_initial = model_visible_scheduled_observation(
                initial_observation
            )
            self._append_event(
                trajectory_path,
                {
                    "schema": "envsolve-openrouter-event-v1",
                    "event": "operation_frontier_observation",
                    "request_index": 0,
                    "trigger": "initial-baseline",
                    "result": initial_result,
                },
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Harness advisory compatibility baseline before the first "
                        "model request:\n"
                        + json.dumps(
                            projected_initial,
                            ensure_ascii=True,
                            sort_keys=True,
                        )
                    ),
                }
            )

        def execute_shell(
            call_id: str,
            arguments: dict[str, Any],
        ) -> dict[str, Any]:
            shell_arguments = {
                key: arguments[key]
                for key in ("command", "timeout_seconds")
                if key in arguments
            }
            request = {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {
                    "name": "envbench_shell",
                    "arguments": shell_arguments,
                },
            }
            response_value = terminal_server.handle(request)
            if response_value is None or "result" not in response_value:
                return {"infrastructure_error": response_value}
            return response_value["result"]["structuredContent"]

        def record_incremental_step(
            call_id: str,
            command: str,
            shell_result: dict[str, Any],
        ) -> tuple[dict[str, Any], dict[str, str] | None]:
            payload: dict[str, Any] = {
                "shell_result": shell_result,
                "program_updated": False,
            }
            successful = (
                shell_result.get("exit_code") == 0
                and shell_result.get("timed_out") is not True
                and shell_result.get("infrastructure_error") is None
            )
            if not successful:
                return payload, None
            if (
                incremental_program is None
                or current_goal_service is None
                or replay_service is None
            ):
                return {
                    **payload,
                    "infrastructure_error": "incremental services are unavailable",
                }, None

            step = incremental_program.append_successful(command, shell_result)
            current_goal = current_goal_service.check(
                f"{call_id}-automatic-goal",
                automatic=True,
            )
            payload.update(
                {
                    "program_updated": True,
                    "program_step": step,
                    "program_state": incremental_program.state(),
                    "current_goal": current_goal,
                }
            )
            if self.editable_incremental_program_enabled:
                payload["indexed_program"] = incremental_program.indexed_steps()
            if current_goal.get("candidate_ready") is not True:
                return payload, None

            raw_replay = replay_service.submit(incremental_program.program)
            status = str(raw_replay.get("status", "unknown"))
            replay_status_counts[status] = replay_status_counts.get(status, 0) + 1
            payload["automatic_clean_replay"] = normalize_replay_feedback(raw_replay)
            if status != "pass":
                return payload, None

            delivery, submission = self._submit(
                {
                    "program": incremental_program.program,
                    "summary": (
                        "Incremental executable program passed operation-triggered "
                        "target-state replay."
                    ),
                },
                replay_service,
            )
            payload["delivery"] = delivery
            return payload, submission

        def loop_metadata(
            request_index: int,
            *,
            termination_reason: str | None = None,
            termination_error: str | None = None,
            fallback_used: bool = False,
        ) -> dict[str, Any]:
            metadata: dict[str, Any] = {
                "model_requests": request_index,
                "token_usage": usage_total,
                "tool_counts": tool_counts,
                "replay_status_counts": replay_status_counts,
            }
            if (
                self.annotated_incremental_program_enabled
                or self.operation_frontier_enabled
            ):
                metadata["shell_effect_counts"] = shell_effect_counts
            if self.incumbent_enabled:
                metadata["certified_incumbent"] = {
                    "update_count": len(incumbent_updates),
                    "updates": incumbent_updates,
                    "first_certification_request": first_certification_request,
                    "fallback_used": fallback_used,
                    "latest_program_sha256": (
                        incumbent.get("program_sha256") if incumbent is not None else None
                    ),
                }
                if termination_reason is not None:
                    metadata["agent_termination"] = {
                        "reason": termination_reason,
                        "error": termination_error,
                        "certified_incumbent_available": incumbent is not None,
                        "fallback_used": fallback_used,
                    }
            if self.verifier_handoff_enabled:
                metadata["verifier_handoff"] = {
                    "trigger_count": sum(
                        item.get("transition") == "candidate-ready"
                        for item in handoff_events
                    ),
                    "forced_model_requests": handoff_forced_requests,
                    "pending_at_termination": handoff_pending,
                    "events": handoff_events,
                    "termination_reason": termination_reason,
                }
            if self.atomic_submission_enabled:
                metadata["atomic_submission"] = {
                    "termination_reason": termination_reason,
                }
            if replay_obligation_ledger is not None:
                metadata["replay_obligation_ledger"] = (
                    replay_obligation_ledger.metadata()
                )
            if scheduled_observer is not None:
                metadata["scheduled_observation"] = scheduled_observer.metadata()
            return metadata

        def fallback_submission(
            request_index: int,
            reason: str,
            error: str | None = None,
        ) -> tuple[dict[str, str], dict[str, Any]] | None:
            if not self.incumbent_enabled or incumbent is None:
                return None
            return incumbent, loop_metadata(
                request_index,
                termination_reason=reason,
                termination_error=error,
                fallback_used=True,
            )

        for request_index in range(1, self.max_iterations + 1):
            if time.monotonic() - started > self.timeout:
                fallback = fallback_submission(
                    request_index - 1,
                    "generation-wall-clock-safety-cap",
                )
                if fallback is not None:
                    return fallback
                raise RuntimeError("Agent exceeded the generation wall-clock safety cap")
            options = self.request_options(model, messages, seed=seed)
            forced_handoff_request = (
                self.verifier_handoff_enabled and handoff_pending
            )
            if forced_handoff_request:
                options["tool_choice"] = {
                    "type": "function",
                    "function": {
                        "name": (
                            "submit_bootstrap"
                            if self.atomic_handoff_enabled
                            else "submit_and_replay"
                        )
                    },
                }
                handoff_forced_requests += 1
            try:
                response = self._provider_request(
                    client,
                    options,
                    trajectory_path,
                    request_index,
                )
            except Exception as exc:
                fallback = fallback_submission(
                    request_index,
                    "provider-request-failure",
                    f"{type(exc).__name__}: {self._redact(str(exc))}",
                )
                if fallback is not None:
                    return fallback
                raise
            _accumulate_usage(usage_total, _usage_dict(response))
            choices = getattr(response, "choices", None)
            if not isinstance(choices, list) or not choices:
                fallback = fallback_submission(
                    request_index,
                    "malformed-provider-response",
                    "Provider response contains no choices",
                )
                if fallback is not None:
                    return fallback
                raise RuntimeError("Provider response contains no choices")
            message = choices[0].message
            tool_calls = list(getattr(message, "tool_calls", None) or [])
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": getattr(message, "content", None),
            }
            reasoning_content = getattr(message, "reasoning_content", None)
            if isinstance(reasoning_content, str):
                assistant_message["reasoning_content"] = reasoning_content
            if tool_calls:
                assistant_message["tool_calls"] = [
                    _tool_call_dict(call) for call in tool_calls
                ]
            messages.append(assistant_message)

            if not tool_calls:
                if incumbent is not None:
                    continuation = (
                        "A clean-replay-certified incumbent is saved. Continue only for "
                        "a material improvement, certify any replacement, or submit an "
                        "exact certified program."
                    )
                elif self.editable_incremental_program_enabled:
                    continuation = (
                        "Continue with envbench_shell and declare effect=inspect or "
                        "effect=persist for every command. Revise an earlier recorded "
                        "step when replay invalidates it. The harness will finish when "
                        "the current program replays."
                    )
                elif self.annotated_incremental_program_enabled:
                    continuation = (
                        "Continue with envbench_shell and declare effect=inspect or "
                        "effect=persist for every command. The harness will finish when "
                        "the accumulated program replays."
                    )
                elif self.incremental_program_enabled:
                    continuation = (
                        "Continue with envbench_shell for diagnosis and "
                        "apply_environment_step for every persistent repair. The harness "
                        "will finish when the accumulated program replays."
                    )
                else:
                    continuation = (
                        "Continue working with the available tools. Finish only by "
                        "calling submit_bootstrap with the complete program."
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": continuation,
                    }
                )
                continue

            handoff_triggered_this_response: dict[str, Any] | None = None
            for call in tool_calls:
                name = str(call.function.name)
                tool_counts[name] = tool_counts.get(name, 0) + 1
                try:
                    arguments = json.loads(str(call.function.arguments))
                    if not isinstance(arguments, dict):
                        raise ValueError("tool arguments must be an object")
                except (json.JSONDecodeError, ValueError) as exc:
                    payload = {"ok": False, "error": f"invalid tool arguments: {exc}"}
                    submission = None
                else:
                    submission = None
                    if name == "envbench_shell":
                        effect = arguments.get("effect")
                        command = arguments.get("command")
                        if self.annotated_incremental_program_enabled and effect not in {
                            "inspect",
                            "persist",
                        }:
                            shell_effect_counts["invalid"] += 1
                            payload = {
                                "ok": False,
                                "error": "effect must be inspect or persist",
                                "declared_effect": "invalid",
                            }
                        elif self.operation_frontier_enabled and effect not in {
                            "inspect",
                            "change",
                        }:
                            shell_effect_counts["invalid"] += 1
                            payload = {
                                "ok": False,
                                "error": "effect must be inspect or change",
                                "declared_effect": "invalid",
                            }
                        elif not isinstance(command, str):
                            payload = {"ok": False, "error": "command must be a string"}
                        else:
                            shell_result = execute_shell(str(call.id), arguments)
                            if self.annotated_incremental_program_enabled:
                                declared_effect = str(effect)
                                shell_effect_counts[declared_effect] += 1
                                if declared_effect == "persist":
                                    payload, submission = record_incremental_step(
                                        str(call.id),
                                        command,
                                        shell_result,
                                    )
                                else:
                                    payload = {
                                        **shell_result,
                                        "program_updated": False,
                                    }
                                payload["declared_effect"] = declared_effect
                            elif self.operation_frontier_enabled:
                                declared_effect = str(effect)
                                shell_effect_counts[declared_effect] += 1
                                payload = {
                                    **shell_result,
                                    "declared_effect": declared_effect,
                                    "program_updated": False,
                                }
                                if declared_effect == "change":
                                    if compatibility_service is None:
                                        payload["infrastructure_error"] = (
                                            "operation frontier service is unavailable"
                                        )
                                    else:
                                        frontier = compatibility_service.check(
                                            f"{call.id}-operation-frontier"
                                        )
                                        observation = {
                                            "schema": (
                                                "envsolve-operation-frontier-"
                                                "observation-v1"
                                            ),
                                            "trigger": "operation-change",
                                            "advisory_only": True,
                                            "result": frontier,
                                        }
                                        projected = (
                                            model_visible_scheduled_observation(
                                                observation
                                            )
                                        )
                                        payload[
                                            "operation_frontier_observation"
                                        ] = projected["result"]
                                        self._append_event(
                                            trajectory_path,
                                            {
                                                "schema": (
                                                    "envsolve-openrouter-event-v1"
                                                ),
                                                "event": (
                                                    "operation_frontier_observation"
                                                ),
                                                "request_index": request_index,
                                                "trigger": "operation-change",
                                                "parent_tool_call_id": str(call.id),
                                                "result": frontier,
                                            },
                                        )
                            else:
                                payload = shell_result
                        if scheduled_observer is not None:
                            scheduled = scheduled_observer.after_shell_operation()
                            if scheduled is not None:
                                record_scheduled_observation(
                                    scheduled,
                                    request_index,
                                    str(call.id),
                                )
                                if isinstance(payload, dict):
                                    payload = {
                                        **payload,
                                        "scheduled_compatibility_observation": (
                                            model_visible_scheduled_observation(scheduled)
                                        ),
                                    }
                                else:
                                    payload = {
                                        "shell_result": payload,
                                        "scheduled_compatibility_observation": (
                                            model_visible_scheduled_observation(scheduled)
                                        ),
                                    }
                                if schedule_verifier_handoff(
                                    scheduled,
                                    request_index,
                                ):
                                    handoff_triggered_this_response = scheduled
                    elif (
                        name == "revise_program"
                        and self.editable_incremental_program_enabled
                        and incremental_program is not None
                        and replay_service is not None
                    ):
                        if self.transactional_editable_incremental_program_enabled:
                            edits = arguments.get("edits")
                            if not isinstance(edits, list):
                                revision_error = "edits must be an array"
                                revision = None
                            else:
                                try:
                                    revision = incremental_program.revise_batch(edits)
                                except ValueError as exc:
                                    revision_error = str(exc)
                                    revision = None
                        else:
                            step_index = arguments.get("step_index")
                            replacement = arguments.get("replacement_command")
                            if (
                                isinstance(step_index, bool)
                                or not isinstance(step_index, int)
                                or not isinstance(replacement, str)
                            ):
                                revision_error = (
                                    "step_index must be an integer and "
                                    "replacement_command must be a string"
                                )
                                revision = None
                            else:
                                try:
                                    revision = incremental_program.revise(
                                        step_index,
                                        replacement,
                                    )
                                except ValueError as exc:
                                    revision_error = str(exc)
                                    revision = None

                        if revision is None:
                            payload = {"ok": False, "error": revision_error}
                        else:
                            raw_replay = replay_service.submit(
                                incremental_program.program
                            )
                            status = str(raw_replay.get("status", "unknown"))
                            replay_status_counts[status] = (
                                replay_status_counts.get(status, 0) + 1
                            )
                            payload = {
                                **normalize_replay_feedback(raw_replay),
                                "program_revision": revision,
                                "program_state": incremental_program.state(),
                                "indexed_program": (
                                    incremental_program.indexed_steps()
                                ),
                            }
                            if status == "pass":
                                delivery, submission = self._submit(
                                    {
                                        "program": incremental_program.program,
                                        "summary": (
                                            "Editable incremental program passed "
                                            "target-state replay after plan revision."
                                        ),
                                    },
                                    replay_service,
                                )
                                payload["delivery"] = delivery
                    elif (
                        name == "apply_environment_step"
                        and incremental_program is not None
                        and current_goal_service is not None
                        and replay_service is not None
                    ):
                        command = arguments.get("command")
                        if not isinstance(command, str):
                            payload = {"ok": False, "error": "command must be a string"}
                        else:
                            shell_result = execute_shell(str(call.id), arguments)
                            payload, submission = record_incremental_step(
                                str(call.id),
                                command,
                                shell_result,
                            )
                    elif (
                        name == "replay_current_program"
                        and incremental_program is not None
                        and replay_service is not None
                    ):
                        if not incremental_program.steps:
                            payload = {
                                "ok": False,
                                "error": "current deployment program has no steps",
                            }
                        else:
                            raw_replay = replay_service.submit(
                                incremental_program.program
                            )
                            status = str(raw_replay.get("status", "unknown"))
                            replay_status_counts[status] = (
                                replay_status_counts.get(status, 0) + 1
                            )
                            payload = normalize_replay_feedback(raw_replay)
                            payload["program_state"] = incremental_program.state()
                            if self.editable_incremental_program_enabled:
                                payload["indexed_program"] = (
                                    incremental_program.indexed_steps()
                                )
                            if status == "pass":
                                delivery, submission = self._submit(
                                    {
                                        "program": incremental_program.program,
                                        "summary": (
                                            "Incremental executable program passed explicit "
                                            "target-state replay."
                                        ),
                                    },
                                    replay_service,
                                )
                                payload["delivery"] = delivery
                    elif name == "check_current_goal" and current_goal_service is not None:
                        payload = current_goal_service.check(str(call.id))
                    elif name == "check_compatibility" and compatibility_service is not None:
                        payload = compatibility_service.check(str(call.id))
                    elif name == "submit_and_replay" and replay_service is not None:
                        program = arguments.get("program")
                        if not isinstance(program, str):
                            payload = {"ok": False, "error": "program must be a string"}
                        else:
                            pre_replay_observation = (
                                scheduled_observer.before_replay()
                                if scheduled_observer is not None
                                else None
                            )
                            if pre_replay_observation is not None:
                                record_scheduled_observation(
                                    pre_replay_observation,
                                    request_index,
                                    str(call.id),
                                )
                            raw_replay = replay_service.submit(program)
                            status = str(raw_replay.get("status", "unknown"))
                            replay_status_counts[status] = replay_status_counts.get(status, 0) + 1
                            payload = normalize_replay_feedback(raw_replay)
                            if replay_obligation_ledger is not None:
                                payload = {
                                    **payload,
                                    "replay_obligation_ledger": (
                                        replay_obligation_ledger.update(raw_replay)
                                    ),
                                }
                            if pre_replay_observation is not None:
                                payload = {
                                    **payload,
                                    "scheduled_compatibility_observation": (
                                        model_visible_scheduled_observation(
                                            pre_replay_observation
                                        )
                                    ),
                                }
                            if status == "pass" and self.incumbent_enabled:
                                canonical = canonical_script(program)
                                digest = script_sha256(canonical)
                                certified_digest = raw_replay.get("program_sha256")
                                certified_hashes = {
                                    item.get("program_sha256")
                                    for item in replay_service.certified_programs
                                }
                                if digest == certified_digest and digest in certified_hashes:
                                    if first_certification_request is None:
                                        first_certification_request = request_index
                                    incumbent = {
                                        "program": canonical,
                                        "summary": (
                                            "Harness fallback to the latest clean-replay-"
                                            f"certified incumbent from request {request_index}."
                                        ),
                                        "program_sha256": digest,
                                    }
                                    update = {
                                        "request_index": request_index,
                                        "program_sha256": digest,
                                        "replay_id": raw_replay.get("replay_id"),
                                        "trigger": "clean-replay-pass",
                                    }
                                    incumbent_updates.append(update)
                                    payload = {
                                        **payload,
                                        "incumbent_update": {
                                            "accepted": True,
                                            **update,
                                        },
                                    }
                                else:
                                    payload = {
                                        **payload,
                                        "incumbent_update": {
                                            "accepted": False,
                                            "reason": (
                                                "replay certificate did not match the "
                                                "canonical candidate program"
                                            ),
                                            "candidate_program_sha256": digest,
                                            "certified_program_sha256": certified_digest,
                                        },
                                    }
                            if self.verifier_handoff_enabled:
                                if status == "pass":
                                    auto_payload, auto_submission = self._submit(
                                        {
                                            "program": program,
                                            "summary": (
                                                "Trusted verifier-triggered handoff returned "
                                                "the clean-replay-certified program."
                                            ),
                                        },
                                        replay_service,
                                    )
                                    if auto_submission is not None:
                                        submission = auto_submission
                                        handoff_pending = False
                                        handoff_events.append(
                                            {
                                                "transition": "clean-replay-pass-returned",
                                                "request_index": request_index,
                                                "replay_id": raw_replay.get("replay_id"),
                                                "program_sha256": auto_submission.get(
                                                    "program_sha256"
                                                ),
                                            }
                                        )
                                        payload = {
                                            **payload,
                                            "verifier_handoff": {
                                                "returned": True,
                                                "reason": "clean-replay-pass",
                                            },
                                        }
                                    else:
                                        handoff_pending = False
                                        handoff_events.append(
                                            {
                                                "transition": "certified-program-return-failed",
                                                "request_index": request_index,
                                                "reason": auto_payload.get("reason"),
                                            }
                                        )
                                        payload = {
                                            **payload,
                                            "verifier_handoff": {
                                                "returned": False,
                                                "reason": auto_payload.get("reason"),
                                            },
                                        }
                                elif handoff_pending:
                                    handoff_pending = False
                                    handoff_events.append(
                                        {
                                            "transition": "replay-returned-for-free-repair",
                                            "request_index": request_index,
                                            "replay_id": raw_replay.get("replay_id"),
                                            "replay_status": status,
                                        }
                                    )
                    elif name == "submit_bootstrap":
                        if self.atomic_submission_enabled:
                            if replay_service is None:
                                raise RuntimeError(
                                    "Atomic submission requires a clean replay service"
                                )
                            payload, submission, status = self._atomic_submit(
                                arguments,
                                replay_service,
                            )
                            if status is not None:
                                replay_status_counts[status] = (
                                    replay_status_counts.get(status, 0) + 1
                                )
                            if self.atomic_handoff_enabled and handoff_pending:
                                replay_id = (
                                    payload.get("replay_id")
                                    if isinstance(payload, dict)
                                    else None
                                )
                                if status == "pass" and submission is not None:
                                    handoff_pending = False
                                    handoff_events.append(
                                        {
                                            "transition": "clean-replay-pass-returned",
                                            "request_index": request_index,
                                            "replay_id": replay_id,
                                            "program_sha256": submission.get(
                                                "program_sha256"
                                            ),
                                        }
                                    )
                                elif status is not None:
                                    handoff_pending = False
                                    handoff_events.append(
                                        {
                                            "transition": "replay-returned-for-free-repair",
                                            "request_index": request_index,
                                            "replay_id": replay_id,
                                            "replay_status": status,
                                        }
                                    )
                        else:
                            payload, submission = self._submit(arguments, replay_service)
                    else:
                        payload = {"ok": False, "error": f"unknown tool: {name}"}

                self._append_event(
                    trajectory_path,
                    {
                        "schema": "envsolve-openrouter-event-v1",
                        "event": "tool_result",
                        "request_index": request_index,
                        "tool_call_id": str(call.id),
                        "tool_name": name,
                        "result": payload,
                    },
                )
                if submission is not None:
                    return submission, loop_metadata(
                        request_index,
                        termination_reason=(
                            "agent-submission"
                            if self.incumbent_enabled
                            else (
                                "verifier-triggered-replay-pass"
                                if forced_handoff_request
                                else (
                                    "incremental-program-replay-pass"
                                    if self.incremental_program_enabled
                                    else "atomic-submit-clean-replay-pass"
                                    if self.atomic_submission_enabled
                                    else None
                                )
                            )
                        ),
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.id),
                        "name": name,
                        "content": json.dumps(payload, ensure_ascii=True, sort_keys=True),
                    }
                )
            if handoff_triggered_this_response is not None:
                messages.append(handoff_message(handoff_triggered_this_response))
        fallback = fallback_submission(
            self.max_iterations,
            "agent-request-safety-cap",
        )
        if fallback is not None:
            return fallback
        raise RuntimeError("Agent exhausted the request safety cap without submission")

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        started_at = self._now()
        write_json(artifacts.status, {"state": "generating", "updated_at": started_at})
        connection = provider_connection(run_spec.model)
        metadata: dict[str, Any] = {
            "runner": self.runner_name,
            "runner_version": self.runner_version,
            "baseline_interface": self.agent_interface,
            "mechanism_primitives": self.mechanism_primitives,
            "model_reasoning_effort": self.reasoning_effort,
            "provider": connection["provider"],
            "provider_base_url": connection["base_url"],
            "provider_policy": (
                self._provider_policy()
                if connection["provider"] == "openrouter"
                else {"route": "first-party-direct"}
            ),
            "sampling_control": {
                "requested_seed": run_spec.seed,
                "forwarded_to_every_model_request": (
                    run_spec.seed is not None
                    and not is_deepseek_direct_model(run_spec.model)
                ),
                "provider_support": (
                    "not-documented"
                    if is_deepseek_direct_model(run_spec.model)
                    else "qualified-by-provider-canary"
                ),
                "scope": "all-model-requests-in-episode",
                "determinism_guaranteed": False,
            },
            "credential_variable": connection["credential_variable"],
            "credential_present": bool(
                os.environ.get(connection["credential_variable"])
            ),
            "official_evaluator_access": "post-episode-only",
            "resource_policy": {
                "generation_wall_clock_safety_cap_seconds": self.timeout,
                "container_command_safety_cap_seconds": self.command_timeout,
                "agent_request_safety_cap": self.max_iterations,
                "provider_max_retries_per_request": self.model_max_retries,
                "provider_retry_delays_seconds": list(
                    _PROVIDER_RETRY_DELAYS_SECONDS[: self.model_max_retries]
                ),
                "token_usage_is_hard_limit": False,
                "cost_is_hard_limit": False,
            },
            "image_reference": self.image,
            "goal_contract": {
                "contract_id": self.goal_contract.contract_id,
                "report_schema": self.goal_contract.report_schema,
                "sha256": self.goal_contract.sha256,
            },
            "workspace_preconditions": [
                item.to_dict() for item in self.workspace_preconditions
            ],
            "started_at": started_at,
        }
        if run_spec.model not in SUPPORTED_DEEPSEEK_MODELS:
            return self._finish(
                artifacts,
                SolverResult(
                    False,
                    run_spec.method,
                    error=(
                        "Provider API experiments require a qualified DeepSeek model: "
                        f"{', '.join(sorted(SUPPORTED_DEEPSEEK_MODELS))}"
                    ),
                    metadata=metadata,
                ),
                "Model identity rejected before provider access.\n",
            )

        workspace = artifacts.generation_dir / "workspace"
        trajectory_path = artifacts.trajectory_jsonl
        command_trace_path = artifacts.generation_dir / "container-commands.jsonl"
        replay_root = artifacts.generation_dir / "clean-replay"
        package_cache_root = artifacts.generation_dir / "package-cache"
        control_root = artifacts.generation_dir / "openrouter-control"
        prompt_path = control_root / "prompt.txt"
        prompt = self._prompt(case, self.goal_contract)
        write_text_atomic(prompt_path, prompt)
        metadata["prompt"] = {
            "path": str(prompt_path.relative_to(artifacts.root)),
            "sha256": sha256_file(prompt_path),
        }
        container_id: str | None = None
        terminal: V2ProcessTreeSafePersistentContainerShell | None = None
        current_goal_service: CurrentGoalService | None = None
        incremental_program: IncrementalProgram | None = None
        compatibility_service: CompatibilityLedgerService | None = None
        scheduled_observer: ScheduledCompatibilityObserver | None = None
        log_parts: list[str] = []
        try:
            repository_acquisition = self._acquire_repository(case, workspace)
            self._materialize_workspace_preconditions(workspace)
            metadata["repository_acquisition"] = repository_acquisition
            image_digest = self._image_digest()
            metadata["image_digest"] = image_digest
            container_id = self._create_container_with_package_cache(
                workspace,
                image_digest,
                package_cache_root,
            )
            metadata["package_cache"] = {
                "scope": "single-episode",
                "cross_case_sharing": False,
                "container_path": "/root/.cache",
                "shared_phases": ["construction"],
                "clean_replay_policy": "fresh-container-default-cache",
                "path": str(package_cache_root.relative_to(artifacts.root)),
            }
            terminal = V2ProcessTreeSafePersistentContainerShell(
                container_id,
                "/data/project",
                self.command_timeout,
                16_000,
                os.environ.get("DOCKER_EXECUTABLE", "docker"),
            )
            terminal_server = ContainerMcpServer(terminal, command_trace_path)
            if self.incremental_program_enabled:
                incremental_program = IncrementalProgram(
                    artifacts.generation_dir / "incremental-program"
                )

            replay_service: CleanReplayService | None = None
            if self.replay_enabled:
                provider = self._create_replay_provider(
                    workspace,
                    replay_root,
                    image_digest,
                    case,
                )
                verifier = MinimalIntegrityGoalVerifier(
                    self.goal_contract,
                    observation_timeout=self.command_timeout,
                    effect_auditor=lambda worktree: inspect_minimal_repository_integrity(
                        worktree,
                        case.revision,
                        self.workspace_preconditions,
                    ),
                )
                replay_service = ObligationSnapshotCleanReplayService(
                    provider=provider,
                    verifier=verifier,
                    repository=case.repository,
                    revision=case.revision,
                    image_digest=image_digest,
                    goal_contract_sha256=self.goal_contract.sha256,
                    trace_path=replay_root / "replays.jsonl",
                    certification_path=replay_root / "certification.json",
                    programs_root=replay_root / "programs",
                )
                replay_service.validator = self.validator

            compatibility_service = (
                CompatibilityLedgerService(self.goal_contract, terminal_server)
                if self.compatibility_observation_enabled
                else None
            )
            current_goal_service = (
                CurrentGoalService(self.goal_contract, terminal_server)
                if self.current_goal_enabled or self.incremental_program_enabled
                else None
            )
            scheduled_observer = (
                ScheduledCompatibilityObserver(compatibility_service)
                if self.scheduled_observation_enabled
                and compatibility_service is not None
                else None
            )

            client = self._client(run_spec.model)
            submission, loop_metadata = self._agent_loop(
                client=client,
                model=run_spec.model,
                prompt=prompt,
                terminal_server=terminal_server,
                replay_service=replay_service,
                incremental_program=incremental_program,
                current_goal_service=current_goal_service,
                compatibility_service=compatibility_service,
                scheduled_observer=scheduled_observer,
                trajectory_path=trajectory_path,
                seed=run_spec.seed,
            )
            metadata.update(loop_metadata)
            metadata["trajectory_progress"] = _trajectory_progress(trajectory_path)
            construction_integrity = inspect_minimal_repository_integrity(
                workspace,
                case.revision,
                self.workspace_preconditions,
            )
            metadata["construction_workspace_integrity"] = (
                construction_integrity.to_dict()
            )
            if replay_service is not None:
                repository_integrity = _certified_repository_integrity(
                    replay_service,
                    submission["program_sha256"],
                )
            else:
                repository_integrity = construction_integrity.to_dict()
            metadata["repository_integrity"] = repository_integrity
            if repository_integrity.get("valid") is not True:
                raise RuntimeError(
                    "submitted environment violated minimal repository integrity: "
                    f"{repository_integrity.get('violations', [])}"
                )
            command_records = read_jsonl(command_trace_path) if command_trace_path.is_file() else []
            metadata["container_command_trace"] = {
                "path": str(command_trace_path.relative_to(artifacts.root)),
                "sha256": (
                    sha256_file(command_trace_path) if command_trace_path.is_file() else None
                ),
                "count": len(command_records),
                "successful_count": sum(
                    1
                    for item in command_records
                    if item.get("exit_code") == 0
                    and not item.get("timed_out")
                    and not item.get("infrastructure_error")
                ),
            }
            if compatibility_service is not None:
                metadata["compatibility_ledger"] = compatibility_service.metadata()
            if current_goal_service is not None:
                metadata["current_goal"] = current_goal_service.metadata()
            if incremental_program is not None:
                incremental_metadata = incremental_program.metadata()
                incremental_metadata["steps_path"] = str(
                    incremental_program.steps_path.relative_to(artifacts.root)
                )
                incremental_metadata["program_path"] = str(
                    incremental_program.program_path.relative_to(artifacts.root)
                )
                metadata["incremental_program"] = incremental_metadata
            if scheduled_observer is not None:
                metadata["scheduled_observation"] = scheduled_observer.metadata()
            submission_metadata: dict[str, Any] = {
                "summary": submission["summary"],
                "program_sha256": submission["program_sha256"],
                "certified_by_clean_replay": self.replay_enabled,
            }
            if self.incumbent_enabled:
                submission_metadata["selected_by"] = (
                    "certified-incumbent-fallback"
                    if metadata.get("certified_incumbent", {}).get("fallback_used")
                    else "agent-submission"
                )
            metadata["submission"] = submission_metadata
            if replay_service is not None:
                metadata["clean_replay"] = {
                    "count": replay_service.sequence,
                    "certified_program_count": len(replay_service.certified_programs),
                    "trace_path": str((replay_root / "replays.jsonl").relative_to(artifacts.root)),
                    "certification_path": str(
                        (replay_root / "certification.json").relative_to(artifacts.root)
                    ),
                }
            write_text_atomic(artifacts.generated_script, submission["program"] + "\n")
            result = SolverResult(
                True,
                run_spec.method,
                script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
                trajectory_path=str(trajectory_path.relative_to(artifacts.root)),
                metadata={**metadata, "finished_at": self._now()},
            )
            return self._finish(artifacts, result, "\n".join(log_parts))
        except Exception as exc:
            if current_goal_service is not None:
                metadata["current_goal"] = current_goal_service.metadata()
            if incremental_program is not None:
                incremental_metadata = incremental_program.metadata()
                incremental_metadata["steps_path"] = str(
                    incremental_program.steps_path.relative_to(artifacts.root)
                )
                incremental_metadata["program_path"] = str(
                    incremental_program.program_path.relative_to(artifacts.root)
                )
                metadata["incremental_program"] = incremental_metadata
            if compatibility_service is not None:
                metadata["compatibility_ledger"] = compatibility_service.metadata()
            if scheduled_observer is not None:
                metadata["scheduled_observation"] = scheduled_observer.metadata()
            metadata["trajectory_progress"] = _trajectory_progress(trajectory_path)
            log_parts.append(f"{type(exc).__name__}: {self._redact(str(exc))}\n")
            result = SolverResult(
                False,
                run_spec.method,
                trajectory_path=(
                    str(trajectory_path.relative_to(artifacts.root))
                    if trajectory_path.is_file()
                    else None
                ),
                error=f"{type(exc).__name__}: {self._redact(str(exc))}",
                metadata={**metadata, "finished_at": self._now()},
            )
            return self._finish(artifacts, result, "\n".join(log_parts))
        finally:
            if terminal is not None:
                terminal.close()
            if container_id:
                import subprocess

                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "--user",
                        "0:0",
                        container_id,
                        "chown",
                        "-R",
                        f"{os.getuid()}:{os.getgid()}",
                        "/data/project",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                subprocess.run(
                    ["docker", "rm", "-f", container_id],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            cleanup_case_containers(artifacts.root)
