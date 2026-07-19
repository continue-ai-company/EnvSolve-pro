from __future__ import annotations

from textwrap import dedent
from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep, RemainingSteps
from langgraph.prebuilt import create_react_agent

from envsolve.v0.verification import PIP_CHECK_COMMAND, V0VerifierResult


class V0AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    is_last_step: IsLastStep
    remaining_steps: RemainingSteps


V0_SYSTEM_PROMPT = dedent(
    """
    You are EnvSolve v0. Configure the Python development environment for the
    repository in the current directory. Inspect project-owned metadata and
    documentation, execute observations and repairs through the bash tool, and
    do not modify application source code.

    Completion is controlled by the verify_environment tool. After you believe
    setup is complete, call verify_environment. If it fails, use its evidence
    to continue diagnosis and repair. You may finish only immediately after a
    passing verifier result. Never claim success without that result. This tool
    is an internal dependency-consistency check, not the benchmark verifier.
    """
).strip()


class VerifierGatedPythonAgent:
    def __init__(self, model: Any, toolkit: Any, max_iterations: int) -> None:
        self.model = model
        self.toolkit = toolkit
        self._max_iterations = max_iterations

    @property
    def max_iterations(self) -> int:
        return 2 * self._max_iterations + 1

    @property
    def configurable_config(self) -> dict[str, Any]:
        return {}

    @property
    def commands_history(self) -> list[dict[str, Any]]:
        return self.toolkit.commands_history

    async def verify_environment(self) -> str:
        output, exit_code = await self.toolkit._execute_bash_command(
            PIP_CHECK_COMMAND,
            add_to_history=False,
        )
        return V0VerifierResult(exit_code == 0, exit_code, output).to_json()

    def get_agent(self):
        tools = [
            *self.toolkit.get_tools(),
            StructuredTool.from_function(
                coroutine=self.verify_environment,
                name="verify_environment",
                description=(
                    "Run the fixed EnvSolve v0 dependency-consistency verifier. "
                    "Call this only after setup; continue repairing if it fails."
                ),
            ),
        ]

        def prompt(state: dict[str, Any]):
            messages = state.get("messages", [])
            return [
                SystemMessage(content=V0_SYSTEM_PROMPT),
                *messages,
            ]

        return create_react_agent(
            model=self.model,
            tools=tools,
            state_schema=V0AgentState,
            prompt=prompt,
        )

    def construct_initial_state(self, repository: str, revision: str, *args, **kwargs):
        return {
            "messages": [
                HumanMessage(content="Configure this repository's Python environment.")
            ]
        }

    @staticmethod
    def process_update_for_trajectory(update: dict[str, Any], *args, **kwargs):
        from inference.src.utils import message_to_info

        if "agent" in update:
            node = "agent"
            messages = update["agent"].get("messages", [])
        elif "tools" in update:
            node = "tools"
            messages = update["tools"].get("messages", [])
        else:
            raise RuntimeError("unexpected EnvSolve v0 graph update")
        return {
            "timestamp": update["timestamp"],
            "node": node,
            "messages": [message_to_info(message) for message in messages],
        }
