from __future__ import annotations

from pathlib import Path
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest

from envsolve_harness.adapters.envbench_goal import (
    envbench_python_goal_contract,
)


class EnvBenchGoalContractTests(unittest.TestCase):
    def test_contract_matches_public_missing_import_criterion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin"
            binary.mkdir()
            python = binary / "python"
            python.write_text(
                "\n".join(
                    (
                        "#!/bin/bash",
                        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then exit 0; fi',
                        (
                            'if [ "$1" = "-m" ] && [ "$2" = "pyright" ] '
                            '&& [ "$3" = "--version" ]; then '
                            'echo "pyright 1.test"; exit 0; fi'
                        ),
                        'if [ "$1" = "-m" ] && [ "$2" = "pyright" ]; then',
                        "cat <<'JSON'",
                        json.dumps(
                            {
                                "generalDiagnostics": [
                                    {
                                        "file": "/data/project/example.py",
                                        "message": 'Import "tomli" could not be resolved',
                                        "rule": "reportMissingImports",
                                        "severity": "error",
                                        "range": {
                                            "start": {"line": 1, "character": 0},
                                            "end": {"line": 1, "character": 5},
                                        },
                                    },
                                    {
                                        "file": "/data/project/example.py",
                                        "message": 'Type of "value" is unknown',
                                        "rule": "reportUnknownVariableType",
                                        "severity": "error",
                                    },
                                ]
                            },
                            sort_keys=True,
                        ),
                        "JSON",
                        "exit 1",
                        "fi",
                        f"exec {shlex.quote(sys.executable)} \"$@\"",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            python.chmod(0o755)
            pyright = binary / "pyright"
            pyright.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            pyright.chmod(0o755)
            report_path = root / "goal-report.json"
            env = {
                **os.environ,
                "ENVSOLVE_PROJECT_ROOT": str(root),
                "ENVSOLVE_GOAL_REPORT": str(report_path),
            }
            program = (
                f"export PATH={shlex.quote(str(binary))}:$PATH\n"
                + envbench_python_goal_contract().program
            )

            process = subprocess.run(
                ["/bin/bash", "-c", program],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "envsolve-goal-report-v1")
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["details"]["issues_count"], 1)
            self.assertEqual(report["details"]["pyright_version"], "pyright 1.test")
            self.assertEqual(
                [item["subject"] for item in report["findings"]],
                ["tomli"],
            )


if __name__ == "__main__":
    unittest.main()
