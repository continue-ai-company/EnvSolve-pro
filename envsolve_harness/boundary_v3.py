from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.integrity import (
    marked_json_payload,
    python_import_alias_audit_command,
)
from envsolve.solver import CandidateValidation, DeploymentCandidate
from envsolve_harness.boundary_v2 import (
    BoundaryV2MinimalBExecutableGoalVerifier,
)
from envsolve_harness import boundary_v2
from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.integrity.repository import (
    CONFIGURATION_NAMES,
    RepositoryIntegrityReport,
)
from envsolve_harness.scripts import open_program
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator


OPEN_PROGRAM_POLICY = "open-candidate-program-v3"
MANAGED_DEPENDENCY_MARKER = "ENVSOLVE_MANAGED_DEPENDENCY_PROVENANCE_V1="
MANAGED_DEPENDENCY_POLICY = "open-aea-content-addressed-lock-v1"
REPOSITORY_POLICY = "submitted-state-plus-content-provenance-v7"

_VIRTUALENV_AUDIT_IMPORTS = """\
import importlib.metadata
import json
"""
_VIRTUALENV_AUDIT_IMPORTS_V3 = """\
import hashlib
import importlib.metadata
import json
"""
_VIRTUALENV_RUNTIME_PROVENANCE = r'''\
trusted_virtualenv_build = {"applicable": False, "valid": False}
try:
    virtualenv_distribution = importlib.metadata.distribution("virtualenv")
    virtualenv_templates = [
        Path(virtualenv_distribution.locate_file(item)).resolve()
        for item in virtualenv_distribution.files or ()
        if str(item).endswith("create/via_global_ref/_virtualenv.py")
    ]
    if len(virtualenv_templates) == 1 and virtualenv_templates[0].is_file():
        template = virtualenv_templates[0]
        trusted_virtualenv_build = {
            "applicable": True,
            "valid": True,
            "distribution_version": virtualenv_distribution.version,
            "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        }
except Exception as exc:
    trusted_virtualenv_build = {
        "applicable": False,
        "valid": False,
        "error": type(exc).__name__ + ": " + str(exc),
    }
'''
_VIRTUALENV_RUNTIME_INSPECTION = r'''\
virtualenv_runtime_artifacts = {"applicable": False, "valid": False}
try:
    environment_root = Path(sys.prefix).resolve()
    configuration = environment_root / "pyvenv.cfg"
    values = {}
    if configuration.is_file():
        for line in configuration.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key.strip()] = value.strip()
    version = values.get("virtualenv")
    environment_site_roots = [
        Path(value).resolve()
        for value in site_roots
        if Path(value).is_dir()
        and Path(value).resolve().is_relative_to(environment_root)
    ]
    pairs = []
    for environment_site_root in sorted(set(environment_site_roots)):
        pth = environment_site_root / "_virtualenv.pth"
        helper = environment_site_root / "_virtualenv.py"
        if not pth.is_file() or not helper.is_file():
            continue
        pth_bytes = pth.read_bytes()
        pairs.append(
            {
                "site_root": str(environment_site_root),
                "relative_paths": ["_virtualenv.pth", "_virtualenv.py"],
                "pth_is_standard": pth_bytes == b"import _virtualenv",
                "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
            }
        )
    virtualenv_runtime_artifacts = {
        "applicable": bool(version or pairs),
        "valid": bool(
            version
            and len(pairs) == 1
            and pairs[0]["pth_is_standard"]
        ),
        "distribution_version": version,
        "environment_root": str(environment_root),
        "pairs": pairs,
    }
except Exception as exc:
    virtualenv_runtime_artifacts = {
        "applicable": True,
        "valid": False,
        "error": type(exc).__name__ + ": " + str(exc),
    }
'''
_UNOWNED_ARTIFACT_WITHOUT_ROOT = '''\
            {
                "audit_kind": "unowned-import-artifact",
                "relative_path": str(path.relative_to(root)),
'''
_UNOWNED_ARTIFACT_WITH_ROOT = '''\
            {
                "audit_kind": "unowned-import-artifact",
                "site_root": str(root.resolve()),
                "relative_path": str(path.relative_to(root)),
'''
_LOCAL_AUDIT_OUTPUT_TAIL = '''\
            "provided_modules": sorted(provided),
'''
_LOCAL_AUDIT_OUTPUT_TAIL_V3 = '''\
            "provided_modules": sorted(provided),
            "trusted_virtualenv_build": trusted_virtualenv_build,
            "virtualenv_runtime_artifacts": virtualenv_runtime_artifacts,
'''

_BASE_NOVEL_LOCAL_DISTRIBUTION_VIOLATIONS = (
    minimal_b_mcp._novel_local_distribution_violations
)

_MANAGED_DEPENDENCY_AUDIT = r"""\
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

project_root = Path(sys.argv[1]).resolve()
marker = sys.argv[2]
payload = {
    "adapter": "open-aea-content-addressed-lock-v1",
    "applicable": False,
    "valid": False,
}

def run(*args, env=None):
    return subprocess.run(
        list(args),
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env=env,
    )

trusted_git_config = None
try:
    system_git = next(
        (value for value in ("/usr/bin/git", "/bin/git") if Path(value).is_file()),
        None,
    )
    if "\n" in str(project_root) or "\r" in str(project_root):
        raise ValueError("project path cannot be represented in Git config")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="envsolve-git-",
        suffix=".config",
        dir="/tmp",
        delete=False,
    ) as handle:
        handle.write("[safe]\n\tdirectory = " + str(project_root) + "\n")
        trusted_git_config = Path(handle.name)
    git_environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    git_environment.update(
        {
            "GIT_CONFIG_GLOBAL": str(trusted_git_config),
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )

    def git(*args):
        if system_git is None:
            raise FileNotFoundError("no trusted system Git executable")
        return run(system_git, *args, env=git_environment)

    inventory = git("ls-tree", "-r", "--name-only", "HEAD")
    lock_paths = [
        value.strip()
        for value in inventory.stdout.splitlines()
        if PurePosixPath(value.strip()).name == "packages.json"
    ] if inventory.returncode == 0 else []
    declared = git(
        "grep", "-l", "-F", "autonomy packages sync", "HEAD", "--"
    )
    declared_by = sorted(
        line.strip() for line in declared.stdout.splitlines() if line.strip()
    ) if declared.returncode == 0 else []
    lock_path = next(
        (value for value in lock_paths if PurePosixPath(value).parent.name == "packages"),
        None,
    )
    executable = shutil.which("autonomy")
    payload["detection"] = {
        "inventory_exit_code": inventory.returncode,
        "inventory_stderr_tail": inventory.stderr[-2000:],
        "lock_paths": lock_paths,
        "declaration_exit_code": declared.returncode,
        "declaration_stderr_tail": declared.stderr[-2000:],
        "declared_by": declared_by,
        "executable": executable,
        "system_git": system_git,
    }
    if lock_path and declared_by and executable:
        payload["applicable"] = True
        payload["package_root"] = str(PurePosixPath(lock_path).parent)
        payload["lock_path"] = lock_path
        payload["declared_by"] = declared_by
        expected = git("show", "HEAD:" + lock_path)
        actual_path = project_root / lock_path
        expected_hash = hashlib.sha256(expected.stdout.encode()).hexdigest()
        actual_hash = hashlib.sha256(actual_path.read_bytes()).hexdigest()
        checked = run(executable, "packages", "lock", "--check")
        payload.update(
            {
                "command": "autonomy packages lock --check",
                "command_exit_code": checked.returncode,
                "command_stdout_tail": checked.stdout[-2000:],
                "command_stderr_tail": checked.stderr[-2000:],
                "lock_matches_revision": (
                    expected.returncode == 0 and expected_hash == actual_hash
                ),
                "lock_sha256": actual_hash,
            }
        )
        payload["valid"] = bool(
            checked.returncode == 0
            and expected.returncode == 0
            and expected_hash == actual_hash
        )
except Exception as exc:
    payload["error"] = type(exc).__name__ + ": " + str(exc)
finally:
    if trusted_git_config is not None:
        trusted_git_config.unlink(missing_ok=True)

print(marker + json.dumps(payload, sort_keys=True))
"""


def boundary_v3_local_distribution_audit() -> str:
    """Add content-derived provenance for standard virtualenv runtime hooks."""
    source = boundary_v2.boundary_v2_local_distribution_audit()
    if _VIRTUALENV_RUNTIME_PROVENANCE in source:
        return source
    replacements = (
        (_VIRTUALENV_AUDIT_IMPORTS, _VIRTUALENV_AUDIT_IMPORTS_V3),
        (
            "marker = sys.argv[2]\n\nprovided = set()",
            (
                "marker = sys.argv[2]\n\n"
                + _VIRTUALENV_RUNTIME_PROVENANCE
                + "\nprovided = set()"
            ),
        ),
        (
            "unowned_import_artifacts = []",
            _VIRTUALENV_RUNTIME_INSPECTION + "\nunowned_import_artifacts = []",
        ),
        (_UNOWNED_ARTIFACT_WITHOUT_ROOT, _UNOWNED_ARTIFACT_WITH_ROOT),
        (_LOCAL_AUDIT_OUTPUT_TAIL, _LOCAL_AUDIT_OUTPUT_TAIL_V3),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError("cannot install boundary-v3 virtualenv audit")
        source = source.replace(old, new, 1)
    return source


def _trusted_virtualenv_runtime_findings(
    baseline: dict[str, Any],
    post: dict[str, Any],
) -> set[tuple[str, str]]:
    build = baseline.get("trusted_virtualenv_build")
    runtime = post.get("virtualenv_runtime_artifacts")
    if not isinstance(build, dict) or not isinstance(runtime, dict):
        return set()
    if build.get("valid") is not True or runtime.get("valid") is not True:
        return set()
    version = build.get("distribution_version")
    if not isinstance(version, str) or runtime.get("distribution_version") != version:
        return set()
    template_hash = build.get("template_sha256")
    pairs = runtime.get("pairs")
    if not isinstance(template_hash, str) or not isinstance(pairs, list):
        return set()
    if len(pairs) != 1 or not isinstance(pairs[0], dict):
        return set()
    pair = pairs[0]
    site_root = pair.get("site_root")
    paths = pair.get("relative_paths")
    if (
        not isinstance(site_root, str)
        or pair.get("pth_is_standard") is not True
        or pair.get("helper_sha256") != template_hash
        or paths != ["_virtualenv.pth", "_virtualenv.py"]
    ):
        return set()
    return {(site_root, path) for path in paths}


def boundary_v3_novel_local_distribution_violations(
    baseline: dict[str, Any],
    post: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = _BASE_NOVEL_LOCAL_DISTRIBUTION_VIOLATIONS(baseline, post)
    trusted = _trusted_virtualenv_runtime_findings(baseline, post)
    return [
        finding
        for finding in findings
        if (
            str(finding.get("site_root", "")),
            str(finding.get("relative_path", "")),
        )
        not in trusted
    ]


def install_boundary_v3_local_distribution_audit() -> None:
    minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT = (
        boundary_v3_local_distribution_audit()
    )
    minimal_b_mcp._novel_local_distribution_violations = (
        boundary_v3_novel_local_distribution_violations
    )


def _managed_dependency_audit_command(project_root: str) -> str:
    return (
        f"command python -I -c {shlex.quote(_MANAGED_DEPENDENCY_AUDIT)} "
        f"{shlex.quote(project_root)} {shlex.quote(MANAGED_DEPENDENCY_MARKER)}"
    )


def _configuration_target(value: str) -> str | None:
    target = value.strip().strip("\"'")
    name = PurePosixPath(target).name
    if name in CONFIGURATION_NAMES or name.startswith("requirements-"):
        return target
    return None


def _python_path_expression(
    node: ast.AST,
    assignments: dict[str, ast.AST],
    *,
    seen: frozenset[str] = frozenset(),
) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return open_program._joined_string(node)
    if isinstance(node, ast.Name):
        if node.id in seen or node.id not in assignments:
            return None
        return _python_path_expression(
            assignments[node.id],
            assignments,
            seen=seen | {node.id},
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
        left = _python_path_expression(node.left, assignments, seen=seen)
        right = _python_path_expression(node.right, assignments, seen=seen)
        if left and right:
            separator = "/" if isinstance(node.op, ast.Div) else ""
            return left.rstrip("/") + separator + right.lstrip("/")
        return right or left
    if not isinstance(node, ast.Call):
        return None
    function = node.func
    if (
        isinstance(function, ast.Name)
        and function.id in {"Path", "PurePath", "PurePosixPath"}
    ) or (
        isinstance(function, ast.Attribute)
        and function.attr in {"join", "joinpath"}
    ):
        values = [
            _python_path_expression(argument, assignments, seen=seen)
            for argument in node.args
        ]
        known = [value for value in values if value]
        return "/".join(value.strip("/") for value in known) if known else None
    return None


def _protected_configuration_write(script: str) -> tuple[str, str] | None:
    for line in script.splitlines():
        for match in open_program._OUTPUT_REDIRECTION.finditer(line):
            target = _configuration_target(match.group("target"))
            if target is not None:
                return line.strip(), target
        for match in open_program._DIRECT_FILE_COMMAND.finditer(line):
            try:
                tokens = shlex.split(match.group("arguments"), posix=True)
            except ValueError:
                tokens = re.findall(
                    r"\"[^\"\n]+\"|'[^'\n]+'|[^\s]+",
                    match.group("arguments"),
                )
            for token in tokens:
                if token.startswith("-"):
                    continue
                target = _configuration_target(token)
                if target is not None:
                    return line.strip(), target

    for source, line_offset in open_program._embedded_python_snippets(script):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        assignments: dict[str, ast.AST] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id] = node.value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            write_target = open_program._call_write_target(node)
            if write_target is None:
                continue
            value = _python_path_expression(write_target, assignments)
            target = _configuration_target(value) if value else None
            if target is None:
                continue
            source_line = source.splitlines()[node.lineno - 1].strip()
            return f"line {line_offset + node.lineno - 1}: {source_line}", target
    return None


class BoundaryV3OpenCandidateProgramValidator(OpenCandidateProgramValidator):
    """Keep the open operation space while making protected config immutable."""

    policy_id = OPEN_PROGRAM_POLICY
    prompt_contract = OpenCandidateProgramValidator.prompt_contract.replace(
        "Use repository build and package tools to materialize real artifacts; a temporary\n"
        "`setup.py` may be used only as a build driver.\n\n",
        "Use repository build and package tools to materialize real artifacts. Do not\n"
        "create or rewrite build, dependency, or verifier configuration, even temporarily.\n\n",
    )

    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        protected_write = _protected_configuration_write(candidate.script)
        if protected_write is not None:
            line, target = protected_write
            return CandidateValidation(
                False,
                self.policy_id,
                reason=(
                    "candidate program writes protected repository configuration"
                ),
                details={"line": line, "target": target},
            )
        validation = super().validate(candidate)
        if not validation.accepted:
            return validation
        return CandidateValidation(
            True,
            self.policy_id,
            normalized_script=validation.normalized_script,
            details={
                **validation.details,
                "interface": self.policy_id,
                "protected_configuration_history": "no-write-observed",
            },
        )


@dataclass(frozen=True)
class BoundaryV3RepositoryIntegrityReport:
    base: RepositoryIntegrityReport
    managed_dependency_provenance: dict[str, Any] | None
    accepted_managed_paths: tuple[str, ...]
    remaining_violations: tuple[Any, ...]

    @property
    def valid(self) -> bool:
        return not self.remaining_violations

    def to_dict(self) -> dict[str, Any]:
        value = self.base.to_dict()
        value.update(
            {
                "policy": REPOSITORY_POLICY,
                "valid": self.valid,
                "base_policy": value.get("policy"),
                "managed_dependency_provenance": (
                    self.managed_dependency_provenance
                ),
                "accepted_managed_paths": list(self.accepted_managed_paths[:256]),
                "accepted_managed_path_count": len(self.accepted_managed_paths),
                "accepted_managed_paths_truncated": (
                    len(self.accepted_managed_paths) > 256
                ),
                "disallowed_untracked_paths": [
                    violation.path
                    for violation in self.remaining_violations
                    if getattr(violation, "path", None) is not None
                ],
                "violations": [
                    violation.to_dict()
                    for violation in self.remaining_violations
                ],
            }
        )
        return value


def _is_ignored(repo_path: Path, path: str) -> bool:
    process = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", path],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return process.returncode == 0


def adjudicate_managed_dependencies(
    repo_path: Path,
    base: RepositoryIntegrityReport,
    provenance: dict[str, Any] | None,
) -> BoundaryV3RepositoryIntegrityReport:
    package_root = (
        provenance.get("package_root")
        if isinstance(provenance, dict) and provenance.get("valid") is True
        else None
    )
    safe_root = None
    if isinstance(package_root, str):
        candidate = PurePosixPath(package_root)
        if (
            candidate.parts
            and not candidate.is_absolute()
            and all(part not in {"", ".", ".."} for part in candidate.parts)
        ):
            safe_root = candidate

    accepted: list[str] = []
    remaining = []
    for violation in base.violations:
        path = violation.path
        pure = PurePosixPath(path) if path is not None else None
        managed = bool(
            safe_root is not None
            and pure is not None
            and violation.kind == "untracked_import_artifact"
            and (pure == safe_root or safe_root in pure.parents)
            and _is_ignored(repo_path, path)
        )
        if managed:
            accepted.append(path)
        else:
            remaining.append(violation)
    return BoundaryV3RepositoryIntegrityReport(
        base=base,
        managed_dependency_provenance=provenance,
        accepted_managed_paths=tuple(sorted(accepted)),
        remaining_violations=tuple(remaining),
    )


class BoundaryV3MinimalBExecutableGoalVerifier(
    BoundaryV2MinimalBExecutableGoalVerifier
):
    """Audit submitted state and content-locked package-manager materialization."""

    check_profile = "minimal-b-executable-goal-contract-boundary-v3"

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        command, completion_marker, report_begin = super()._command(
            candidate,
            handle,
            nonce,
        )
        alias_audit = python_import_alias_audit_command(handle.container_workdir)
        if command.count(alias_audit) != 1:
            raise RuntimeError("cannot install boundary-v3 provenance audit")
        managed_audit = _managed_dependency_audit_command(
            handle.container_workdir
        )
        return (
            command.replace(alias_audit, f"{managed_audit}\n{alias_audit}", 1),
            completion_marker,
            report_begin,
        )

    def _effect_audit(self, handle, result):  # type: ignore[no-untyped-def]
        if self.effect_auditor is None:
            return None, None
        provenance = marked_json_payload(
            result.stdout,
            MANAGED_DEPENDENCY_MARKER,
        )
        try:
            base = self.effect_auditor(handle.worktree)
            if not isinstance(base, RepositoryIntegrityReport):
                return super()._effect_audit(handle, result)
            report = adjudicate_managed_dependencies(
                handle.worktree,
                base,
                provenance,
            )
        except Exception:
            return super()._effect_audit(handle, result)

        original = self.effect_auditor
        self.effect_auditor = lambda _worktree: report
        try:
            return super()._effect_audit(handle, result)
        finally:
            self.effect_auditor = original
