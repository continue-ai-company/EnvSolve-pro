from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.codex.minimal_b_mcp import script_sha256
from envsolve_harness.replay_feedback import normalize_replay_feedback
from envsolve_harness.runners.openrouter_agent import (
    DEEPSEEK_V4_PRO,
    OpenRouterAgentRunner,
    _EpisodePackageCacheRunCommand,
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
            },
            "certificate": {"program_sha256": script_sha256(program)},
        }


class OpenRouterAgentRunnerTest(unittest.TestCase):
    def test_episode_package_cache_is_added_only_to_docker_create(self) -> None:
        calls: list[list[str]] = []

        def run(command: list[str], **kwargs: object) -> SimpleNamespace:
            del kwargs
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory) / "cache"
            adapter = _EpisodePackageCacheRunCommand(cache_root, run)
            adapter(["git", "status"])
            adapter(["docker", "image", "inspect", "image"])
            adapter(["docker", "create", "image"])
            adapter(["docker", "start", "container-1"])
            cache_mode = cache_root.stat().st_mode & 0o777

        self.assertEqual(calls[0], ["git", "status"])
        self.assertEqual(calls[1], ["docker", "image", "inspect", "image"])
        self.assertEqual(calls[2][0:2], ["docker", "create"])
        self.assertIn("dst=/root/.cache", calls[2][3])
        self.assertEqual(calls[3], ["docker", "start", "container-1"])
        self.assertEqual(
            calls[4],
            [
                "docker",
                "exec",
                "--user",
                "0:0",
                "container-1",
                "chown",
                "0:0",
                "/root/.cache",
            ],
        )
        self.assertEqual(cache_mode, 0o777)

    def test_existing_episode_cache_is_reused_without_chmod(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory) / "cache"
            cache_root.mkdir()
            with mock.patch.object(Path, "chmod") as chmod:
                adapter = _EpisodePackageCacheRunCommand(cache_root)

        self.assertEqual(adapter.cache_root, cache_root.resolve())
        chmod.assert_not_called()

    def _runner(self, root: Path, replay_mode: str) -> OpenRouterAgentRunner:
        return OpenRouterAgentRunner(
            harness_root=root,
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
            workspace_preconditions=(),
            goal_contract=ExecutableGoalContract(
                "goal",
                "Require success",
                "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
            ),
        )

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

    def test_prompt_defines_a_path_independent_submission_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory), "soft")
            prompt = runner._prompt(
                SimpleNamespace(repository="owner/repo", revision="abc")
            )

        self.assertIn("absolute path may", prompt)
        self.assertIn("do not hardcode the construction path", prompt)
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
                    {"model": DEEPSEEK_V4_PRO},
                    trajectory,
                    request_index=7,
                )

            progress = _trajectory_progress(trajectory)

        self.assertIsInstance(response, FakeResponse)
        self.assertEqual(completions.calls, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 10])
        self.assertEqual(progress["model_requests"], 7)
        self.assertEqual(progress["provider_attempts"], 3)
        self.assertEqual(progress["provider_error_count"], 2)

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
            )

        self.assertEqual(submission["program_sha256"], script_sha256(program))
        self.assertEqual(metadata["model_requests"], 3)
        self.assertEqual(metadata["token_usage"]["total_tokens"], 45)
        self.assertEqual(metadata["tool_counts"]["submit_and_replay"], 1)
        second_messages = client.chat.completions.requests[1]["messages"]
        self.assertTrue(any(item.get("role") == "tool" for item in second_messages))

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
