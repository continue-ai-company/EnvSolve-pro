from __future__ import annotations

import unittest

from envsolve.v0.verification import (
    V0VerifierResult,
    completion_from_trajectory,
    parse_verifier_result,
)


def call(name: str, identifier: str) -> dict:
    return {
        "node": "agent",
        "messages": [
            {"message_content": {"tool_calls": [{"name": name, "id": identifier}]}}
        ],
    }


def result(identifier: str, value: V0VerifierResult) -> dict:
    return {
        "node": "tools",
        "messages": [
            {
                "message_content": {
                    "tool_call_id": identifier,
                    "content": value.to_json(),
                }
            }
        ],
    }


class V0VerificationTests(unittest.TestCase):
    def test_requires_verifier(self) -> None:
        decision = completion_from_trajectory([call("execute_bash_command", "bash")])
        self.assertFalse(decision.passed)
        self.assertEqual(decision.reason, "verifier was never called")

    def test_passing_verifier_closes_trajectory(self) -> None:
        value = V0VerifierResult(True, 0, "No broken requirements found")
        decision = completion_from_trajectory(
            [call("execute_bash_command", "bash"), call("verify_environment", "v"), result("v", value)]
        )
        self.assertTrue(decision.passed)

    def test_failed_verifier_does_not_close_trajectory(self) -> None:
        value = V0VerifierResult(False, 1, "missing dependency")
        decision = completion_from_trajectory([call("verify_environment", "v"), result("v", value)])
        self.assertFalse(decision.passed)
        self.assertEqual(decision.reason, "last verifier call failed")

    def test_bash_after_pass_requires_reverification(self) -> None:
        value = V0VerifierResult(True, 0, "ok")
        decision = completion_from_trajectory(
            [call("verify_environment", "v"), result("v", value), call("execute_bash_command", "bash")]
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.bash_calls_after_last_verifier, 1)

    def test_inconsistent_result_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "disagree"):
            parse_verifier_result(
                '{"schema":"envsolve-v0-verifier-v1","passed":true,"exit_code":1,"output":"bad"}'
            )


if __name__ == "__main__":
    unittest.main()
