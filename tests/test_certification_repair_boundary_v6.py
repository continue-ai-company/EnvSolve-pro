from __future__ import annotations

from pathlib import Path
import subprocess

from envsolve.solver import DeploymentCandidate
from envsolve_harness.boundary_v3 import (
    BoundaryV3OpenCandidateProgramValidator,
    adjudicate_managed_dependencies,
)
from envsolve_harness.boundary_v4 import adjudicate_repository_native_artifacts
from envsolve_harness.boundary_v5 import (
    BoundaryV5OpenCandidateProgramValidator,
    adjudicate_repository_tracked_copies,
)
from envsolve_harness.boundary_v6 import (
    OPEN_PROGRAM_POLICY,
    REPOSITORY_POLICY,
    BoundaryV6OpenCandidateProgramValidator,
    adjudicate_open_import_artifacts,
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
    (repo / ".gitignore").write_text("package/generated/\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def _v6_report(repo: Path, revision: str):
    raw = inspect_repository(repo, revision)
    managed = adjudicate_managed_dependencies(repo, raw, None)
    native = adjudicate_repository_native_artifacts(repo, managed)
    tracked = adjudicate_repository_tracked_copies(repo, native)
    return adjudicate_open_import_artifacts(repo, tracked)


def test_v6_opens_direct_and_embedded_import_artifact_operations() -> None:
    validator = BoundaryV6OpenCandidateProgramValidator()
    scripts = (
        "printf 'DEBUG=False\\n' > package/override_settings.py",
        "python - <<'PY'\nfrom pathlib import Path\nPath('package/config_pb2.py').write_text('VALUE=1\\n')\nPY",
    )

    for script in scripts:
        result = validator.validate(
            DeploymentCandidate("candidate", script, "fixture")
        )
        assert result.accepted
        assert result.policy_id == OPEN_PROGRAM_POLICY


def test_v6_allows_functional_package_under_direct_mktemp_root() -> None:
    script = """\
legacy_compat_source=$(mktemp -d)
cat > "$legacy_compat_source/setup.py" <<'PY'
from setuptools import setup
setup(name="legacy-compat", version="1.0", py_modules=["cStringIO"])
PY
cat > "$legacy_compat_source/cStringIO.py" <<'PY'
from io import StringIO
PY
python -m pip install "$legacy_compat_source"
"""

    result = BoundaryV6OpenCandidateProgramValidator().validate(
        DeploymentCandidate("candidate", script, "position-2 regression")
    )

    assert result.accepted
    assert result.policy_id == OPEN_PROGRAM_POLICY


def test_v6_still_rejects_repository_configuration_write() -> None:
    result = BoundaryV6OpenCandidateProgramValidator().validate(
        DeploymentCandidate(
            "candidate",
            "printf 'from setuptools import setup\\n' > setup.py",
            "repository write",
        )
    )

    assert not result.accepted
    assert "protected repository configuration" in (result.reason or "")


def test_v6_rejects_configuration_write_after_temp_root_rebinding() -> None:
    script = """\
build_root=$(mktemp -d)
build_root=$PWD
printf 'from setuptools import setup\\n' > "$build_root/setup.py"
"""

    result = BoundaryV6OpenCandidateProgramValidator().validate(
        DeploymentCandidate("candidate", script, "rebound root")
    )

    assert not result.accepted
    assert "protected repository configuration" in (result.reason or "")


def test_v6_rejects_type_only_provider_under_temp_root() -> None:
    script = """\
stub_root=$(mktemp -d)
mkdir -p "$stub_root/PyQuante-stubs"
printf 'class CGBF: ...\\n' > "$stub_root/PyQuante-stubs/CGBF.pyi"
"""

    result = BoundaryV6OpenCandidateProgramValidator().validate(
        DeploymentCandidate("candidate", script, "position-1 regression")
    )

    assert not result.accepted
    assert "type-only import provider" in (result.reason or "")


def test_v3_does_not_inherit_the_v6_temp_build_driver_exemption() -> None:
    script = """\
build_root=$(mktemp -d)
printf 'from setuptools import setup\\n' > "$build_root/setup.py"
"""

    result = BoundaryV3OpenCandidateProgramValidator().validate(
        DeploymentCandidate("candidate", script, "v3 remains unchanged")
    )

    assert not result.accepted
    assert "protected repository configuration" in (result.reason or "")


def test_v5_operation_language_remains_frozen() -> None:
    result = BoundaryV5OpenCandidateProgramValidator().validate(
        DeploymentCandidate(
            "candidate",
            "printf 'DEBUG=False\\n' > package/override_settings.py",
            "fixture",
        )
    )

    assert not result.accepted


def test_v6_keeps_symlink_import_alias_rejection() -> None:
    result = BoundaryV6OpenCandidateProgramValidator().validate(
        DeploymentCandidate(
            "candidate",
            'site_packages=/tmp/site-packages\n'
            'ln -s "$PWD/package" "$site_packages/package"',
            "fixture",
        )
    )

    assert not result.accepted
    assert "symbolic link" in (result.reason or "")


def test_v6_defers_nonempty_real_deployment_artifacts_for_review(
    tmp_path: Path,
) -> None:
    repo, revision = _source_repo(tmp_path)
    artifacts = {
        "package/override_settings.py": "DEBUG = False\n",
        "package/generated/config_pb2.py": "# generated by protoc\nVALUE = 1\n",
        "package/generated/OverrideLexer.py": "# generated by ANTLR\nVALUE = 1\n",
    }
    for relative, content in artifacts.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    report = _v6_report(repo, revision)

    assert report.valid
    assert report.to_dict()["policy"] == REPOSITORY_POLICY
    assert [item.path for item in report.review_required_artifacts] == sorted(
        artifacts
    )


def test_v6_rejects_empty_import_file_and_empty_namespace(tmp_path: Path) -> None:
    repo, revision = _source_repo(tmp_path)
    (repo / "package/empty.py").touch()
    (repo / "package/override_settings").mkdir()

    report = _v6_report(repo, revision)

    assert not report.valid
    assert report.review_required_artifacts == ()
    assert {
        (item.kind, item.path) for item in report.remaining_violations
    } == {
        ("untracked_import_artifact", "package/empty.py"),
        ("empty_import_directory", "package/override_settings"),
    }


def test_v6_and_v5_agree_on_boundary_invariant_script() -> None:
    candidate = DeploymentCandidate(
        "candidate",
        "python -m venv .venv\n. .venv/bin/activate\npip install -e .",
        "fixture",
    )

    v5 = BoundaryV5OpenCandidateProgramValidator().validate(candidate)
    v6 = BoundaryV6OpenCandidateProgramValidator().validate(candidate)

    assert v5.accepted == v6.accepted is True
    assert v5.normalized_script == v6.normalized_script
