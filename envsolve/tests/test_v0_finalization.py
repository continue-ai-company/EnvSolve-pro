from __future__ import annotations

import unittest

from envsolve.v0.finalization import finalize_v0_trajectory
from envsolve.v0.verification import V0VerifierResult


class V0FinalizationTests(unittest.TestCase):
    def test_verified_mutation_is_distilled_without_verifier(self) -> None:
        verifier = V0VerifierResult(True, 0, "ok").to_json()
        records = [
            {"node": "agent", "messages": [{"message_content": {"tool_calls": [
                {"name": "execute_bash_command", "id": "b"}
            ]}}]},
            {"node": "agent", "messages": [{"message_content": {"tool_calls": [
                {"name": "verify_environment", "id": "v"}
            ]}}]},
            {"node": "tools", "messages": [{"message_content": {
                "tool_call_id": "v", "content": verifier
            }}]},
            {"node": "commands_history", "commands": [
                {"command": "python -m pip install -e .", "exit_code": 0}
            ]},
        ]
        result = finalize_v0_trajectory(records, "owner__repo@rev")
        self.assertIsNone(result.error)
        self.assertEqual(result.distillation.script, "python -m pip install -e .\n")
        self.assertNotIn("pip check", result.distillation.script)

    def test_unverified_trajectory_never_distills(self) -> None:
        records = [{"node": "commands_history", "commands": [
            {"command": "python -m pip install -e .", "exit_code": 0}
        ]}]
        result = finalize_v0_trajectory(records, "owner__repo@rev")
        self.assertEqual(result.error, "verifier was never called")
        self.assertIsNone(result.distillation)


if __name__ == "__main__":
    unittest.main()
