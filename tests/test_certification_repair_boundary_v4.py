from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from envsolve.solver import DeploymentCandidate
from envsolve_harness.boundary_v4 import (
    NATIVE_BUILD_POLICY,
    OPEN_PROGRAM_POLICY,
    REPOSITORY_POLICY,
    BoundaryV4OpenCandidateProgramValidator,
    adjudicate_repository_native_artifacts,
    boundary_v4_local_distribution_audit,
    boundary_v4_novel_local_distribution_violations,
)
from envsolve_harness.boundary_v3 import adjudicate_managed_dependencies
from envsolve_harness.integrity.repository import inspect_repository


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _native_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    source = repo / "distutils" / "tests" / "xxmodule.c"
    source.parent.mkdir(parents=True)
    source.write_text(
        "void *PyInit_xx(void) { return 0; }\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def _fake_native(module: str) -> bytes:
    return b"\x7fELF\x02\x01fixture\x00PyInit_" + module.encode("ascii") + b"\x00"


def _v4_repository_report(repo: Path, revision: str):
    base = inspect_repository(repo, revision)
    managed = adjudicate_managed_dependencies(repo, base, None)
    return base, adjudicate_repository_native_artifacts(repo, managed)


def test_repository_native_build_is_accepted_from_tracked_provider(
    tmp_path: Path,
) -> None:
    repo, revision = _native_repo(tmp_path)
    artifact = repo / "build_output" / "xx.cpython-313-aarch64-linux-gnu.so"
    artifact.parent.mkdir()
    artifact.write_bytes(_fake_native("xx"))

    base, report = _v4_repository_report(repo, revision)

    assert not base.valid
    assert report.valid
    assert report.native_build_policy == NATIVE_BUILD_POLICY
    assert report.native_providers == {"xx": ("distutils/tests/xxmodule.c",)}
    assert [item.path for item in report.accepted_native_artifacts] == [
        "build_output/xx.cpython-313-aarch64-linux-gnu.so"
    ]
    payload = report.to_dict()
    assert payload["policy"] == REPOSITORY_POLICY
    assert payload["accepted_native_artifact_count"] == 1


def test_repository_native_build_requires_tracked_provider(tmp_path: Path) -> None:
    repo, revision = _native_repo(tmp_path)
    artifact = repo / "build_output" / "invented.cpython-313-aarch64-linux-gnu.so"
    artifact.parent.mkdir()
    artifact.write_bytes(_fake_native("invented"))

    _, report = _v4_repository_report(repo, revision)

    assert not report.valid
    assert report.accepted_native_artifacts == ()
    assert [item.path for item in report.remaining_violations] == [
        "build_output/invented.cpython-313-aarch64-linux-gnu.so"
    ]


def test_repository_native_build_requires_binary_and_initializer(
    tmp_path: Path,
) -> None:
    repo, revision = _native_repo(tmp_path)
    build = repo / "build_output"
    build.mkdir()
    (build / "xx.so").write_bytes(b"not-a-native-binary PyInit_xx")

    _, report = _v4_repository_report(repo, revision)

    assert not report.valid
    assert report.accepted_native_artifacts == ()


def test_repository_python_shim_remains_rejected(tmp_path: Path) -> None:
    repo, revision = _native_repo(tmp_path)
    build = repo / "build_output"
    build.mkdir()
    (build / "xx.py").write_text("VALUE = 1\n", encoding="utf-8")

    _, report = _v4_repository_report(repo, revision)

    assert not report.valid
    assert report.accepted_native_artifacts == ()
    assert [item.path for item in report.remaining_violations] == [
        "build_output/xx.py"
    ]


def test_local_audit_accepts_same_native_build_outside_repository(
    tmp_path: Path,
) -> None:
    repo, _ = _native_repo(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    artifact = external / "xx.cpython-313-aarch64-linux-gnu.so"
    artifact.write_bytes(_fake_native("xx"))
    marker = "ENVSOLVE_TEST_AUDIT="
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join((str(external), str(repo)))}

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            boundary_v4_local_distribution_audit(),
            str(repo),
            marker,
        ],
        capture_output=True,
        text=True,
        check=True,
        env=environment,
    )
    payload = json.loads(completed.stdout.removeprefix(marker))
    external_findings = [
        item
        for item in payload["unowned_import_artifacts"]
        if item["site_root"] == str(external.resolve())
    ]

    assert external_findings == []
    assert payload["repository_native_providers"] == {
        "xx": ["distutils/tests/xxmodule.c"]
    }
    assert [item["relative_path"] for item in payload["repository_native_artifacts"]] == [
        artifact.name
    ]


def test_local_audit_rejects_unprovided_native_and_python_shim(
    tmp_path: Path,
) -> None:
    repo, _ = _native_repo(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "invented.so").write_bytes(_fake_native("invented"))
    (external / "xx.py").write_text("VALUE = 1\n", encoding="utf-8")
    marker = "ENVSOLVE_TEST_AUDIT="
    environment = {**os.environ, "PYTHONPATH": str(external)}

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            boundary_v4_local_distribution_audit(),
            str(repo),
            marker,
        ],
        capture_output=True,
        text=True,
        check=True,
        env=environment,
    )
    payload = json.loads(completed.stdout.removeprefix(marker))
    external_findings = [
        item
        for item in payload["unowned_import_artifacts"]
        if item["site_root"] == str(external.resolve())
    ]

    assert payload["repository_native_artifacts"] == []
    assert sorted(
        item["relative_path"] for item in external_findings
    ) == ["invented.so", "xx.py"]


def test_boundary_v4_audit_is_self_contained_and_uses_committed_source() -> None:
    source = boundary_v4_local_distribution_audit()

    compile(source, "<boundary-v4-local-distribution-audit>", "exec")
    assert '[system_git, "show", "HEAD:" + relative_path]' in source
    assert "resolved_root.is_relative_to(project_root)" in source
    assert "repository_native_artifacts" in source


def test_boundary_v4_decision_uses_only_new_unowned_artifacts() -> None:
    background = {
        "audit_kind": "unowned-import-artifact",
        "site_root": "/baseline/editable-project",
        "relative_path": "existing.py",
    }
    novel = {
        "audit_kind": "unowned-import-artifact",
        "site_root": "/tmp/candidate-path",
        "relative_path": "synthetic.py",
    }

    findings = boundary_v4_novel_local_distribution_violations(
        {"violations": [], "unowned_import_artifacts": [background]},
        {"violations": [], "unowned_import_artifacts": [background, novel]},
    )

    assert findings == [novel]


def test_boundary_v4_validator_keeps_build_tools_but_rejects_direct_artifacts() -> None:
    validator = BoundaryV4OpenCandidateProgramValidator()
    build = validator.validate(
        DeploymentCandidate(
            "candidate",
            "cc -shared distutils/tests/xxmodule.c -o /tmp/native/xx.so",
            "fixture",
        )
    )
    fake = validator.validate(
        DeploymentCandidate(
            "candidate",
            "python - <<'PY'\n"
            "from pathlib import Path\n"
            "Path('/tmp/native/xx.so').write_bytes(b'fake')\n"
            "PY",
            "fixture",
        )
    )

    assert build.accepted
    assert build.policy_id == OPEN_PROGRAM_POLICY
    assert not fake.accepted
    assert fake.policy_id == OPEN_PROGRAM_POLICY
