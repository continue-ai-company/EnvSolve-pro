from __future__ import annotations

import json
from pathlib import Path
import subprocess

from envsolve.solver import DeploymentCandidate
from envsolve_harness.boundary_v3 import (
    _MANAGED_DEPENDENCY_AUDIT,
    BoundaryV3OpenCandidateProgramValidator,
    MANAGED_DEPENDENCY_POLICY,
    REPOSITORY_POLICY,
    adjudicate_managed_dependencies,
    boundary_v3_local_distribution_audit,
    boundary_v3_novel_local_distribution_violations,
)
from envsolve_harness.integrity.repository import inspect_repository


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _candidate(script: str) -> DeploymentCandidate:
    return DeploymentCandidate("candidate", script, "fixture")


def test_boundary_v3_rejects_temporary_repository_configuration() -> None:
    validator = BoundaryV3OpenCandidateProgramValidator()
    direct = validator.validate(
        _candidate("cat > setup.py <<'PY'\nprint('build')\nPY\nrm setup.py")
    )
    embedded = validator.validate(
        _candidate(
            "python - <<'PY'\n"
            "from pathlib import Path\n"
            "Path('pyrightconfig.json').write_text('{}')\n"
            "PY"
        )
    )

    assert not direct.accepted
    assert direct.policy_id == "open-candidate-program-v3"
    assert direct.details["target"] == "setup.py"
    assert not embedded.accepted
    assert embedded.details["target"] == "pyrightconfig.json"


def test_boundary_v3_keeps_normal_package_manager_program_open() -> None:
    result = BoundaryV3OpenCandidateProgramValidator().validate(
        _candidate(
            "python3.10 -m venv .venv\n"
            ". .venv/bin/activate\n"
            "poetry install --no-root\n"
            "autonomy packages sync\n"
            "export PYTHONPATH=$PWD"
        )
    )

    assert result.accepted
    assert result.policy_id == "open-candidate-program-v3"
    assert result.details["protected_configuration_history"] == (
        "no-write-observed"
    )


def test_content_locked_ignored_packages_are_distinct_from_unowned_shims(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / ".gitignore").write_text("packages/vendor/\n", encoding="utf-8")
    (repo / "tox.ini").write_text(
        "[testenv]\ncommands = autonomy packages sync\n",
        encoding="utf-8",
    )
    packages = repo / "packages"
    packages.mkdir()
    (packages / "packages.json").write_text(
        json.dumps({"third_party": {"skill/vendor/example/1.0.0": "cid"}}),
        encoding="utf-8",
    )
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    generated = packages / "vendor" / "example"
    generated.mkdir(parents=True)
    (generated / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "unowned.py").write_text("VALUE = 2\n", encoding="utf-8")
    base = inspect_repository(repo, revision)

    report = adjudicate_managed_dependencies(
        repo,
        base,
        {
            "adapter": MANAGED_DEPENDENCY_POLICY,
            "applicable": True,
            "valid": True,
            "package_root": "packages",
            "lock_path": "packages/packages.json",
        },
    )

    assert not base.valid
    assert not report.valid
    assert report.accepted_managed_paths == (
        "packages/vendor/example/__init__.py",
    )
    assert [item.path for item in report.remaining_violations] == ["unowned.py"]
    assert report.to_dict()["policy"] == REPOSITORY_POLICY


def test_managed_package_allowance_requires_valid_provenance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / ".gitignore").write_text("packages/vendor/\n", encoding="utf-8")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    generated = repo / "packages" / "vendor"
    generated.mkdir(parents=True)
    (generated / "shim.py").write_text("VALUE = 1\n", encoding="utf-8")
    base = inspect_repository(repo, revision)

    report = adjudicate_managed_dependencies(
        repo,
        base,
        {"valid": False, "package_root": "packages"},
    )

    assert not report.valid
    assert report.accepted_managed_paths == ()
    assert [item.path for item in report.remaining_violations] == [
        "packages/vendor/shim.py"
    ]


def _virtualenv_audit_fixture(helper_hash: str = "trusted-hash") -> tuple[dict, dict]:
    site_root = "/tmp/candidate/lib/python3.10/site-packages"
    runtime_findings = [
        {
            "audit_kind": "unowned-import-artifact",
            "site_root": site_root,
            "relative_path": name,
        }
        for name in ("_virtualenv.pth", "_virtualenv.py", "candidate_shim.py")
    ]
    baseline = {
        "violations": [],
        "unowned_import_artifacts": [],
        "trusted_virtualenv_build": {
            "valid": True,
            "distribution_version": "20.31.2",
            "template_sha256": "trusted-hash",
        },
    }
    post = {
        "violations": [],
        "unowned_import_artifacts": runtime_findings,
        "virtualenv_runtime_artifacts": {
            "valid": True,
            "distribution_version": "20.31.2",
            "pairs": [
                {
                    "site_root": site_root,
                    "relative_paths": ["_virtualenv.pth", "_virtualenv.py"],
                    "pth_is_standard": True,
                    "helper_sha256": helper_hash,
                }
            ],
        },
    }
    return baseline, post


def test_virtualenv_runtime_allowance_is_content_and_version_derived() -> None:
    baseline, post = _virtualenv_audit_fixture()

    findings = boundary_v3_novel_local_distribution_violations(baseline, post)

    assert [item["relative_path"] for item in findings] == ["candidate_shim.py"]


def test_virtualenv_runtime_allowance_rejects_modified_helper() -> None:
    baseline, post = _virtualenv_audit_fixture(helper_hash="modified-hash")

    findings = boundary_v3_novel_local_distribution_violations(baseline, post)

    assert [item["relative_path"] for item in findings] == [
        "_virtualenv.pth",
        "_virtualenv.py",
        "candidate_shim.py",
    ]


def test_boundary_v3_local_distribution_audit_is_self_contained() -> None:
    source = boundary_v3_local_distribution_audit()

    compile(source, "<boundary-v3-local-distribution-audit>", "exec")
    assert '"site_root": str(root.resolve())' in source
    assert 'pth_bytes == b"import _virtualenv"' in source
    assert "trusted_virtualenv_build" in source


def test_managed_dependency_audit_uses_trusted_git_for_mounted_worktree() -> None:
    compile(_MANAGED_DEPENDENCY_AUDIT, "<managed-dependency-audit>", "exec")
    assert '("/usr/bin/git", "/bin/git")' in _MANAGED_DEPENDENCY_AUDIT
    assert 'handle.write("[safe]\\n\\tdirectory = "' in _MANAGED_DEPENDENCY_AUDIT
    assert '"GIT_CONFIG_GLOBAL": str(trusted_git_config)' in (
        _MANAGED_DEPENDENCY_AUDIT
    )
    assert 'if not key.startswith("GIT_")' in _MANAGED_DEPENDENCY_AUDIT
    assert 'run("git"' not in _MANAGED_DEPENDENCY_AUDIT
