from __future__ import annotations

import unittest

from envsolve.analysis.trajectory import analyze_trajectory_records


def agent(tool_id: str, command: str, reason: str = "test") -> dict:
    return {
        "node": "agent",
        "messages": [
            {
                "message_content": {
                    "tool_calls": [
                        {"id": tool_id, "args": {"command": command, "reason": reason}}
                    ]
                }
            }
        ],
    }


def tool(tool_id: str, output: str) -> dict:
    return {
        "node": "tools",
        "messages": [
            {"message_content": {"tool_call_id": tool_id, "content": output}}
        ],
    }


class TrajectoryAnalysisTests(unittest.TestCase):
    def test_failed_exact_retry_can_recover(self) -> None:
        command = "python -m pip install -e ."
        records = [
            agent("a", command),
            tool("a", "network timeout"),
            agent("b", command),
            tool("b", "installed"),
            {
                "node": "commands_history",
                "commands": [
                    {"command": command, "exit_code": 1},
                    {"command": command, "exit_code": 0},
                ],
            },
        ]

        analysis = analyze_trajectory_records(records)

        self.assertEqual(analysis["exact_retries_after_failure"], 1)
        self.assertEqual(analysis["exact_failure_recoveries"], 1)
        self.assertEqual(analysis["same_output_retries_after_failure"], 0)
        self.assertTrue(analysis["decisions"][1]["recovered_exact_failure"])

    def test_same_failed_output_is_distinguished(self) -> None:
        command = "poetry install"
        records = [
            agent("a", command),
            tool("a", "same error"),
            agent("b", command),
            tool("b", "same   error"),
            {
                "node": "commands_history",
                "commands": [
                    {"command": command, "exit_code": 1},
                    {"command": command, "exit_code": 1},
                ],
            },
        ]

        analysis = analyze_trajectory_records(records)

        self.assertEqual(analysis["same_output_retries_after_failure"], 1)
        self.assertEqual(analysis["exact_failure_recoveries"], 0)

    def test_mismatched_tool_and_history_is_rejected(self) -> None:
        records = [
            agent("a", "ls"),
            tool("a", "output"),
            {"node": "commands_history", "commands": [{"command": "pwd", "exit_code": 0}]},
        ]

        with self.assertRaisesRegex(ValueError, "differ"):
            analyze_trajectory_records(records)


if __name__ == "__main__":
    unittest.main()
