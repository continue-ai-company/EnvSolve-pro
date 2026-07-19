from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any


VERIFIER_SCHEMA = "envsolve-v0-verifier-v1"
PIP_CHECK_COMMAND = "python -m pip check"


@dataclass(frozen=True)
class V0VerifierResult:
    passed: bool
    exit_code: int
    output: str
    schema: str = VERIFIER_SCHEMA

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass(frozen=True)
class V0CompletionDecision:
    passed: bool
    reason: str
    verifier_calls: int
    last_verifier: V0VerifierResult | None
    bash_calls_after_last_verifier: int


def parse_verifier_result(value: str) -> V0VerifierResult:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("v0 verifier output is not JSON") from exc
    if not isinstance(parsed, dict) or parsed.get("schema") != VERIFIER_SCHEMA:
        raise ValueError("v0 verifier output has the wrong schema")
    passed = parsed.get("passed")
    exit_code = parsed.get("exit_code")
    output = parsed.get("output")
    if not isinstance(passed, bool):
        raise ValueError("v0 verifier passed field must be boolean")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ValueError("v0 verifier exit code must be integer")
    if not isinstance(output, str):
        raise ValueError("v0 verifier output field must be text")
    if passed != (exit_code == 0):
        raise ValueError("v0 verifier pass and exit code disagree")
    return V0VerifierResult(passed, exit_code, output)


def completion_from_trajectory(records: list[dict[str, Any]]) -> V0CompletionDecision:
    pending_verifiers: set[str] = set()
    verifier_results: list[tuple[int, V0VerifierResult]] = []
    bash_call_positions: list[int] = []
    position = 0
    for record in records:
        messages = record.get("messages")
        if not isinstance(messages, list):
            continue
        for message in messages:
            content = message.get("message_content") if isinstance(message, dict) else None
            if not isinstance(content, dict):
                continue
            calls = content.get("tool_calls")
            if isinstance(calls, list):
                for call in calls:
                    if not isinstance(call, dict):
                        continue
                    position += 1
                    name = call.get("name")
                    identifier = call.get("id")
                    if name == "verify_environment" and isinstance(identifier, str):
                        pending_verifiers.add(identifier)
                    elif name == "execute_bash_command":
                        bash_call_positions.append(position)
            identifier = content.get("tool_call_id")
            if isinstance(identifier, str) and identifier in pending_verifiers:
                verifier_results.append(
                    (position, parse_verifier_result(str(content.get("content", ""))))
                )
                pending_verifiers.remove(identifier)
    if pending_verifiers:
        return V0CompletionDecision(
            False,
            "verifier tool call has no result",
            len(verifier_results) + len(pending_verifiers),
            verifier_results[-1][1] if verifier_results else None,
            0,
        )
    if not verifier_results:
        return V0CompletionDecision(False, "verifier was never called", 0, None, 0)
    last_position, last = verifier_results[-1]
    bash_after = sum(item > last_position for item in bash_call_positions)
    if not last.passed:
        return V0CompletionDecision(
            False,
            "last verifier call failed",
            len(verifier_results),
            last,
            bash_after,
        )
    if bash_after:
        return V0CompletionDecision(
            False,
            "bash actions occurred after the last passing verifier",
            len(verifier_results),
            last,
            bash_after,
        )
    return V0CompletionDecision(
        True,
        "last action-state boundary is verified",
        len(verifier_results),
        last,
        0,
    )

