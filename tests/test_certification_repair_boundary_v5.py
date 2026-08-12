from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from envsolve.solver import DeploymentCandidate
from envsolve_harness.boundary_v3 import adjudicate_managed_dependencies
from envsolve_harness.boundary_v4 import adjudicate_repository_native_artifacts
from envsolve_harness.boundary_v5 import (
    OPEN_PROGRAM_POLICY,
    REPOSITORY_POLICY,
    TRACKED_COPY_POLICY,
    BoundaryV5OpenCandidateProgramValidator,
    adjudicate_repository_tracked_copies,
    boundary_v5_local_distribution_audit,
)
from envsolve_harness.integrity.repository import inspect_repository


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _source_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    package = repo / "package"
    package.mkdir()
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "module.py").write_text("ANSWER = 42\n", encoding="utf-8")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def _v5_repository_report(repo: Path, revision: str):
    raw = inspect_repository(repo, revision)
    managed = adjudicate_managed_dependencies(repo, raw, None)
    native = adjudicate_repository_native_artifacts(repo, managed)
    return raw, adjudicate_repository_tracked_copies(repo, native)


def test_build_tree_accepts_exact_committed_source_with_preserved_path(
    tmp_path: Path,
) -> None:
    repo, revision = _source_repo(tmp_path)
    target = repo / "arbitrary-output" / "lib" / "package" / "module.py"
    target.parent.mkdir(parents=True)
    target.write_bytes((repo / "package" / "module.py").read_bytes())

    raw, report = _v5_repository_report(repo, revision)

    assert not raw.valid
    assert report.valid
    assert report.tracked_copy_policy == TRACKED_COPY_POLICY
    assert [item.to_dict() for item in report.accepted_tracked_copies] == [
        {
            "path": "arbitrary-output/lib/package/module.py",
            "source_path": "package/module.py",
            "sha256": "5db028e2723bc88cf5657f92b784f28683657f7459caf7f0c54299bf6cb4b3fc",
            "derivation": "exact-committed-source-copy-with-path-preservation",
        }
    ]
    assert report.to_dict()["policy"] == REPOSITORY_POLICY


def test_build_tree_rejects_modified_source_copy(tmp_path: Path) -> None:
    repo, revision = _source_repo(tmp_path)
    target = repo / "output" / "package" / "module.py"
    target.parent.mkdir(parents=True)
    target.write_text("ANSWER = 43\n", encoding="utf-8")

    _, report = _v5_repository_report(repo, revision)

    assert not report.valid
    assert report.accepted_tracked_copies == ()
    assert [item.path for item in report.remaining_violations] == [
        "output/package/module.py"
    ]


def test_build_tree_rejects_renamed_source_copy(tmp_path: Path) -> None:
    repo, revision = _source_repo(tmp_path)
    target = repo / "output" / "synthetic.py"
    target.parent.mkdir()
    target.write_bytes((repo / "package" / "module.py").read_bytes())

    _, report = _v5_repository_report(repo, revision)

    assert not report.valid
    assert report.accepted_tracked_copies == ()
    assert [item.path for item in report.remaining_violations] == [
        "output/synthetic.py"
    ]


def _run_local_audit(repo: Path, import_root: Path) -> dict:
    marker = "ENVSOLVE_TEST_AUDIT="
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            boundary_v5_local_distribution_audit(),
            str(repo),
            marker,
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(import_root)},
    )
    return json.loads(completed.stdout.removeprefix(marker))


def test_external_build_tree_accepts_same_tracked_copy(tmp_path: Path) -> None:
    repo, _ = _source_repo(tmp_path)
    external = tmp_path / "external"
    target = external / "stage" / "package" / "module.py"
    target.parent.mkdir(parents=True)
    target.write_bytes((repo / "package" / "module.py").read_bytes())

    payload = _run_local_audit(repo, external)
    external_findings = [
        item
        for item in payload["unowned_import_artifacts"]
        if item["site_root"] == str(external.resolve())
    ]

    assert external_findings == []
    assert [item["relative_path"] for item in payload["repository_tracked_copies"]] == [
        "stage/package/module.py"
    ]


def test_external_build_tree_rejects_modified_and_renamed_copies(
    tmp_path: Path,
) -> None:
    repo, _ = _source_repo(tmp_path)
    external = tmp_path / "external"
    package = external / "package"
    package.mkdir(parents=True)
    (package / "module.py").write_text("ANSWER = 43\n", encoding="utf-8")
    (external / "synthetic.py").write_bytes(
        (repo / "package" / "module.py").read_bytes()
    )

    payload = _run_local_audit(repo, external)
    external_findings = [
        item
        for item in payload["unowned_import_artifacts"]
        if item["site_root"] == str(external.resolve())
    ]

    assert payload["repository_tracked_copies"] == []
    assert sorted(item["relative_path"] for item in external_findings) == [
        "package/module.py",
        "synthetic.py",
    ]


def test_external_target_distribution_owns_installed_package(tmp_path: Path) -> None:
    repo, _ = _source_repo(tmp_path)
    external = tmp_path / "external"
    package = external / "installed_package"
    metadata = external / "installed_package-1.0.dist-info"
    package.mkdir(parents=True)
    metadata.mkdir()
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: installed-package\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (metadata / "RECORD").write_text(
        "installed_package/__init__.py,,\n"
        "installed_package-1.0.dist-info/METADATA,,\n"
        "installed_package-1.0.dist-info/RECORD,,\n",
        encoding="utf-8",
    )

    payload = _run_local_audit(repo, external)
    external_findings = [
        item
        for item in payload["unowned_import_artifacts"]
        if item["site_root"] == str(external.resolve())
    ]

    assert external_findings == []


def test_boundary_v5_audit_has_no_standalone_line_continuations() -> None:
    source = boundary_v5_local_distribution_audit()

    assert all(line != "\\" for line in source.splitlines())


def test_boundary_v5_audit_is_self_contained() -> None:
    source = boundary_v5_local_distribution_audit()

    compile(source, "<boundary-v5-local-distribution-audit>", "exec")
    assert "tracked_python_source_bytes" in source
    assert "exact-committed-source-copy-with-path-preservation" in source
    assert "repository_tracked_copies" in source


def test_boundary_v5_keeps_frozen_candidate_operation_language() -> None:
    validator = BoundaryV5OpenCandidateProgramValidator()
    accepted = validator.validate(
        DeploymentCandidate(
            "candidate",
            "python -m build --wheel",
            "fixture",
        )
    )
    rejected = validator.validate(
        DeploymentCandidate(
            "candidate",
            "cp package/module.py output/synthetic.py",
            "fixture",
        )
    )

    assert accepted.accepted
    assert accepted.policy_id == OPEN_PROGRAM_POLICY
    assert not rejected.accepted
    assert rejected.policy_id == OPEN_PROGRAM_POLICY
