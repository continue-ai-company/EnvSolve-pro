from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.compatibility_ledger import ScheduledCompatibilityObserver
from envsolve_harness.codex.minimal_b_mcp import script_sha256
from envsolve_harness.replay_feedback import normalize_replay_feedback
from envsolve_harness.runners.openrouter_agent import (
    DEEPSEEK_DIRECT_BASE_URL,
    DEEPSEEK_DIRECT_V4_FLASH,
    DEEPSEEK_V4_FLASH_0731,
    DEEPSEEK_V4_PRO,
    OpenRouterAgentRunner,
    SUPPORTED_DEEPSEEK_MODELS,
    _request_contract,
    _trajectory_progress,
)


class FakeDump:
    def __init__(self, value: dict[str, object]) -> None:
        self.value = value

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return self.value


class FakeResponse:
    def __init__(self, *tool_calls: SimpleNamespace) -> None:
        self.choices = [
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=list(tool_calls))
            )
        ]
        self.usage = FakeDump(
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        )

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {"id": "response", "model": DEEPSEEK_V4_PRO}


def tool_call(call_id: str, name: str, arguments: dict[str, object]) -> SimpleNamespace:
    import json

    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=True),
        ),
    )


class FakeCompletions:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def create(self, **options: object) -> FakeResponse:
        self.requests.append(options)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class FakeTerminalServer:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def handle(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        return {
            "result": {
                "structuredContent": {
                    "command": "true",
                    "exit_code": 0,
                    "output": "",
                    "duration_seconds": 0.01,
                }
            }
        }


class FakeReplayService:
    def __init__(self, program: str) -> None:
        self.program = program
        self.certified_programs: list[dict[str, object]] = []

    def submit(self, program: str) -> dict[str, object]:
        self.certified_programs.append({"program_sha256": script_sha256(program)})
        return {
            "status": "pass",
            "phase": "clean-replay",
            "replay_id": "replay-1",
            "program_sha256": script_sha256(program),
            "environment_receipt": {
                "environment_id": "container-1",
                "provider_id": "fresh",
                "image_digest": "sha256:image",
                "repository": "owner/repo",
                "revision": "abc",
            },
            "verification": {
                "summary": "goal passed",
                "bootstrap": {
                    "exit_code": 0,
                    "stdout": "ok",
                    "stderr": "",
                    "duration_seconds": 1.0,
                },
                "counterexamples": {"json": "[]", "truncated": False},
                "details": {"json": "{}", "truncated": False},
                "obligation_snapshot": {
                    "schema": "envsolve-replay-obligation-snapshot-v1",
                    "coverage": "complete-pass",
                    "verification_passed": True,
                    "finding_set_complete": True,
                    "obligations": [],
                },
            },
            "certificate": {"program_sha256": script_sha256(program)},
        }


class FakeCompatibilityService:
    def __init__(self) -> None:
        self.call_ids: list[str] = []

    def check(self, call_id: str) -> dict[str, object]:
        self.call_ids.append(call_id)
        return {
            "schema": "envsolve-compatibility-delta-ledger-v1",
            "ok": True,
            "finding_set_complete": True,
            "goal_status": "fail",
            "candidate_ready": False,
            "current": {"obligation_count": 1},
            "delta_from_previous": {"classification": "initial"},
            "operation_constraints_added": False,
        }

    def metadata(self) -> dict[str, object]:
        return {
            "observation_count": len(self.call_ids),
            "complete_observation_count": len(self.call_ids),
        }


class CandidateReadyCompatibilityService(FakeCompatibilityService):
    def check(self, call_id: str) -> dict[str, object]:
        self.call_ids.append(call_id)
        return {
            "schema": "envsolve-compatibility-delta-ledger-v1",
            "ok": True,
            "finding_set_complete": True,
            "goal_status": "pass",
            "candidate_ready": True,
            "current": {"obligation_count": 0},
            "delta_from_previous": {"classification": "improved"},
            "operation_constraints_added": False,
        }


class OpenRouterAgentRunnerTest(unittest.TestCase):
    def test_construction_container_keeps_the_episode_package_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            cache_root = root / "cache"
            runner = self._runner(root, "soft")
            checked = mock.Mock(side_effect=["container-1", "", ""])
            runner._checked = checked  # type: ignore[method-assign]

            container_id = runner._create_container_with_package_cache(
                workspace,
                "sha256:image",
                cache_root,
            )
            cache_mode = cache_root.stat().st_mode & 0o777

        create_command = checked.call_args_list[0].args[0]
        self.assertEqual(container_id, "container-1")
        self.assertIn(
            f"type=bind,src={cache_root.resolve()},dst=/root/.cache",
            create_command,
        )
        self.assertEqual(cache_mode, 0o777)

    def test_replay_provider_does_not_reuse_construction_package_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            runner = self._runner(root, "soft")
            provider = runner._create_replay_provider(
                workspace,
                root / "clean-replay",
                "sha256:image",
                SimpleNamespace(repository="owner/repo", revision="abc"),
            )

        self.assertIs(provider.run_command, subprocess.run)
        self.assertEqual(provider.source_repository, workspace.resolve())

    def _runner(
        self,
        root: Path,
        replay_mode: str,
        *,
        public_goal_visible: bool = True,
    ) -> OpenRouterAgentRunner:
        return OpenRouterAgentRunner(
            harness_root=root,
            source_cache_root=root / "source-cache",
            image="sha256:image",
            timeout=120,
            command_timeout=30,
            container_create_timeout=10,
            git_fetch_timeout=20,
            max_iterations=10,
            model_request_timeout=30,
            model_max_retries=5,
            model_max_output_tokens=4096,
            reasoning_effort="xhigh",
            replay_mode=replay_mode,  # type: ignore[arg-type]
            public_goal_visible=public_goal_visible,
            workspace_preconditions=(),
            goal_contract=ExecutableGoalContract(
                "goal",
                "Require success",
                "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
            ),
        )

    def test_repository_feedback_control_does_not_receive_public_goal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(
                Path(directory),
                "none",
                public_goal_visible=False,
            )
            prompt = runner._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertNotIn("<trusted_goal_program>", prompt)
        self.assertNotIn(runner.goal_contract.program, prompt)
        self.assertIn("repository-owned", prompt)
        self.assertEqual(runner.mechanism_primitives, ["F", "minimal-H"])
        self.assertEqual(runner.agent_interface, "free-repository-feedback-search-v1")

    def test_goal_visibility_is_isolated_from_clean_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blind = self._runner(root, "none", public_goal_visible=False)
            visible = self._runner(root, "none")
            replay = self._runner(root, "soft")

            self.assertEqual(blind._tools(), visible._tools())
            self.assertIn("<trusted_goal_program>", visible._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            ))
            self.assertEqual(
                visible.mechanism_primitives,
                ["F", "public-O", "minimal-H"],
            )
            self.assertEqual(
                replay.mechanism_primitives,
                ["F", "public-O", "soft-C", "R", "minimal-H"],
            )

        with self.assertRaisesRegex(ValueError, "model-visible public goal"):
            self._runner(root, "soft", public_goal_visible=False)

    def test_repository_acquisition_uses_exact_revision_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self._runner(root, "none")
            destination = root / "workspace"
            case = SimpleNamespace(repository="owner/repo", revision="abc123")
            receipt = {
                "source": "immutable-exact-revision-cache-v1",
                "cache_hit": True,
            }
            with mock.patch(
                "envsolve_harness.runners.openrouter_agent.ExactRevisionSourceCache"
            ) as cache_type:
                cache_type.return_value.acquire.return_value = receipt
                result = runner._acquire_repository(case, destination)  # type: ignore[arg-type]

        cache_type.assert_called_once_with((root / "source-cache").resolve(), 20)
        cache_type.return_value.acquire.assert_called_once_with(
            repository="owner/repo",
            revision="abc123",
            destination=destination,
        )
        self.assertEqual(result, receipt)

    def test_control_and_treatment_differ_only_by_replay_capability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = self._runner(root, "none")
            treatment = self._runner(root, "soft")

            control_tools = control._tools()
            treatment_tools = treatment._tools()
            control_names = [item["function"]["name"] for item in control_tools]
            treatment_names = [item["function"]["name"] for item in treatment_tools]

        self.assertEqual(control_names, ["envbench_shell", "submit_bootstrap"])
        self.assertEqual(
            treatment_names,
            ["envbench_shell", "submit_and_replay", "submit_bootstrap"],
        )
        with mock.patch.dict(os.environ, {"OPENROUTER_PROVIDER_ORDER": ""}):
            self.assertEqual(control._provider_policy(), treatment._provider_policy())
            options = treatment.request_options(
                DEEPSEEK_V4_PRO, [{"role": "user", "content": "x"}]
            )
        self.assertEqual(options["model"], DEEPSEEK_V4_PRO)
        self.assertEqual(options["extra_body"]["reasoning"], {"effort": "xhigh"})
        self.assertEqual(
            options["extra_body"]["provider"],
            {"require_parameters": True, "allow_fallbacks": False},
        )

    def test_atomic_submission_keeps_the_control_action_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = self._runner(root, "none")
            atomic = self._runner(root, "atomic")
            control_tools = control._tools()
            atomic_tools = atomic._tools()
            prompt = atomic._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertEqual(
            [item["function"]["name"] for item in atomic_tools],
            ["envbench_shell", "submit_bootstrap"],
        )
        self.assertEqual(
            [item["function"]["parameters"] for item in atomic_tools],
            [item["function"]["parameters"] for item in control_tools],
        )
        self.assertNotIn("submit_and_replay", prompt)
        self.assertIn("single atomic delivery action", prompt)
        self.assertIn("Fail returns normalized executable", prompt)
        self.assertEqual(
            atomic.agent_interface,
            "free-feedback-search+atomic-submit-clean-replay-v1",
        )
        self.assertEqual(
            atomic.mechanism_primitives,
            ["F", "public-O", "soft-C", "R", "atomic-delivery", "minimal-H"],
        )

    def test_atomic_handoff_keeps_atomic_action_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic = self._runner(root, "atomic")
            handoff = self._runner(root, "atomic-handoff")
            prompt = handoff._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertEqual(handoff._tools(), atomic._tools())
        self.assertNotIn("submit_and_replay", prompt)
        self.assertIn("single atomic delivery action", prompt)
        self.assertIn("automatically executes the complete public goal", prompt)
        self.assertEqual(
            handoff.agent_interface,
            "free-feedback-search+scheduled-trusted-goal-observation+"
            "verified-atomic-handoff-v1",
        )
        self.assertEqual(
            handoff.mechanism_primitives,
            [
                "F",
                "scheduled-O",
                "verified-atomic-handoff",
                "soft-C",
                "R",
                "minimal-H",
            ],
        )

    def test_deepseek_direct_uses_first_party_route_and_thinking_parameters(self) -> None:
        created: dict[str, object] = {}

        def factory(**options: object) -> object:
            created.update(options)
            return object()

        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "stateful")
            runner.client_factory = factory
            options = runner.request_options(
                DEEPSEEK_DIRECT_V4_FLASH,
                [{"role": "user", "content": "x"}],
                seed=12345,
            )
            with mock.patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "present-not-recorded"},
                clear=True,
            ):
                runner._client(DEEPSEEK_DIRECT_V4_FLASH)

        self.assertEqual(created["base_url"], DEEPSEEK_DIRECT_BASE_URL)
        self.assertEqual(created["api_key"], "present-not-recorded")
        self.assertEqual(options["model"], DEEPSEEK_DIRECT_V4_FLASH)
        self.assertEqual(options["reasoning_effort"], "xhigh")
        self.assertNotIn("seed", options)
        self.assertEqual(
            options["extra_body"],
            {"thinking": {"type": "enabled"}},
        )
        self.assertNotIn("provider", options["extra_body"])

    def test_reasoning_content_is_preserved_across_direct_tool_turns(self) -> None:
        response = FakeResponse(tool_call("1", "submit_bootstrap", {
            "program": "python -m pip install -e .",
            "summary": "done",
        }))
        response.choices[0].message.reasoning_content = "inspect then submit"
        client = FakeClient([response])
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "none")
            runner._agent_loop(
                client=client,
                model=DEEPSEEK_DIRECT_V4_FLASH,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=None,
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        assistant = client.chat.completions.requests[0]["messages"][1]
        self.assertEqual(assistant["reasoning_content"], "inspect then submit")

    def test_incumbent_treatment_reuses_the_frozen_replay_tool_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "incumbent")
            names = [item["function"]["name"] for item in runner._tools()]
            prompt = runner._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertEqual(
            names,
            [
                "envbench_shell",
                "submit_and_replay",
                "submit_bootstrap",
            ],
        )
        self.assertIn("harness-managed", prompt)
        self.assertIn("never a container checkpoint", prompt)

    def test_ledger_treatment_adds_only_advisory_compatibility_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "ledger")
            names = [item["function"]["name"] for item in runner._tools()]
            prompt = runner._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertEqual(
            names,
            [
                "envbench_shell",
                "check_compatibility",
                "submit_and_replay",
                "submit_bootstrap",
            ],
        )
        self.assertIn("A regression is evidence, not a forbidden state", prompt)
        self.assertIn("never selects packages, blocks commands", prompt)

    def test_scheduled_treatment_keeps_the_control_tool_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control = self._runner(Path(directory), "soft")
            treatment = self._runner(Path(directory), "scheduled")
            control_names = [item["function"]["name"] for item in control._tools()]
            treatment_names = [item["function"]["name"] for item in treatment._tools()]
            prompt = treatment._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertEqual(treatment_names, control_names)
        self.assertNotIn("check_compatibility", treatment_names)
        self.assertIn("after every 16 completed shell operations", prompt)
        self.assertIn("temporary regression remains allowed", prompt)
        self.assertEqual(
            treatment.mechanism_primitives,
            ["F", "scheduled-O", "delta-C", "R", "minimal-H"],
        )

    def test_verifier_handoff_keeps_the_pre_trigger_interface_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = self._runner(root, "scheduled")
            runner = self._runner(root, "handoff")
            names = [item["function"]["name"] for item in runner._tools()]
            control_prompt = control._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )
            treatment_prompt = runner._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertEqual(
            names,
            ["envbench_shell", "submit_and_replay", "submit_bootstrap"],
        )
        self.assertEqual(treatment_prompt, control_prompt)
        self.assertNotIn("from free search to programization", treatment_prompt)
        self.assertEqual(
            runner.mechanism_primitives,
            [
                "F",
                "scheduled-O",
                "verifier-triggered-programization",
                "R",
                "minimal-H",
            ],
        )

    def test_stateful_replay_keeps_tools_free_and_adds_only_advisory_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control = self._runner(Path(directory), "scheduled")
            treatment = self._runner(Path(directory), "stateful")
            control_names = [item["function"]["name"] for item in control._tools()]
            treatment_names = [
                item["function"]["name"] for item in treatment._tools()
            ]
            prompt = treatment._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )
            control_prompt = control._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertEqual(treatment_names, control_names)
        self.assertEqual(prompt, control_prompt)
        self.assertNotIn("replay_obligation_ledger", prompt)
        self.assertEqual(
            treatment.mechanism_primitives,
            [
                "F",
                "scheduled-O",
                "replay-obligation-ledger",
                "R",
                "minimal-H",
            ],
        )

    def test_stateful_replay_feedback_reaches_same_session_and_metadata(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        client = FakeClient(
            [
                FakeResponse(
                    tool_call("1", "submit_and_replay", {"program": program})
                ),
                FakeResponse(
                    tool_call(
                        "2",
                        "submit_bootstrap",
                        {"program": program, "summary": "done"},
                    )
                ),
            ]
        )
        compatibility = FakeCompatibilityService()
        scheduled = ScheduledCompatibilityObserver(compatibility)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "stateful")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                scheduled_observer=scheduled,
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        second_messages = client.chat.completions.requests[1]["messages"]
        self.assertTrue(
            any(
                item.get("role") == "tool"
                and "replay_obligation_ledger" in str(item.get("content"))
                for item in second_messages
            )
        )
        self.assertEqual(submission["program_sha256"], script_sha256(program))
        self.assertEqual(metadata["replay_obligation_ledger"]["replay_count"], 1)
        self.assertEqual(
            metadata["replay_obligation_ledger"]["active_obligation_count"],
            0,
        )

    def test_candidate_ready_forces_replay_and_returns_pass_without_second_request(
        self,
    ) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        client = FakeClient(
            [FakeResponse(tool_call("1", "submit_and_replay", {"program": program}))]
        )
        compatibility = CandidateReadyCompatibilityService()
        scheduled = ScheduledCompatibilityObserver(compatibility)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "handoff")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                scheduled_observer=scheduled,
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(submission["program_sha256"], script_sha256(program))
        self.assertEqual(metadata["model_requests"], 1)
        self.assertEqual(metadata["tool_counts"]["submit_and_replay"], 1)
        self.assertEqual(metadata["verifier_handoff"]["trigger_count"], 1)
        self.assertEqual(metadata["verifier_handoff"]["forced_model_requests"], 1)
        self.assertEqual(
            metadata["verifier_handoff"]["termination_reason"],
            "verifier-triggered-replay-pass",
        )
        self.assertEqual(
            [item["transition"] for item in metadata["verifier_handoff"]["events"]],
            ["candidate-ready", "clean-replay-pass-returned"],
        )
        self.assertEqual(
            client.chat.completions.requests[0]["tool_choice"],
            {"type": "function", "function": {"name": "submit_and_replay"}},
        )
        self.assertTrue(
            any(
                item.get("role") == "user"
                and "candidate_ready=true" in str(item.get("content"))
                for item in client.chat.completions.requests[0]["messages"]
            )
        )

    def test_failed_forced_replay_restores_free_tool_choice(self) -> None:
        first_program = "false"
        second_program = "python -m venv .venv\nsource .venv/bin/activate"

        class FailThenPassReplay(FakeReplayService):
            def __init__(self) -> None:
                super().__init__(second_program)
                self.calls = 0

            def submit(self, program: str) -> dict[str, object]:
                self.calls += 1
                if self.calls == 1:
                    return {
                        "status": "fail",
                        "phase": "clean-replay",
                        "replay_id": "replay-1",
                        "program_sha256": script_sha256(program),
                        "verification": {
                            "summary": "bootstrap failed",
                            "bootstrap": {
                                "exit_code": 1,
                                "stdout": "",
                                "stderr": "failed",
                                "duration_seconds": 1.0,
                            },
                            "counterexamples": {"json": "[]", "truncated": False},
                            "details": {"json": "{}", "truncated": False},
                        },
                    }
                return super().submit(program)

        client = FakeClient(
            [
                FakeResponse(
                    tool_call("1", "submit_and_replay", {"program": first_program})
                ),
                FakeResponse(tool_call("2", "envbench_shell", {"command": "true"})),
                FakeResponse(
                    tool_call("3", "submit_and_replay", {"program": second_program})
                ),
            ]
        )
        compatibility = CandidateReadyCompatibilityService()
        scheduled = ScheduledCompatibilityObserver(compatibility)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "handoff")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FailThenPassReplay(),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                scheduled_observer=scheduled,
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(submission["program_sha256"], script_sha256(second_program))
        self.assertEqual(
            client.chat.completions.requests[0]["tool_choice"],
            {"type": "function", "function": {"name": "submit_and_replay"}},
        )
        self.assertEqual(client.chat.completions.requests[1]["tool_choice"], "auto")
        self.assertEqual(client.chat.completions.requests[2]["tool_choice"], "auto")
        self.assertIn(
            "replay-returned-for-free-repair",
            [item["transition"] for item in metadata["verifier_handoff"]["events"]],
        )

    def test_candidate_ready_forces_atomic_delivery_then_restores_free_repair(
        self,
    ) -> None:
        first_program = "false"
        second_program = "python -m venv .venv\nsource .venv/bin/activate"

        class FailThenPassReplay(FakeReplayService):
            def __init__(self) -> None:
                super().__init__(second_program)
                self.calls = 0

            def submit(self, program: str) -> dict[str, object]:
                self.calls += 1
                if self.calls == 1:
                    return {
                        "status": "fail",
                        "phase": "clean-replay",
                        "replay_id": "replay-1",
                        "program_sha256": script_sha256(program),
                        "verification": {
                            "summary": "bootstrap failed",
                            "bootstrap": {
                                "exit_code": 1,
                                "stdout": "",
                                "stderr": "failed",
                                "duration_seconds": 1.0,
                            },
                            "counterexamples": {"json": "[]", "truncated": False},
                            "details": {"json": "{}", "truncated": False},
                        },
                    }
                return super().submit(program)

        client = FakeClient(
            [
                FakeResponse(
                    tool_call(
                        "1",
                        "submit_bootstrap",
                        {"program": first_program, "summary": "first attempt"},
                    )
                ),
                FakeResponse(
                    tool_call(
                        "2",
                        "submit_bootstrap",
                        {"program": second_program, "summary": "repair"},
                    )
                ),
            ]
        )
        compatibility = CandidateReadyCompatibilityService()
        scheduled = ScheduledCompatibilityObserver(compatibility)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "atomic-handoff")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FailThenPassReplay(),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                scheduled_observer=scheduled,
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(submission["program_sha256"], script_sha256(second_program))
        self.assertEqual(
            client.chat.completions.requests[0]["tool_choice"],
            {"type": "function", "function": {"name": "submit_bootstrap"}},
        )
        self.assertEqual(client.chat.completions.requests[1]["tool_choice"], "auto")
        self.assertEqual(metadata["tool_counts"]["submit_bootstrap"], 2)
        self.assertEqual(metadata["replay_status_counts"], {"fail": 1, "pass": 1})
        self.assertEqual(metadata["verifier_handoff"]["trigger_count"], 1)
        self.assertEqual(metadata["verifier_handoff"]["forced_model_requests"], 1)
        self.assertEqual(
            metadata["verifier_handoff"]["termination_reason"],
            "atomic-submit-clean-replay-pass",
        )
        self.assertEqual(
            [item["transition"] for item in metadata["verifier_handoff"]["events"]],
            [
                "candidate-ready",
                "replay-returned-for-free-repair",
            ],
        )

    def test_candidate_ready_atomic_delivery_returns_passing_program(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        client = FakeClient(
            [
                FakeResponse(
                    tool_call(
                        "1",
                        "submit_bootstrap",
                        {"program": program, "summary": "ready"},
                    )
                )
            ]
        )
        compatibility = CandidateReadyCompatibilityService()
        scheduled = ScheduledCompatibilityObserver(compatibility)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "atomic-handoff")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                scheduled_observer=scheduled,
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(submission["program_sha256"], script_sha256(program))
        self.assertEqual(metadata["model_requests"], 1)
        self.assertEqual(metadata["tool_counts"]["submit_bootstrap"], 1)
        self.assertEqual(metadata["replay_status_counts"], {"pass": 1})
        self.assertEqual(
            metadata["verifier_handoff"]["termination_reason"],
            "verifier-triggered-replay-pass",
        )
        self.assertEqual(
            [item["transition"] for item in metadata["verifier_handoff"]["events"]],
            ["candidate-ready", "clean-replay-pass-returned"],
        )

    def test_incomplete_goal_observation_does_not_force_handoff(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        client = FakeClient(
            [FakeResponse(tool_call("1", "submit_and_replay", {"program": program}))]
        )
        compatibility = FakeCompatibilityService()
        scheduled = ScheduledCompatibilityObserver(compatibility)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "handoff")
            _, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                scheduled_observer=scheduled,
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(client.chat.completions.requests[0]["tool_choice"], "auto")
        self.assertEqual(metadata["verifier_handoff"]["trigger_count"], 0)

    def test_ledger_tool_feedback_remains_in_the_continuous_agent_loop(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        responses = [
            FakeResponse(tool_call("1", "check_compatibility", {})),
            FakeResponse(tool_call("2", "submit_and_replay", {"program": program})),
            FakeResponse(
                tool_call(
                    "3",
                    "submit_bootstrap",
                    {"program": program, "summary": "created environment"},
                )
            ),
        ]
        client = FakeClient(responses)
        compatibility = FakeCompatibilityService()
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "ledger")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(compatibility.call_ids, ["1"])
        self.assertEqual(metadata["tool_counts"]["check_compatibility"], 1)
        self.assertEqual(submission["program_sha256"], script_sha256(program))
        second_messages = client.chat.completions.requests[1]["messages"]
        self.assertTrue(
            any(
                item.get("role") == "tool"
                and item.get("name") == "check_compatibility"
                and "operation_constraints_added" in str(item.get("content"))
                for item in second_messages
            )
        )

    def test_scheduled_feedback_is_injected_at_all_frozen_triggers(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        responses = [
            FakeResponse(tool_call("1", "envbench_shell", {"command": "true"})),
            FakeResponse(tool_call("2", "envbench_shell", {"command": "true"})),
            FakeResponse(tool_call("3", "envbench_shell", {"command": "true"})),
            FakeResponse(tool_call("4", "submit_and_replay", {"program": program})),
            FakeResponse(
                tool_call(
                    "5",
                    "submit_bootstrap",
                    {"program": program, "summary": "created environment"},
                )
            ),
        ]
        client = FakeClient(responses)
        compatibility = FakeCompatibilityService()
        scheduled = ScheduledCompatibilityObserver(compatibility, cadence=2)  # type: ignore[arg-type]
        with tempfile.TemporaryDirectory() as directory:
            trajectory = Path(directory) / "trajectory.jsonl"
            runner = self._runner(Path(directory), "scheduled")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                compatibility_service=compatibility,  # type: ignore[arg-type]
                scheduled_observer=scheduled,
                trajectory_path=trajectory,
            )
            events = [
                json.loads(line)
                for line in trajectory.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(
            compatibility.call_ids,
            [
                "scheduled-initial-1",
                "scheduled-periodic-2",
                "scheduled-pre-replay-dirty-3",
            ],
        )
        self.assertEqual(submission["program_sha256"], script_sha256(program))
        schedule = metadata["scheduled_observation"]
        self.assertTrue(schedule["schedule_compliant"])
        self.assertEqual(
            schedule["trigger_counts"],
            {"initial": 1, "periodic": 1, "pre-replay-dirty": 1},
        )
        self.assertEqual(metadata["tool_counts"]["check_compatibility"], 0)
        first_messages = client.chat.completions.requests[0]["messages"]
        self.assertTrue(
            any(
                item.get("role") == "user"
                and '\"trigger\": \"initial\"' in str(item.get("content"))
                for item in first_messages
            )
        )
        periodic_messages = client.chat.completions.requests[2]["messages"]
        self.assertTrue(
            any(
                item.get("role") == "tool"
                and "scheduled_compatibility_observation" in str(item.get("content"))
                for item in periodic_messages
            )
        )
        replay_messages = client.chat.completions.requests[4]["messages"]
        self.assertTrue(
            any(
                item.get("role") == "tool"
                and "pre-replay-dirty" in str(item.get("content"))
                for item in replay_messages
            )
        )
        observations = [
            item for item in events if item.get("event") == "compatibility_observation"
        ]
        self.assertEqual(
            [item["trigger"] for item in observations],
            ["initial", "periodic", "pre-replay-dirty"],
        )

    def test_flash_0731_is_pinned_without_enabling_moving_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            options = runner.request_options(
                DEEPSEEK_V4_FLASH_0731,
                [{"role": "user", "content": "x"}],
            )

        self.assertEqual(options["model"], "deepseek/deepseek-v4-flash-0731")
        self.assertIn(DEEPSEEK_V4_PRO, SUPPORTED_DEEPSEEK_MODELS)
        self.assertIn(DEEPSEEK_V4_FLASH_0731, SUPPORTED_DEEPSEEK_MODELS)
        self.assertNotIn(
            "~deepseek/deepseek-v4-flash-latest",
            SUPPORTED_DEEPSEEK_MODELS,
        )

    def test_request_options_forward_seed_only_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            seeded = runner.request_options(
                DEEPSEEK_V4_FLASH_0731,
                [{"role": "user", "content": "x"}],
                seed=12345,
            )
            unseeded = runner.request_options(
                DEEPSEEK_V4_FLASH_0731,
                [{"role": "user", "content": "x"}],
            )

        self.assertEqual(seeded["seed"], 12345)
        self.assertNotIn("seed", unseeded)
        self.assertEqual(
            _request_contract(seeded),
            {
                "model": DEEPSEEK_V4_FLASH_0731,
                "seed": 12345,
                "seed_forwarded": True,
                "max_tokens": 4096,
                "tool_choice": "auto",
                "reasoning": {"effort": "xhigh"},
                "provider": {
                    "require_parameters": True,
                    "allow_fallbacks": False,
                },
            },
        )

    def test_prompt_defines_a_path_independent_submission_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            prompt = runner._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertIn("absolute path may", prompt)
        self.assertIn("do not hardcode the construction path", prompt)
        self.assertIn("does not reuse the construction package cache", prompt)
        self.assertIn("submit it promptly", prompt)

    def test_provider_order_is_explicitly_injected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            with mock.patch.dict(
                os.environ, {"OPENROUTER_PROVIDER_ORDER": "cloudflare"}
            ):
                policy = runner._provider_policy()

        self.assertEqual(policy["order"], ["cloudflare"])
        self.assertFalse(policy["allow_fallbacks"])

    def test_retryable_provider_errors_use_frozen_backoff(self) -> None:
        class RateLimitError(Exception):
            pass

        class FlakyCompletions:
            def __init__(self) -> None:
                self.calls = 0

            def create(self, **options: object) -> FakeResponse:
                del options
                self.calls += 1
                if self.calls < 3:
                    raise RateLimitError("shared pool busy")
                return FakeResponse()

        completions = FlakyCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            trajectory = Path(directory) / "trajectory.jsonl"
            with mock.patch(
                "envsolve_harness.runners.openrouter_agent.time.sleep"
            ) as sleep:
                response = runner._provider_request(
                    client,
                    {"model": DEEPSEEK_V4_PRO, "seed": 31415},
                    trajectory,
                    request_index=7,
                )

            progress = _trajectory_progress(trajectory)
            events = [
                json.loads(line)
                for line in trajectory.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIsInstance(response, FakeResponse)
        self.assertEqual(completions.calls, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 10])
        self.assertEqual(progress["model_requests"], 7)
        self.assertEqual(progress["provider_attempts"], 3)
        self.assertEqual(progress["provider_error_count"], 2)
        self.assertEqual(
            [event["request_contract"]["seed"] for event in events],
            [31415, 31415, 31415],
        )
        self.assertTrue(
            all(event["request_contract"]["seed_forwarded"] for event in events)
        )

    def test_empty_provider_response_uses_frozen_backoff(self) -> None:
        class EmptyResponse:
            choices: list[object] = []

            def model_dump(self, mode: str = "json") -> dict[str, object]:
                del mode
                return {"id": "empty", "choices": []}

        completions = FakeCompletions([EmptyResponse(), FakeResponse()])  # type: ignore[list-item]
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "none")
            trajectory = Path(directory) / "trajectory.jsonl"
            with mock.patch(
                "envsolve_harness.runners.openrouter_agent.time.sleep"
            ) as sleep:
                response = runner._provider_request(
                    client,
                    {"model": DEEPSEEK_V4_PRO},
                    trajectory,
                    request_index=4,
                )

            progress = _trajectory_progress(trajectory)

        self.assertIsInstance(response, FakeResponse)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2])
        self.assertEqual(progress["provider_attempts"], 2)
        self.assertEqual(progress["provider_error_count"], 1)

    def test_continuous_loop_replays_then_submits_exact_certified_hash(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        responses = [
            FakeResponse(tool_call("1", "envbench_shell", {"command": "true"})),
            FakeResponse(tool_call("2", "submit_and_replay", {"program": program})),
            FakeResponse(
                tool_call(
                    "3",
                    "submit_bootstrap",
                    {"program": program, "summary": "created a virtual environment"},
                )
            ),
        ]
        client = FakeClient(responses)
        terminal = FakeTerminalServer()
        replay = FakeReplayService(program)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=terminal,  # type: ignore[arg-type]
                replay_service=replay,  # type: ignore[arg-type]
                trajectory_path=Path(directory) / "trajectory.jsonl",
                seed=9173,
            )

        self.assertEqual(submission["program_sha256"], script_sha256(program))
        self.assertEqual(metadata["model_requests"], 3)
        self.assertEqual(metadata["token_usage"]["total_tokens"], 45)
        self.assertEqual(metadata["tool_counts"]["submit_and_replay"], 1)
        second_messages = client.chat.completions.requests[1]["messages"]
        self.assertTrue(any(item.get("role") == "tool" for item in second_messages))
        self.assertEqual(
            [request["seed"] for request in client.chat.completions.requests],
            [9173, 9173, 9173],
        )

    def test_atomic_failure_returns_to_same_session_then_pass_finishes(self) -> None:
        first_program = "false"
        second_program = "python -m venv .venv\nsource .venv/bin/activate"

        class FailThenPassReplay(FakeReplayService):
            def __init__(self) -> None:
                super().__init__(second_program)
                self.programs: list[str] = []

            def submit(self, program: str) -> dict[str, object]:
                self.programs.append(program)
                if len(self.programs) == 1:
                    return {
                        "status": "fail",
                        "phase": "clean-replay",
                        "replay_id": "replay-1",
                        "program_sha256": script_sha256(program),
                        "verification": {
                            "summary": "bootstrap failed",
                            "bootstrap": {
                                "exit_code": 1,
                                "stdout": "",
                                "stderr": "missing executable",
                                "duration_seconds": 1.0,
                            },
                            "counterexamples": {"json": "[]", "truncated": False},
                            "details": {"json": "{}", "truncated": False},
                        },
                    }
                return super().submit(program)

        client = FakeClient(
            [
                FakeResponse(
                    tool_call(
                        "1",
                        "submit_bootstrap",
                        {"program": first_program, "summary": "first attempt"},
                    )
                ),
                FakeResponse(
                    tool_call(
                        "2",
                        "submit_bootstrap",
                        {"program": second_program, "summary": "repaired attempt"},
                    )
                ),
            ]
        )
        replay = FailThenPassReplay()
        with tempfile.TemporaryDirectory() as directory:
            trajectory = Path(directory) / "trajectory.jsonl"
            runner = self._runner(Path(directory), "atomic")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=replay,  # type: ignore[arg-type]
                trajectory_path=trajectory,
            )
            progress = _trajectory_progress(trajectory)

        self.assertEqual(replay.programs, [first_program, second_program])
        self.assertEqual(submission["program_sha256"], script_sha256(second_program))
        self.assertEqual(metadata["model_requests"], 2)
        self.assertEqual(metadata["tool_counts"]["submit_bootstrap"], 2)
        self.assertEqual(metadata["tool_counts"]["submit_and_replay"], 0)
        self.assertEqual(metadata["replay_status_counts"], {"fail": 1, "pass": 1})
        self.assertEqual(
            metadata["atomic_submission"]["termination_reason"],
            "atomic-submit-clean-replay-pass",
        )
        self.assertEqual(progress["replay_status_counts"], {"fail": 1, "pass": 1})
        self.assertTrue(
            any(
                item.get("role") == "tool"
                and item.get("name") == "submit_bootstrap"
                and "missing executable" in str(item.get("content"))
                for item in client.chat.completions.requests[1]["messages"]
            )
        )
        self.assertEqual(
            [request["tool_choice"] for request in client.chat.completions.requests],
            ["auto", "auto"],
        )

    def test_atomic_invalid_candidate_does_not_start_clean_replay(self) -> None:
        replay = FakeReplayService("unused")
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "atomic")
            payload, submission, status = runner._atomic_submit(
                {"program": "", "summary": "invalid"},
                replay,  # type: ignore[arg-type]
            )

        self.assertIsNone(submission)
        self.assertIsNone(status)
        self.assertFalse(payload["accepted"])
        self.assertEqual(
            payload["atomic_submission"],
            {"accepted": False, "replayed": False},
        )
        self.assertEqual(replay.certified_programs, [])

    def test_incumbent_survives_a_later_provider_failure(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        client = FakeClient(
            [
                FakeResponse(
                    tool_call("1", "submit_and_replay", {"program": program})
                ),
            ]
        )
        replay = FakeReplayService(program)
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "incumbent")
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=replay,  # type: ignore[arg-type]
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(submission["program_sha256"], script_sha256(program))
        self.assertTrue(metadata["certified_incumbent"]["fallback_used"])
        self.assertEqual(metadata["certified_incumbent"]["update_count"], 1)
        self.assertEqual(
            metadata["certified_incumbent"]["first_certification_request"],
            1,
        )
        self.assertEqual(
            metadata["agent_termination"]["reason"],
            "provider-request-failure",
        )
        second_messages = client.chat.completions.requests[1]["messages"]
        incumbent_message = next(
            item
            for item in second_messages
            if item.get("role") == "tool"
            and "incumbent_update" in str(item.get("content"))
        )
        incumbent_payload = json.loads(str(incumbent_message["content"]))
        self.assertTrue(incumbent_payload["incumbent_update"]["accepted"])

    def test_incumbent_is_returned_at_the_request_safety_cap(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        client = FakeClient(
            [
                FakeResponse(
                    tool_call("1", "submit_and_replay", {"program": program})
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "incumbent")
            runner.max_iterations = 1
            submission, metadata = runner._agent_loop(
                client=client,
                model=DEEPSEEK_V4_PRO,
                prompt="prompt",
                terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                trajectory_path=Path(directory) / "trajectory.jsonl",
            )

        self.assertEqual(submission["program_sha256"], script_sha256(program))
        self.assertEqual(metadata["model_requests"], 1)
        self.assertEqual(
            metadata["agent_termination"]["reason"],
            "agent-request-safety-cap",
        )

    def test_soft_replay_does_not_gain_incumbent_fallback(self) -> None:
        program = "python -m venv .venv\nsource .venv/bin/activate"
        client = FakeClient(
            [
                FakeResponse(
                    tool_call("1", "submit_and_replay", {"program": program})
                )
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            with self.assertRaises(IndexError):
                runner._agent_loop(
                    client=client,
                    model=DEEPSEEK_V4_PRO,
                    prompt="prompt",
                    terminal_server=FakeTerminalServer(),  # type: ignore[arg-type]
                    replay_service=FakeReplayService(program),  # type: ignore[arg-type]
                    trajectory_path=Path(directory) / "trajectory.jsonl",
                )

    def test_treatment_rejects_uncertified_final_program(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            payload, submission = runner._submit(
                {"program": "python -m pip install -e .", "summary": "install"},
                FakeReplayService("different"),  # type: ignore[arg-type]
            )

        self.assertFalse(payload["accepted"])
        self.assertIn("has not passed", payload["reason"])
        self.assertIsNone(submission)

    def test_event_log_redacts_openrouter_credentials(self) -> None:
        secret = "sk-or-v1-abcdefghijklmnopqrstuvwxyz123456"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            runner = self._runner(Path(directory), "none")
            runner._append_event(path, {"value": secret})
            encoded = path.read_text(encoding="utf-8")

        self.assertNotIn(secret, encoded)
        self.assertIn("[REDACTED]", encoded)

    def test_trajectory_progress_survives_terminal_provider_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.jsonl"
            runner = self._runner(Path(directory), "soft")
            runner._append_event(
                path,
                {
                    "event": "provider_response",
                    "request_index": 1,
                    "attempt": 1,
                    "response": {
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                            "cost": 0.02,
                        }
                    },
                },
            )
            runner._append_event(
                path,
                {
                    "event": "tool_result",
                    "request_index": 1,
                    "tool_name": "submit_and_replay",
                    "result": {"status": "fail"},
                },
            )
            for attempt in (1, 2):
                runner._append_event(
                    path,
                    {
                        "event": "provider_error",
                        "request_index": 2,
                        "attempt": attempt,
                    },
                )

            progress = _trajectory_progress(path)

        self.assertEqual(progress["model_requests"], 2)
        self.assertEqual(progress["provider_attempts"], 3)
        self.assertEqual(progress["provider_error_count"], 2)
        self.assertEqual(progress["token_usage"]["total_tokens"], 15)
        self.assertEqual(progress["token_usage"]["cost"], 0.02)
        self.assertEqual(progress["tool_counts"], {"submit_and_replay": 1})
        self.assertEqual(progress["replay_status_counts"], {"fail": 1})


class ReplayFeedbackTest(unittest.TestCase):
    def test_failure_becomes_advisory_constraint_with_raw_evidence(self) -> None:
        replay = {
            "status": "fail",
            "phase": "clean-replay",
            "replay_id": "replay-1",
            "program_sha256": "abc",
            "verification": {
                "summary": "one import is missing",
                "bootstrap": {
                    "exit_code": 0,
                    "stdout": "goal output",
                    "stderr": "",
                    "duration_seconds": 1.0,
                },
                "counterexamples": {
                    "json": (
                        '[{"kind":"missing-import","value":'
                        '{"required":"import succeeds","observed":"ModuleNotFoundError"},'
                        '"confidence":1.0}]'
                    ),
                    "truncated": False,
                },
                "details": {"json": "{}", "truncated": False},
            },
        }

        feedback = normalize_replay_feedback(replay)

        self.assertTrue(feedback["advisory_only"])
        self.assertEqual(feedback["retryability"], "agent_repair")
        self.assertEqual(
            feedback["soft_constraint"]["required_condition"],
            "import succeeds",
        )
        self.assertEqual(
            feedback["soft_constraint"]["observed_state"],
            "ModuleNotFoundError",
        )
        self.assertEqual(feedback["raw_evidence"]["bootstrap"]["stdout"], "goal output")


if __name__ == "__main__":
    unittest.main()
