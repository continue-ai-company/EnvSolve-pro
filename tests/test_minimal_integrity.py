from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock
import venv
import zipfile

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import (
    CommandResult,
    DeploymentCandidate,
    ExecutableVerification,
    FeedbackChannel,
)
from envsolve_harness.integrity.minimal import (
    MinimalIntegrityGoalVerifier,
    _PROVIDER_AUDIT_SCHEMA,
    _PROVIDER_BASELINE_MARKER,
    _PROVIDER_POST_MARKER,
    _UNOWNED_PROVIDER_AUDIT,
    _novel_unowned_provider_violations,
    _provider_audit_command,
    inspect_minimal_repository_integrity,
)
from envsolve.runtime.integrity import marked_json_payload
from envsolve_harness.scripts.minimal_integrity import MinimalIntegrityCandidateValidator


class MinimalIntegrityTest(unittest.TestCase):
    def test_candidate_contract_declares_dynamic_project_root(self) -> None:
        contract = " ".join(MinimalIntegrityCandidateValidator.prompt_contract.split())

        self.assertIn("current working directory", contract)
        self.assertIn("absolute path is not stable", contract)
        self.assertIn("placeholder import providers", contract)
        self.assertIn("auditable repository provider", contract)
        self.assertIn("return the controlling shell", contract)

    def test_candidate_policy_allows_deployment_artifacts(self) -> None:
        validation = MinimalIntegrityCandidateValidator().validate(
            DeploymentCandidate(
                "candidate",
                "printf 'value = 1\\n' > compatibility.py",
                "materialize a compatibility artifact",
            )
        )

        self.assertTrue(validation.accepted)
        self.assertFalse(validation.details["semantic_rules"])

    def test_live_policy_names_evaluator_only_artifacts(self) -> None:
        validator = MinimalIntegrityCandidateValidator(
            protect_evaluator_artifacts=True
        )

        self.assertEqual(validator.policy_id, "minimal-evaluator-integrity-v2")
        self.assertIn("pyrightconfig.json", validator.prompt_contract)
        self.assertIn("type-only `.pyi` providers", validator.prompt_contract)

    def test_repository_audit_allows_untracked_outputs_but_not_tracked_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            tracked = root / "tracked.py"
            tracked.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (root / "compatibility.py").write_text("value = 2\n", encoding="utf-8")

            clean = inspect_minimal_repository_integrity(root, revision)
            tracked.write_text("value = 3\n", encoding="utf-8")
            modified = inspect_minimal_repository_integrity(root, revision)

        self.assertTrue(clean.valid)
        self.assertFalse(modified.valid)
        self.assertEqual(modified.tracked_changes, ("tracked.py",))

    def test_live_audit_rejects_evaluator_config_and_type_only_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=root, check=True
            )
            (root / "tracked.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (root / "compatibility.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "pyrightconfig.json").write_text("{}\n", encoding="utf-8")
            (root / "typings/pkg").mkdir(parents=True)
            (root / "typings/pkg/__init__.pyi").write_text("VALUE: int\n", encoding="utf-8")
            (root / ".venv/lib/pkg").mkdir(parents=True)
            (root / ".venv/lib/pkg/__init__.pyi").write_text("VALUE: int\n", encoding="utf-8")
            custom_venv = root / ".venv_py39"
            (custom_venv / "bin").mkdir(parents=True)
            (custom_venv / "lib/pkg").mkdir(parents=True)
            (custom_venv / "pyvenv.cfg").write_text(
                "home = /usr/bin\ninclude-system-site-packages = false\n",
                encoding="utf-8",
            )
            (custom_venv / "bin/activate").write_text("true\n", encoding="utf-8")
            inaccessible = root.parent / f"{root.name}-container-only-python"
            inaccessible.mkdir()
            interpreter = inaccessible / "python3.9"
            interpreter.write_text("", encoding="utf-8")
            interpreter.chmod(0)
            inaccessible.chmod(0)
            (custom_venv / "bin/python").symlink_to(interpreter)
            (custom_venv / "lib/pkg/__init__.pyi").write_text(
                "VALUE: int\n", encoding="utf-8"
            )
            try:
                historical = inspect_minimal_repository_integrity(root, revision)
                live = inspect_minimal_repository_integrity(
                    root,
                    revision,
                    protect_evaluator_artifacts=True,
                )
            finally:
                inaccessible.chmod(0o700)
                interpreter.chmod(0o600)
                interpreter.unlink()
                inaccessible.rmdir()

        self.assertTrue(historical.valid)
        self.assertFalse(live.valid)
        self.assertEqual(
            live.untracked_evaluator_artifacts,
            ("pyrightconfig.json", "typings/pkg/__init__.pyi"),
        )
        self.assertNotIn("compatibility.py", live.untracked_evaluator_artifacts)
        self.assertNotIn(".venv/lib/pkg/__init__.pyi", live.untracked_evaluator_artifacts)
        self.assertNotIn(
            ".venv_py39/lib/pkg/__init__.pyi",
            live.untracked_evaluator_artifacts,
        )

    def test_goal_verifier_adds_only_narrow_provider_provenance_boundary(self) -> None:
        verifier = MinimalIntegrityGoalVerifier(
            ExecutableGoalContract(
                "goal",
                "Require success",
                "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
            )
        )
        command, _, _ = verifier._command(
            DeploymentCandidate(
                "candidate",
                "printf 'candidate-sentinel\\n'",
                "test",
            ),
            DockerEnvironmentHandle("container", Path("/tmp/worktree"), "/data/project"),
            "nonce",
        )

        self.assertLess(
            command.index(_PROVIDER_BASELINE_MARKER),
            command.index("candidate-sentinel"),
        )
        self.assertLess(
            command.index("candidate-sentinel"),
            command.index(_PROVIDER_POST_MARKER),
        )
        self.assertIn("packages_distributions", command)
        self.assertIn("distribution.files", command)
        self.assertIn("/usr/bin/dpkg-query", command)
        self.assertIn("/usr/bin/rpm", command)
        self.assertIn("/sbin/apk", command)
        self.assertIn("module.startswith", command)
        self.assertNotIn("importlib.util.find_spec", command)

    def test_provider_delta_rejects_only_new_unowned_artifacts(self) -> None:
        existing = {
            "module": "base_helper",
            "artifact_path": "/opt/site-packages/base_helper.py",
            "artifact_sha256": "a" * 64,
        }
        stub = {
            "module": "gfosd",
            "artifact_path": "/tmp/venv/site-packages/gfosd/__init__.py",
            "artifact_sha256": "b" * 64,
            "artifact_kind": "package",
            "artifact_bytes": 20,
        }
        baseline = {
            "schema": _PROVIDER_AUDIT_SCHEMA,
            "unowned_public_site_providers": [existing],
        }
        post = {
            "schema": _PROVIDER_AUDIT_SCHEMA,
            "unowned_public_site_providers": [existing, stub],
        }

        self.assertEqual(
            _novel_unowned_provider_violations(baseline, post),
            [stub],
        )

    def test_provider_audit_detects_manual_package_in_real_venv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = root / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / "bin" / "python"
            wheel = root / "owned_provider-1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("owned_provider/__init__.py", "VALUE = 1\n")
                archive.writestr(
                    "owned_provider-1.0.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: owned-provider\nVersion: 1.0\n",
                )
                archive.writestr(
                    "owned_provider-1.0.dist-info/WHEEL",
                    "Wheel-Version: 1.0\nGenerator: envsolve-test\n"
                    "Root-Is-Purelib: true\nTag: py3-none-any\n",
                )
                archive.writestr("owned_provider-1.0.dist-info/RECORD", "")
            subprocess.run(
                [str(python), "-m", "pip", "install", "--no-index", str(wheel)],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            site_root = Path(
                subprocess.run(
                    [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            )
            package = site_root / "gfosd"
            package.mkdir()
            (package / "__init__.py").write_text(
                '"""Stub for gfosd."""\n',
                encoding="utf-8",
            )
            environment_vars = dict(os.environ)
            environment_vars["PATH"] = (
                f"{environment / 'bin'}{os.pathsep}{environment_vars.get('PATH', '')}"
            )
            fallback_audit = _UNOWNED_PROVIDER_AUDIT.replace(
                'resolver = getattr(metadata, "packages_distributions", None)',
                "resolver = None",
                1,
            )
            self.assertNotEqual(fallback_audit, _UNOWNED_PROVIDER_AUDIT)
            completed = subprocess.run(
                [
                    "bash",
                    "-c",
                    "command python -I -c "
                    f"{shlex.quote(fallback_audit)} "
                    f"{shlex.quote(_PROVIDER_POST_MARKER)}",
                ],
                env=environment_vars,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )

        report = marked_json_payload(completed.stdout, _PROVIDER_POST_MARKER)
        self.assertIsNotNone(report)
        self.assertEqual(report["schema"], _PROVIDER_AUDIT_SCHEMA)
        self.assertEqual(
            [
                item["module"]
                for item in report["unowned_public_site_providers"]
            ],
            ["gfosd"],
        )
        self.assertNotIn(
            "owned_provider",
            [
                item["module"]
                for item in report["unowned_public_site_providers"]
            ],
        )

    def test_provider_audit_accepts_system_package_manager_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = root / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / "bin" / "python"
            site_root = Path(
                subprocess.run(
                    [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            )
            module = site_root / "system_helper.py"
            module.write_text("VALUE = 1\n", encoding="utf-8")
            fake_bin = root / "bin"
            fake_bin.mkdir()
            dpkg_query = fake_bin / "dpkg-query"
            dpkg_query.write_text(
                "#!/bin/sh\n"
                "case \"$2\" in\n"
                f"  {shlex.quote(str(module.resolve()))}) exit 0 ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            dpkg_query.chmod(0o755)
            environment_vars = dict(os.environ)
            environment_vars["PATH"] = os.pathsep.join(
                (
                    str(fake_bin),
                    str(environment / "bin"),
                    environment_vars.get("PATH", ""),
                )
            )
            system_audit = _UNOWNED_PROVIDER_AUDIT.replace(
                'Path("/usr/bin/dpkg-query")',
                f"Path({str(dpkg_query)!r})",
                1,
            )
            completed = subprocess.run(
                [
                    "bash",
                    "-c",
                    "command python -I -c "
                    f"{shlex.quote(system_audit)} "
                    f"{shlex.quote(_PROVIDER_POST_MARKER)}",
                ],
                env=environment_vars,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )

        report = marked_json_payload(completed.stdout, _PROVIDER_POST_MARKER)
        self.assertIsNotNone(report)
        self.assertNotIn(
            "system_helper",
            [
                item["module"]
                for item in report["unowned_public_site_providers"]
            ],
        )

    def test_passing_goal_becomes_counterexample_for_new_unowned_provider(self) -> None:
        baseline = {
            "schema": _PROVIDER_AUDIT_SCHEMA,
            "unowned_public_site_providers": [],
        }
        stub = {
            "module": "tikz",
            "artifact_path": "/tmp/venv/site-packages/tikz/__init__.py",
            "artifact_sha256": "c" * 64,
        }
        post = {
            "schema": _PROVIDER_AUDIT_SCHEMA,
            "unowned_public_site_providers": [stub],
        }
        stdout = "\n".join(
            (
                _PROVIDER_BASELINE_MARKER + json.dumps(baseline),
                _PROVIDER_POST_MARKER + json.dumps(post),
            )
        )
        passed = ExecutableVerification(
            verifier="goal",
            check_profile="goal-v1",
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=True,
            bootstrap=CommandResult(0, stdout, "", 1.0),
            summary="pass",
        )
        verifier = MinimalIntegrityGoalVerifier(
            ExecutableGoalContract("goal", "test", "true")
        )

        with mock.patch(
            "envsolve.runtime.goal_verifier.ExecutableGoalContractVerifier.verify",
            return_value=passed,
        ):
            outcome = verifier.verify(
                DeploymentCandidate("candidate", "true", "test"),
                object(),
            )

        self.assertFalse(outcome.passed)
        self.assertEqual(outcome.counterexamples[0].kind, "import-provider-provenance")
        self.assertEqual(
            outcome.details["import_provider_provenance"]["violations"],
            [stub],
        )


if __name__ == "__main__":
    unittest.main()
