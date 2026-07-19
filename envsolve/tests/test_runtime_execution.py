from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.context import build_repair_context
from envsolve.execution import derive_runtime_execution_contract
from envsolve.solver import SolverStateSession


CASE = {
    "case_id": "synthetic:runtime-execution",
    "repository": "owner/repo",
    "revision": "abc",
    "language": "python",
    "split": "synthetic",
    "tags": [],
}


class RuntimeExecutionContractTest(unittest.TestCase):
    @staticmethod
    def session(root: Path, tool_path: str) -> SolverStateSession:
        session = SolverStateSession(
            root / "state.jsonl",
            root / "snapshot.json",
            CASE,
        )
        session.record_evidence(
            "context-tool-observation",
            "synthetic",
            {"tool": "pyenv", "present": True, "path": tool_path},
            evidence_id="evidence-context-tool-pyenv",
        )
        session.record_evidence(
            "context-runtime-root",
            "synthetic",
            {"manager": "pyenv", "root": "/root/.pyenv"},
            evidence_id="evidence-context-runtime-root-pyenv",
        )
        session.record_evidence(
            "context-runtime-inventory",
            "synthetic",
            {"manager": "pyenv", "versions": ["3.11.7"]},
            evidence_id="evidence-context-runtime-pyenv",
        )
        return session

    def test_derives_guarded_pyenv_shim_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory), "/root/.pyenv/bin/pyenv")
            state = session.reconstruct()
            context = build_repair_context(state).context

            contract = derive_runtime_execution_contract(state, context)

            self.assertEqual(contract.path_prepend, ("/root/.pyenv/shims",))
            self.assertEqual(
                contract.required_executable,
                "/root/.pyenv/shims/python",
            )
            wrapped = contract.wrap("python --version")
            self.assertIn("test -x /root/.pyenv/shims/python", wrapped)
            self.assertIn('export PATH=/root/.pyenv/shims:"$PATH"', wrapped)
            self.assertTrue(wrapped.endswith("python --version"))

    def test_uses_probed_root_for_homebrew_tool_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(Path(directory), "/usr/local/pyenv")
            state = session.reconstruct()
            context = build_repair_context(state).context

            contract = derive_runtime_execution_contract(state, context)

            self.assertEqual(contract.path_prepend, ("/root/.pyenv/shims",))


if __name__ == "__main__":
    unittest.main()
