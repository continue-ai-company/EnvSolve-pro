#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.codex.minimal_b_mcp import (
    REPLAY_SCHEMA,
    CleanReplayService,
    MinimalBMcpServer,
    canonical_script,
    script_sha256,
)


class OneShotCleanReplayService(CleanReplayService):
    """Expose the Minimal B verifier exactly once per Agent session."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.submission_attempts = 0

    def submit(self, program: str) -> dict[str, Any]:
        self.submission_attempts += 1
        if self.submission_attempts == 1:
            return super().submit(program)

        canonical = canonical_script(program)
        result = {
            "schema": REPLAY_SCHEMA,
            "replay_id": f"one-shot-rejected-{self.submission_attempts:04d}",
            "replay_index": self.submission_attempts,
            "program_sha256": script_sha256(canonical),
            "certified": False,
            "status": "replay_limit",
            "phase": "replay-limit",
            "replay_executed": False,
            "reason": "one-shot certification permits exactly one replay submission",
        }
        self._trace(result)
        return result


class OneShotMinimalBMcpServer(MinimalBMcpServer):
    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        response = super().handle(request)
        method = request.get("method")
        if response is None:
            return None
        if method == "initialize":
            response["result"]["serverInfo"] = {
                "name": "envsolve-pro-one-shot-certification",
                "version": "1.0.0",
            }
            response["result"]["instructions"] = (
                "Use envbench_shell for construction work. The submit_and_replay "
                "tool may be called exactly once to certify the complete program in "
                "a distinct clean environment."
            )
        elif method == "tools/list":
            for tool in response["result"]["tools"]:
                if tool.get("name") == self.replay_tool_name:
                    tool["description"] = (
                        "Exactly once, validate and execute one complete self-contained "
                        "bootstrap program in a new clean checkout and container, then "
                        "return public-goal and integrity evidence to this Agent session."
                    )
        elif method == "tools/call":
            result = response.get("result")
            if isinstance(result, dict):
                content = result.get("structuredContent")
                if isinstance(content, dict) and content.get("status") == "replay_limit":
                    result["isError"] = True
        return response


def main() -> int:
    minimal_b_mcp.CleanReplayService = OneShotCleanReplayService
    minimal_b_mcp.MinimalBMcpServer = OneShotMinimalBMcpServer
    return minimal_b_mcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
