from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from envsolve.context import build_repair_context
from envsolve.discovery.apt_file import parse_provider_environment
from envsolve.discovery.packages_policy import UbuntuPackagesDiscoveryPolicy
from envsolve.discovery.ubuntu_packages import parse_ubuntu_contents_response
from envsolve.solver import CommandResult, SolverStateSession, StatefulSolverLoop


CASE = {
    "case_id": "synthetic:ubuntu-packages-discovery",
    "repository": "owner/repo",
    "revision": "abc",
    "language": "infrastructure",
    "split": "synthetic",
    "tags": [],
}
ENVIRONMENT_OUTPUT = (
    "path\t/usr/local/bin:/usr/bin:/bin\n"
    "architecture\tarm64\n"
    "os\tubuntu\tjammy\n"
)
HTML = """<!DOCTYPE html>
<html><body><table>
<tr><td class="file">/usr/bin/<span>sample_tool</span></td>
<td><a href="/jammy/sample-dev">sample-dev</a></td></tr>
<tr><td class="file">/usr/lib/sample/<span>sample_tool</span></td>
<td><a href="/jammy/sample-server-dev">sample-server-dev</a></td></tr>
</table></body></html>"""


def response_envelope(body: str = HTML, final_url: str | None = None) -> str:
    query = urlencode(
        {
            "searchon": "contents",
            "keywords": "sample_tool",
            "mode": "exactfilename",
            "suite": "jammy",
            "arch": "arm64",
        }
    )
    url = f"https://packages.ubuntu.com/search?{query}"
    encoded = body.encode()
    return json.dumps(
        {
            "request_url": url,
            "final_url": final_url or url,
            "status": 200,
            "bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "body": body,
        },
        separators=(",", ":"),
    )


class ScriptedExecutor:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        if command.startswith("printf 'path"):
            return CommandResult(0, ENVIRONMENT_OUTPUT)
        if "command -v -- sample_tool" in command:
            return CommandResult(0, "absent\n")
        if "urllib.request" in command:
            return CommandResult(0, response_envelope())
        if command.startswith("if apt-cache show"):
            return CommandResult(0, "present\tsample-dev\n")
        return CommandResult(0)


class UbuntuContentsParserTest(unittest.TestCase):
    def test_parser_keeps_only_exact_path_reachable_package(self) -> None:
        environment = parse_provider_environment(ENVIRONMENT_OUTPUT)
        result = parse_ubuntu_contents_response(
            response_envelope(),
            "sample_tool",
            environment,
            12_000,
        )

        self.assertEqual(result.packages, ("sample-dev",))
        self.assertEqual(result.candidates[0].path, "/usr/bin/sample_tool")
        self.assertEqual(result.rejected[0]["reason"], "not_on_path")

    def test_parser_rejects_cross_host_redirect(self) -> None:
        environment = parse_provider_environment(ENVIRONMENT_OUTPUT)
        with self.assertRaisesRegex(ValueError, "fixed HTTPS endpoint"):
            parse_ubuntu_contents_response(
                response_envelope(final_url="https://example.com/search"),
                "sample_tool",
                environment,
                12_000,
            )


class UbuntuPackagesPolicyTest(unittest.TestCase):
    def test_policy_emits_only_apt_verified_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = SolverStateSession(root / "state.jsonl", root / "snapshot.json", CASE)
            session.record_evidence(
                "context-system-manager-observation",
                "synthetic",
                {"manager": "apt-get", "present": True, "path": "/usr/bin/apt-get"},
                evidence_id="evidence-context-system-manager-apt-get",
            )
            executor = ScriptedExecutor()
            result = StatefulSolverLoop(
                session,
                executor,
                max_actions=6,
                goal_id="goal-packages-discovery",
            ).run(
                UbuntuPackagesDiscoveryPolicy(
                    session,
                    "sample_tool",
                    timeout_seconds=120,
                    max_response_bytes=12_000,
                    user_agent="EnvSolve-P4D/1.0 capability-index-research",
                )
            )

            self.assertEqual(result.goal_status, "satisfied")
            self.assertEqual(result.actions_executed, 5)
            context = build_repair_context(session.reconstruct()).context
            self.assertEqual(
                context.capability_packages,
                {"sample_tool": ("sample-dev",)},
            )


if __name__ == "__main__":
    unittest.main()
