from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from textwrap import dedent
import unittest


ROOT = Path(__file__).resolve().parents[2]


class V0InferenceEntrypointTests(unittest.TestCase):
    def test_agent_initial_state_writes_the_message_channel(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from unittest.mock import Mock; "
                    "from envsolve.v0.agent import VerifierGatedPythonAgent; "
                    "state=VerifierGatedPythonAgent(Mock(), Mock(), 3)"
                    ".construct_initial_state('owner/repo', 'revision'); "
                    "assert len(state['messages']) == 1; "
                    "assert 'Configure' in state['messages'][0].content"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_agent_graph_reaches_the_model_offline(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "-c",
                dedent(
                    """
                    from unittest.mock import Mock
                    from langchain_core.language_models.chat_models import BaseChatModel
                    from langchain_core.messages import AIMessage
                    from langchain_core.outputs import ChatGeneration, ChatResult
                    from envsolve.v0.agent import VerifierGatedPythonAgent

                    class FakeModel(BaseChatModel):
                        calls: int = 0

                        @property
                        def _llm_type(self):
                            return "envsolve-test"

                        def bind_tools(self, tools, **kwargs):
                            return self

                        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                            self.calls += 1
                            return ChatResult(generations=[
                                ChatGeneration(message=AIMessage(content="done"))
                            ])

                    toolkit = Mock()
                    toolkit.get_tools.return_value = []
                    toolkit.commands_history = []
                    model = FakeModel()
                    agent = VerifierGatedPythonAgent(model, toolkit, 3)
                    result = agent.get_agent().invoke(
                        agent.construct_initial_state("owner/repo", "revision"),
                        {"recursion_limit": 7},
                    )
                    assert model.calls == 1
                    assert result["messages"][-1].content == "done"
                    """
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_direct_file_help_does_not_require_envbench_checkout(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "envsolve/tools/run_v0_inference.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("minimal EnvSolve v0", process.stdout)


if __name__ == "__main__":
    unittest.main()
