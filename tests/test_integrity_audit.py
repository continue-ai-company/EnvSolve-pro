from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from envsolve.runtime.integrity import (
    IMPORT_ALIAS_AUDIT_MARKER,
    marked_json_payload,
    python_import_alias_audit_command,
)
from envsolve.runtime.stateful_integrity_v2 import (
    python_source_provenance_audit_command,
)


def _run_audit(
    project: Path,
    pythonpath: Path,
    *,
    reject_project_namespace_overlays: bool = False,
) -> dict[str, object]:
    command = (
        python_source_provenance_audit_command(str(project))
        if reject_project_namespace_overlays
        else python_import_alias_audit_command(str(project))
    )
    environment = os.environ.copy()
    environment["PATH"] = (
        str(Path(sys.executable).parent)
        + os.pathsep
        + environment.get("PATH", "")
    )
    process = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"export PYTHONPATH={shlex.quote(str(pythonpath))}; "
                f"{command}"
            ),
        ],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    payload = marked_json_payload(process.stdout, IMPORT_ALIAS_AUDIT_MARKER)
    assert payload is not None
    return payload


class ImportAliasAuditTests(unittest.TestCase):
    def test_ignores_pythonpath_stdlib_shadowing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            project = tmp_path / "project"
            poison = tmp_path / "python2-stdlib"
            project.mkdir()
            poison.mkdir()
            (poison / "pathlib.py").write_text(
                "raise RuntimeError('candidate path polluted the audit')\n",
                encoding="utf-8",
            )

            payload = _run_audit(project, poison)

            self.assertIs(payload["valid"], True)
            self.assertEqual(payload["violations"], [])

    def test_still_checks_pythonpath_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            project = tmp_path / "project"
            package = project / "real_package"
            pythonpath = tmp_path / "candidate-pythonpath"
            package.mkdir(parents=True)
            pythonpath.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (pythonpath / "synthetic_alias").symlink_to(
                package,
                target_is_directory=True,
            )

            payload = _run_audit(project, pythonpath)

            self.assertIs(payload["valid"], False)
            self.assertEqual(
                payload["violations"],
                [
                    {
                        "alias": "synthetic_alias",
                        "link": str(pythonpath / "synthetic_alias"),
                        "reason": (
                            "undeclared import alias resolves into project source"
                        ),
                        "target": str(package.resolve()),
                    }
                ],
            )
            json.dumps(payload, ensure_ascii=True)

    def test_v2_rejects_external_project_namespace_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            project = tmp_path / "project"
            package = project / "micropy"
            pythonpath = tmp_path / "old-distribution"
            overlay = pythonpath / "micropy"
            package.mkdir(parents=True)
            overlay.mkdir(parents=True)
            (package / "__init__.py").write_text(
                "from micropy.cli import VALUE\n",
                encoding="utf-8",
            )
            (overlay / "__init__.py").write_text(
                "from micropy.cli import VALUE\n",
                encoding="utf-8",
            )
            (overlay / "cli.py").write_text("VALUE = 'old'\n", encoding="utf-8")

            legacy = _run_audit(project, pythonpath)
            protected = _run_audit(
                project,
                pythonpath,
                reject_project_namespace_overlays=True,
            )

            self.assertIs(legacy["valid"], True)
            self.assertEqual(legacy["violations"], [])
            self.assertIs(protected["valid"], False)
            self.assertEqual(
                protected["violations"],
                [
                    {
                        "alias": "micropy",
                        "divergent_sources": ["cli.py"],
                        "path": str(overlay.resolve()),
                        "reason": (
                            "external import search root contributes divergent "
                            "project source"
                        ),
                        "search_root": str(pythonpath.resolve()),
                    }
                ],
            )

    def test_v2_allows_unrelated_external_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            project = tmp_path / "project"
            package = project / "current_project"
            pythonpath = tmp_path / "installed-dependencies"
            dependency = pythonpath / "third_party"
            package.mkdir(parents=True)
            dependency.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (dependency / "__init__.py").write_text("", encoding="utf-8")

            payload = _run_audit(
                project,
                pythonpath,
                reject_project_namespace_overlays=True,
            )

            self.assertIs(payload["valid"], True)
            self.assertEqual(payload["violations"], [])

    def test_v2_allows_source_identical_project_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            project = tmp_path / "project"
            package = project / "current_project"
            pythonpath = tmp_path / "installed-project"
            installed = pythonpath / "current_project"
            package.mkdir(parents=True)
            installed.mkdir(parents=True)
            for root in (package, installed):
                (root / "__init__.py").write_text(
                    "VALUE = 'current'\n",
                    encoding="utf-8",
                )

            payload = _run_audit(
                project,
                pythonpath,
                reject_project_namespace_overlays=True,
            )

            self.assertIs(payload["valid"], True)
            self.assertEqual(payload["violations"], [])


if __name__ == "__main__":
    unittest.main()
