from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path, PurePosixPath
import shlex
import subprocess
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.integrity import (
    IMPORT_ALIAS_AUDIT_MARKER,
    marked_json_payload,
    python_import_alias_audit_command,
)
from envsolve.solver import (
    CounterexampleEvidence,
    DeploymentCandidate,
    ExecutableVerification,
    FeedbackChannel,
)
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve_harness.integrity.repository import ALLOWED_GENERATED_DIRECTORIES


_EVALUATOR_CONFIGURATION_NAMES = {"pyrightconfig.json"}


_PROVIDER_BASELINE_MARKER = "ENVSOLVE_IMPORT_PROVIDER_BASELINE_V1="
_PROVIDER_POST_MARKER = "ENVSOLVE_IMPORT_PROVIDER_POST_V1="
_PROVIDER_AUDIT_SCHEMA = "envsolve-import-provider-provenance-v1"
_UNOWNED_PROVIDER_AUDIT = r"""\
import hashlib
from importlib import metadata
import json
from pathlib import Path
import site
import subprocess
import sysconfig

marker = __import__("sys").argv[1]


def package_distribution_owners():
    resolver = getattr(metadata, "packages_distributions", None)
    if resolver is not None:
        try:
            return resolver()
        except Exception:
            pass

    owners = {}
    for distribution in metadata.distributions():
        distribution_name = distribution.metadata.get("Name", "unknown")
        modules = set()
        top_level = distribution.read_text("top_level.txt")
        if top_level:
            modules.update(
                line.strip()
                for line in top_level.splitlines()
                if line.strip().isidentifier()
            )
        else:
            for relative_path in distribution.files or ():
                parts = Path(str(relative_path)).parts
                if not parts:
                    continue
                first = parts[0]
                if first.endswith((".dist-info", ".egg-info")):
                    continue
                module = Path(first).stem if len(parts) == 1 else first
                if module.isidentifier():
                    modules.add(module)
        for module in modules:
            owners.setdefault(module, []).append(distribution_name)
    return owners


owners = package_distribution_owners()
owned_artifacts = set()
for distribution in metadata.distributions():
    for relative_path in distribution.files or ():
        try:
            owned_artifacts.add(
                str(Path(distribution.locate_file(relative_path)).resolve(strict=True))
            )
        except (OSError, RuntimeError):
            pass


def has_system_package_owner(path):
    commands = (
        (Path("/usr/bin/dpkg-query"), "-S", str(path)),
        (Path("/usr/bin/rpm"), "-qf", str(path)),
        (Path("/bin/rpm"), "-qf", str(path)),
        (Path("/sbin/apk"), "info", "--who-owns", str(path)),
        (Path("/usr/sbin/apk"), "info", "--who-owns", str(path)),
    )
    for command in commands:
        if not command[0].is_file():
            continue
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            continue
        if completed.returncode == 0:
            return True
    return False


roots = set()
try:
    roots.update(site.getsitepackages())
except Exception:
    pass
try:
    roots.add(site.getusersitepackages())
except Exception:
    pass
for key in ("purelib", "platlib"):
    value = sysconfig.get_paths().get(key)
    if value:
        roots.add(value)

artifacts = []
seen = set()
for encoded_root in sorted(roots):
    root = Path(encoded_root)
    if not root.is_dir():
        continue
    for path in root.iterdir():
        proof = None
        kind = None
        if path.is_file() and path.suffix in {".py", ".pyi", ".so", ".pyd"}:
            module = path.name.split(".", 1)[0]
            proof = path
            kind = "module-file"
        elif path.is_dir() and (path / "__init__.py").is_file():
            module = path.name
            proof = path / "__init__.py"
            kind = "package"
        else:
            continue
        if not module.isidentifier() or module.startswith("_") or owners.get(module):
            continue
        try:
            resolved = proof.resolve(strict=True)
            payload = resolved.read_bytes()
        except (OSError, RuntimeError):
            continue
        if str(resolved) in owned_artifacts or has_system_package_owner(resolved):
            continue
        identity = (module, str(resolved), hashlib.sha256(payload).hexdigest())
        if identity in seen:
            continue
        seen.add(identity)
        artifacts.append({
            "module": module,
            "artifact_kind": kind,
            "artifact_path": str(resolved),
            "artifact_sha256": identity[2],
            "artifact_bytes": len(payload),
            "reason": "public site-packages provider has no distribution owner",
        })

print(marker + json.dumps({
    "schema": "envsolve-import-provider-provenance-v1",
    "unowned_public_site_providers": sorted(
        artifacts, key=lambda item: (item["module"], item["artifact_path"])
    ),
}, sort_keys=True))
"""


def _provider_audit_command(marker: str) -> str:
    return (
        f"command python -I -c {shlex.quote(_UNOWNED_PROVIDER_AUDIT)} "
        f"{shlex.quote(marker)}"
    )


def _novel_unowned_provider_violations(
    baseline: dict[str, Any],
    post: dict[str, Any],
) -> list[dict[str, Any]]:
    for report in (baseline, post):
        if report.get("schema") != _PROVIDER_AUDIT_SCHEMA or not isinstance(
            report.get("unowned_public_site_providers"), list
        ):
            raise ValueError("import provider provenance report is malformed")

    def identity(item: Any) -> tuple[str, str, str]:
        if not isinstance(item, dict):
            raise ValueError("import provider provenance item is malformed")
        module = item.get("module")
        path = item.get("artifact_path")
        digest = item.get("artifact_sha256")
        values = (module, path, digest)
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError("import provider provenance identity is malformed")
        return str(module), str(path), str(digest)

    known = {
        identity(item) for item in baseline["unowned_public_site_providers"]
    }
    return [
        item
        for item in post["unowned_public_site_providers"]
        if identity(item) not in known
    ]


@dataclass(frozen=True)
class MinimalIntegrityViolation:
    kind: str
    path: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MinimalRepositoryIntegrityReport:
    expected_revision: str
    checked_out_revision: str | None
    tracked_changes: tuple[str, ...]
    untracked_evaluator_artifacts: tuple[str, ...]
    evaluator_artifacts_protected: bool
    violations: tuple[MinimalIntegrityViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "minimal-repository-and-adapter-integrity-v1",
            "valid": self.valid,
            "expected_revision": self.expected_revision,
            "checked_out_revision": self.checked_out_revision,
            "tracked_changes": list(self.tracked_changes),
            "untracked_evaluator_artifacts": list(
                self.untracked_evaluator_artifacts
            ),
            "untracked_deployment_artifacts_are_semantically_gated": (
                self.evaluator_artifacts_protected
            ),
            "violations": [item.to_dict() for item in self.violations],
        }


def _git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _nul_paths(value: str) -> tuple[str, ...]:
    return tuple(sorted(path for path in value.split("\0") if path))


def inspect_minimal_repository_integrity(
    repo_path: Path,
    expected_revision: str,
    required_preconditions: tuple[WorkspacePrecondition, ...] = (),
    *,
    protect_evaluator_artifacts: bool = False,
) -> MinimalRepositoryIntegrityReport:
    """Protect the checkout and adapter state, while allowing deployment outputs."""

    violations: list[MinimalIntegrityViolation] = []
    head = _git(repo_path, "rev-parse", "HEAD")
    checked_out_revision = head.stdout.strip() if head.returncode == 0 else None
    if head.returncode != 0:
        violations.append(
            MinimalIntegrityViolation("git_error", None, head.stderr.strip())
        )
    elif checked_out_revision != expected_revision:
        violations.append(
            MinimalIntegrityViolation(
                "revision_mismatch",
                None,
                f"checked out {checked_out_revision}, expected {expected_revision}",
            )
        )

    unstaged = _git(repo_path, "diff", "--name-only", "-z", "HEAD", "--")
    staged = _git(repo_path, "diff", "--cached", "--name-only", "-z", "HEAD", "--")
    tracked_changes = _nul_paths(unstaged.stdout + staged.stdout)
    for process, label in ((unstaged, "unstaged diff"), (staged, "staged diff")):
        if process.returncode != 0:
            violations.append(
                MinimalIntegrityViolation(
                    "git_error",
                    None,
                    f"{label}: {process.stderr.strip()}",
                )
            )
    violations.extend(
        MinimalIntegrityViolation(
            "tracked_change",
            path,
            "tracked repository files must remain unchanged",
        )
        for path in tracked_changes
    )
    evaluator_artifacts: tuple[str, ...] = ()
    if protect_evaluator_artifacts:
        evaluator_pathspecs = (
            ":(glob)**/*.pyi",
            ":(glob)**/pyrightconfig.json",
        )
        untracked = _git(
            repo_path,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *evaluator_pathspecs,
        )
        ignored = _git(
            repo_path,
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
            "--",
            *evaluator_pathspecs,
        )
        for process, label in ((untracked, "untracked files"), (ignored, "ignored files")):
            if process.returncode != 0:
                violations.append(
                    MinimalIntegrityViolation(
                        "git_error",
                        None,
                        f"{label}: {process.stderr.strip()}",
                    )
                )
        candidates = set(_nul_paths(untracked.stdout + ignored.stdout))

        def changes_evaluator(path: str) -> bool:
            pure = PurePosixPath(path)
            if any(
                part in ALLOWED_GENERATED_DIRECTORIES or part.endswith(".egg-info")
                for part in pure.parts
            ):
                return False
            return (
                pure.suffix.lower() == ".pyi"
                or pure.name in _EVALUATOR_CONFIGURATION_NAMES
            )

        evaluator_artifacts = tuple(sorted(filter(changes_evaluator, candidates)))
        violations.extend(
            MinimalIntegrityViolation(
                "untracked_evaluator_artifact",
                path,
                (
                    "untracked type-only providers and evaluator configuration "
                    "must not change the public goal's meaning"
                ),
            )
            for path in evaluator_artifacts
        )
    violations.extend(
        MinimalIntegrityViolation(
            "workspace_precondition_missing",
            item.path,
            f"{item.kind} owned by {item.producer} must remain present",
        )
        for item in required_preconditions
        if not item.satisfied_by(repo_path)
    )
    return MinimalRepositoryIntegrityReport(
        expected_revision=expected_revision,
        checked_out_revision=checked_out_revision,
        tracked_changes=tracked_changes,
        untracked_evaluator_artifacts=evaluator_artifacts,
        evaluator_artifacts_protected=protect_evaluator_artifacts,
        violations=tuple(violations),
    )


class MinimalIntegrityGoalVerifier(ExecutableGoalContractVerifier):
    """Run the shared goal and reject newly unowned site-package providers."""

    check_profile = "executable-goal-minimal-integrity-v2"

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
        baseline_path = f"/tmp/envsolve-import-provider-baseline-{nonce}.jsonl"
        command = (
            f"{_provider_audit_command(_PROVIDER_BASELINE_MARKER)} "
            f"> {shlex.quote(baseline_path)}\n{command}"
        )
        completion_line = f"printf '%s\\n' {shlex.quote(completion_marker)}"
        if command.count(completion_line) != 1:
            raise RuntimeError("cannot instrument import provider post-audit")
        post_audit = _provider_audit_command(_PROVIDER_POST_MARKER)
        command = command.replace(
            completion_line,
            "\n".join(
                (
                    f"if {post_audit}; then :; else :; fi",
                    (
                        f"if [ -f {shlex.quote(baseline_path)} ]; then "
                        f"cat {shlex.quote(baseline_path)}; fi"
                    ),
                    f"rm -f {shlex.quote(baseline_path)}",
                    completion_line,
                )
            ),
            1,
        )
        legacy_audit = python_import_alias_audit_command(handle.container_workdir)
        if command.count(legacy_audit) != 1:
            raise RuntimeError("cannot isolate the legacy import-provenance gate")
        marker_payload = IMPORT_ALIAS_AUDIT_MARKER + json.dumps(
            {
                "valid": True,
                "violations": [],
                "performed": False,
                "reason": "deployment provenance is a measured outcome, not a hard gate",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        replacement = f"printf '%s\\n' {shlex.quote(marker_payload)}"
        return (
            command.replace(legacy_audit, replacement, 1),
            completion_marker,
            report_begin,
        )

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: Any,
    ) -> ExecutableVerification:
        outcome = super().verify(candidate, environment)
        if outcome.passed is not True:
            return outcome
        baseline = marked_json_payload(
            outcome.bootstrap.stdout,
            _PROVIDER_BASELINE_MARKER,
        )
        post = marked_json_payload(
            outcome.bootstrap.stdout,
            _PROVIDER_POST_MARKER,
        )
        if baseline is None or post is None:
            return self._unknown(
                outcome.bootstrap,
                "Import provider provenance audit did not complete",
                {
                    "import_provider_provenance": {
                        "baseline_present": baseline is not None,
                        "post_present": post is not None,
                    }
                },
            )
        try:
            violations = _novel_unowned_provider_violations(baseline, post)
        except ValueError as exc:
            return self._unknown(
                outcome.bootstrap,
                "Import provider provenance audit was malformed",
                {"import_provider_provenance_error": str(exc)},
            )
        if not violations:
            return outcome
        audit = {
            "valid": False,
            "scope": "candidate-introduced-public-site-packages-providers",
            "violations": violations,
        }
        return ExecutableVerification(
            verifier="envsolve-minimal-integrity-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=False,
            bootstrap=outcome.bootstrap,
            summary=(
                "Candidate introduced a site-packages import provider without "
                "installed-distribution ownership"
            ),
            counterexamples=(
                CounterexampleEvidence("import-provider-provenance", audit),
            ),
            details={
                "goal_verification": outcome.details,
                "import_provider_provenance": audit,
            },
        )
