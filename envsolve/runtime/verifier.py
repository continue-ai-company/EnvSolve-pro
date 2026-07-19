from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
import time
from typing import Callable

from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from envsolve.constraints import InitialConstraintEvidence
from envsolve.constraints.models import ConstraintDomain, ConstraintPredicate
from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.import_probe import ImportInventory, collect_source_imports
from envsolve.solver import (
    CommandResult,
    DeploymentCandidate,
    ExecutableVerification,
    FeedbackChannel,
    HypothesisEvidence,
    ProvisionedEnvironment,
)
from envsolve.verification.counterexamples import (
    FindingDisposition,
    StructuredFindingAdapter,
    StructuredVerifierFinding,
    StructuredVerifierReport,
)
from envsolve.verification.imports import (
    EnvironmentFacts,
    ImportContextAnalyzer,
    MissingImportFinding,
)
from envsolve.verification.obligations import (
    ObligationDisposition,
    ResolutionStatus,
    decide_import_obligation,
)


RunCommand = Callable[..., subprocess.CompletedProcess[str]]
_PROBE_MARKER = "ENVSOLVE_IMPORT_PROBE_V3="
_FAILED_ACTION_MARKER = re.compile(
    r"^ENVSOLVE_FAILED_ACTION_V1=(?P<index>[0-9]+|internal):(?P<exit_code>[0-9]+)$",
    re.MULTILINE,
)
_NETWORK_FAILURES = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("read-timeout", r"ReadTimeout(?:Error)?"),
        ("connection-error", r"ConnectionError"),
        ("dns-temporary-failure", r"Temporary failure in name resolution"),
        ("dns-resolution-failure", r"Could not resolve host"),
        ("tls-timeout", r"TLSV?\s+handshake.*timed out"),
        ("network-unreachable", r"network is unreachable"),
        (
            "upstream-http-5xx",
            r"\b(?:500 Internal Server Error|502 Bad Gateway|503 Service Unavailable|504 Gateway Time-?out)\b",
        ),
        ("apt-connection-failed", r"\bConnection failed \[IP:[^\]]+\]"),
    )
)
_INFRASTRUCTURE_FAILURES = (
    (
        "artifact-hash-mismatch",
        re.compile(r"PACKAGES DO NOT MATCH THE HASHES", re.IGNORECASE),
    ),
)
_IMPORT_PROBE = """\
import importlib
import importlib.machinery
from importlib import metadata
import json
import platform
from pathlib import Path
import sys

modules = json.loads(sys.argv[1])
package_names = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
packages = {}
for name in package_names:
    try:
        packages[name] = {
            \"status\": \"resolved\",
            \"version\": metadata.version(name),
        }
    except metadata.PackageNotFoundError:
        packages[name] = {\"status\": \"missing\"}
    except Exception as exc:
        packages[name] = {
            \"status\": \"unknown\",
            \"error\": f\"{type(exc).__name__}: {exc}\"[:1000],
        }
runtime = {}
for module in modules:
    try:
        loaded = importlib.import_module(module)
        spec = getattr(loaded, \"__spec__\", None)
        runtime[module] = {
            \"status\": \"resolved\",
            \"kind\": \"import\",
            \"origin\": getattr(spec, \"origin\", None),
        }
    except ModuleNotFoundError as exc:
        runtime[module] = {
            \"status\": \"missing\",
            \"kind\": \"missing\",
            \"error\": str(exc)[:1000],
            \"missing_name\": exc.name,
        }
    except ImportError as exc:
        runtime[module] = {
            \"status\": \"unknown\",
            \"kind\": \"import_error\",
            \"error\": str(exc)[:1000],
        }
    except Exception as exc:
        runtime[module] = {
            \"status\": \"unknown\",
            \"kind\": \"execution_error\",
            \"error\": f\"{type(exc).__name__}: {exc}\"[:1000],
        }

suffixes = tuple(
    dict.fromkeys(
        (\".pyi\",)
        + tuple(importlib.machinery.SOURCE_SUFFIXES)
        + tuple(importlib.machinery.EXTENSION_SUFFIXES)
        + tuple(importlib.machinery.BYTECODE_SUFFIXES)
    )
)
search_roots = []
archive_roots = []
for entry in sys.path:
    path = Path(entry or \".\").resolve()
    if path.is_dir():
        search_roots.append(path)
    elif path.is_file():
        archive_roots.append(str(path))


def physical_resolution(module):
    parts = module.split(\".\")
    if not parts or any(not part or not part.isidentifier() for part in parts):
        return {\"status\": \"unknown\", \"kind\": \"invalid_module_name\"}
    layouts = (parts, (parts[0] + \"-stubs\", *parts[1:]))
    for root in search_roots:
        for layout in layouts:
            current = root
            for index, part in enumerate(layout):
                terminal = index == len(layout) - 1
                directory = current / part
                file_match = next(
                    (
                        current / (part + suffix)
                        for suffix in suffixes
                        if (current / (part + suffix)).is_file()
                    ),
                    None,
                )
                if terminal and file_match is not None:
                    return {
                        \"status\": \"resolved\",
                        \"kind\": \"physical_file\",
                        \"path\": str(file_match),
                    }
                if directory.is_dir():
                    if terminal:
                        return {
                            \"status\": \"resolved\",
                            \"kind\": \"physical_package\",
                            \"path\": str(directory),
                        }
                    current = directory
                    continue
                break
    return None


def origin_matches_module(module, origin):
    if not isinstance(origin, str) or origin.startswith(\"<\"):
        return False
    path = Path(origin)
    parts = module.split(\".\")
    if path.name.startswith(\"__init__.\"):
        observed = path.parent.parts[-len(parts) :]
    else:
        stem = next(
            (
                path.name[: -len(suffix)]
                for suffix in suffixes
                if path.name.endswith(suffix)
            ),
            None,
        )
        if stem is None:
            return False
        parent_tail = path.parent.parts[-(len(parts) - 1) :] if len(parts) > 1 else ()
        observed = (*parent_tail, stem)
    return tuple(observed) == tuple(parts)


static = {}
stdlib = getattr(sys, \"stdlib_module_names\", frozenset())
for module in modules:
    physical = physical_resolution(module)
    if physical is not None:
        static[module] = physical
        continue
    observation = runtime[module]
    origin = observation.get(\"origin\")
    if module.split(\".\", 1)[0] in stdlib:
        static[module] = {\"status\": \"resolved\", \"kind\": \"stdlib\"}
    elif origin_matches_module(module, origin):
        static[module] = {
            \"status\": \"resolved\",
            \"kind\": \"mapped_physical_origin\",
            \"origin\": origin,
        }
    elif isinstance(origin, str) and any(
        token in origin for token in (\".zip/\", \".egg/\", \".whl/\")
    ):
        static[module] = {
            \"status\": \"resolved\",
            \"kind\": \"archive_origin\",
            \"origin\": origin,
        }
    elif archive_roots and observation[\"status\"] != \"resolved\":
        static[module] = {
            \"status\": \"unknown\",
            \"kind\": \"unsupported_archive_search\",
            \"archives\": archive_roots[:20],
        }
    elif observation[\"status\"] == \"resolved\" and (
        origin is None or (isinstance(origin, str) and origin.startswith(\"<\"))
    ):
        static[module] = {
            \"status\": \"unknown\",
            \"kind\": \"unsupported_importer\",
            \"origin\": origin,
        }
    else:
        static[module] = {
            \"status\": \"missing\",
            \"kind\": \"no_static_path\",
            \"runtime_status\": observation[\"status\"],
            \"runtime_origin\": origin,
        }
print(
    \"ENVSOLVE_IMPORT_PROBE_V3=\"
    + json.dumps(
        {
            \"facts\": {
                \"sys_platform\": sys.platform,
                \"python_major\": sys.version_info[0],
                \"python_version\": platform.python_version(),
                \"python_implementation\": platform.python_implementation(),
                \"platform_name\": platform.system(),
            },
            \"runtime\": runtime,
            \"static\": static,
            \"packages\": packages,
        },
        sort_keys=True,
    )
)
"""


@dataclass(frozen=True)
class _PackageRequirement:
    evidence_id: str
    source: str
    name: str
    specifier: str | None


class PythonDeploymentVerifier:
    """Fixed internal Python checks with no benchmark evaluator dependency."""

    check_profile = "python-deployment-v5"

    def __init__(
        self,
        *,
        command_timeout: int = 900,
        collect_tests: bool = True,
        obligation_profile: str = "two-layer",
        package_requirements: tuple[InitialConstraintEvidence, ...] = (),
        run_command: RunCommand = subprocess.run,
    ) -> None:
        if obligation_profile not in {"two-layer", "runtime-only"}:
            raise ValueError("Unknown import obligation profile")
        self.command_timeout = command_timeout
        self.collect_tests = collect_tests
        self.obligation_profile = obligation_profile
        self.check_profile = (
            "python-deployment-v5"
            if obligation_profile == "two-layer"
            else "python-deployment-v5-runtime-only-ablation"
        )
        parsed_requirements: list[_PackageRequirement] = []
        for item in package_requirements:
            if item.kind != "package-requirement":
                raise ValueError("Python verifier accepts only package requirements")
            name = item.value.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Package requirement name cannot be empty")
            specifier = item.value.get("specifier")
            if specifier is not None:
                specifier = str(SpecifierSet(str(specifier)))
            parsed_requirements.append(
                _PackageRequirement(
                    item.evidence_id,
                    item.source,
                    canonicalize_name(name),
                    specifier,
                )
            )
        self.package_requirements = tuple(parsed_requirements)
        self.run_command = run_command
        self.import_analyzer = ImportContextAnalyzer()
        self.finding_adapter = StructuredFindingAdapter()

    @staticmethod
    def _has_tests(worktree: Path) -> bool:
        return any((worktree / name).is_dir() for name in ("test", "tests")) or any(
            worktree.glob("test_*.py")
        )

    @staticmethod
    def _candidate_commands(script: str) -> tuple[str, ...]:
        return tuple(
            value
            for line in script.splitlines()
            if (value := line.strip())
            and not value.startswith("#")
            and not value.startswith("set ")
        )

    @classmethod
    def _instrument_candidate(
        cls, script: str
    ) -> tuple[str, tuple[str, ...]]:
        commands = cls._candidate_commands(script)
        lines = [
            "set -euo pipefail",
            "trap 'rc=$?; printf \"ENVSOLVE_FAILED_ACTION_V1=%s:%s\\n\" "
            '"${ENVSOLVE_ACTION_INDEX:-internal}" "$rc" >&2; exit "$rc"\' ERR',
        ]
        for index, command in enumerate(commands):
            lines.extend((f"ENVSOLVE_ACTION_INDEX={index}", command))
        lines.append("ENVSOLVE_ACTION_INDEX=internal")
        return "\n".join(lines), commands

    @staticmethod
    def _failed_candidate_action(
        stderr: str,
        commands: tuple[str, ...],
    ) -> dict[str, object] | None:
        matches = tuple(_FAILED_ACTION_MARKER.finditer(stderr))
        if not matches:
            return None
        match = matches[-1]
        raw_index = match.group("index")
        if raw_index == "internal":
            return None
        index = int(raw_index)
        if index >= len(commands):
            return None
        return {
            "action_index": index,
            "command": commands[index],
            "prefix_commands": list(commands[: index + 1]),
            "exit_code": int(match.group("exit_code")),
        }

    @staticmethod
    def _failure_details(
        checks: list[str],
        failed_action: dict[str, object] | None,
        **extra: object,
    ) -> dict[str, object]:
        details: dict[str, object] = {"checks": checks, **extra}
        if failed_action is not None:
            details["failed_candidate_action"] = failed_action
        return details

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
    ) -> ExecutableVerification:
        handle = environment.handle
        if not isinstance(handle, DockerEnvironmentHandle):
            raise ValueError("Python verifier requires a Docker environment handle")
        inventory = collect_source_imports(handle.worktree)
        checks = ["python -m pip check", "python -m compileall -q ."]
        if self.collect_tests and self._has_tests(handle.worktree):
            checks.append("python -m pytest --collect-only -q")
        probe = "python -I -c {code} {modules} {packages}".format(
            code=shlex.quote(_IMPORT_PROBE),
            modules=shlex.quote(json.dumps(inventory.modules)),
            packages=shlex.quote(
                json.dumps(sorted({item.name for item in self.package_requirements}))
            ),
        )
        instrumented_candidate, candidate_commands = self._instrument_candidate(
            candidate.script
        )
        command = "\n".join([instrumented_candidate, *checks, probe])
        started = time.monotonic()
        timed_out = False
        try:
            process = self.run_command(
                [
                    "docker",
                    "exec",
                    "--workdir",
                    handle.container_workdir,
                    handle.container_id,
                    "/bin/bash",
                    "-lc",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.command_timeout,
            )
            result = CommandResult(
                process.returncode,
                process.stdout,
                process.stderr,
                time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            result = CommandResult(
                124,
                stdout,
                f"{stderr}\nInternal verification timed out".strip(),
                time.monotonic() - started,
            )
        failed_action = self._failed_candidate_action(
            result.stderr,
            candidate_commands,
        )
        if result.exit_code == 0:
            return self._evaluate_import_probe(result, inventory, environment, checks)
        infrastructure_failure = self._infrastructure_failure(result)
        if infrastructure_failure is not None:
            return ExecutableVerification(
                verifier="envsolve-python-deployment-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=None,
                bootstrap=result,
                summary="Candidate execution was blocked by infrastructure failure",
                hypotheses=(
                    HypothesisEvidence(
                        hypothesis_id=f"hypothesis-{candidate.candidate_id}-infrastructure",
                        statement="Dependency acquisition encountered infrastructure failure",
                        value={
                            "signature": infrastructure_failure,
                            "exit_code": result.exit_code,
                        },
                        confidence=1.0,
                    ),
                ),
                details=self._failure_details(
                    checks,
                    failed_action,
                    infrastructure_error="dependency_acquisition_failure",
                    infrastructure_signature=infrastructure_failure,
                ),
            )
        if timed_out:
            return ExecutableVerification(
                verifier="envsolve-python-deployment-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=result,
                summary="Candidate exceeded the fixed execution time limit",
                hypotheses=(
                    HypothesisEvidence(
                        hypothesis_id=f"hypothesis-{candidate.candidate_id}-execution-timeout",
                        statement="The candidate must reduce installation or verification cost",
                        value={
                            "command_timeout_seconds": self.command_timeout,
                            "exit_code": result.exit_code,
                        },
                        confidence=1.0,
                    ),
                ),
                details=self._failure_details(
                    checks,
                    failed_action,
                    execution_timeout=True,
                    command_timeout_seconds=self.command_timeout,
                ),
            )
        value = {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "deterministic_counterexample": False,
            "check_profile": self.check_profile,
        }
        return ExecutableVerification(
            verifier="envsolve-python-deployment-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=False,
            bootstrap=result,
            summary="Complete candidate failed fixed internal Python checks",
            hypotheses=(
                HypothesisEvidence(
                    hypothesis_id=f"hypothesis-{candidate.candidate_id}-internal-check",
                    statement="The complete deployment candidate failed an internal check",
                    value=value,
                    confidence=0.6,
                ),
            ),
            details=self._failure_details(checks, failed_action),
        )

    @staticmethod
    def _infrastructure_failure(result: CommandResult) -> str | None:
        logs = result.stdout + "\n" + result.stderr
        return next(
            (
                name
                for name, pattern in (*_NETWORK_FAILURES, *_INFRASTRUCTURE_FAILURES)
                if pattern.search(logs)
            ),
            None,
        )

    def _evaluate_import_probe(
        self,
        result: CommandResult,
        inventory: ImportInventory,
        environment: ProvisionedEnvironment,
        checks: list[str],
    ) -> ExecutableVerification:
        payload = self._probe_payload(result.stdout)
        if payload is None:
            return ExecutableVerification(
                verifier="envsolve-python-deployment-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=None,
                bootstrap=result,
                summary="Internal import probe did not produce a valid report",
                hypotheses=(
                    HypothesisEvidence(
                        hypothesis_id="hypothesis-import-probe-malformed",
                        statement="The fixed import-closure probe was incomplete",
                        value={"probe_marker": _PROBE_MARKER},
                        confidence=1.0,
                    ),
                ),
                details={"checks": checks, "import_inventory": self._inventory_details(inventory)},
            )
        facts_value = payload.get("facts")
        runtime = payload.get("runtime")
        static = payload.get("static")
        packages_value = payload.get("packages", {})
        if (
            not isinstance(facts_value, dict)
            or not isinstance(runtime, dict)
            or not isinstance(static, dict)
            or not isinstance(packages_value, dict)
        ):
            return ExecutableVerification(
                verifier="envsolve-python-deployment-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=None,
                bootstrap=result,
                summary="Internal import probe report has an invalid schema",
                details={"checks": checks, "import_inventory": self._inventory_details(inventory)},
            )
        try:
            facts = EnvironmentFacts(
                sys_platform=str(facts_value["sys_platform"]),
                python_major=int(facts_value["python_major"]),
                platform_name=str(facts_value["platform_name"]),
            )
        except (KeyError, TypeError, ValueError):
            return ExecutableVerification(
                verifier="envsolve-python-deployment-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=None,
                bootstrap=result,
                summary="Internal import probe facts are invalid",
                details={"checks": checks, "import_inventory": self._inventory_details(inventory)},
            )
        environment_facts = {
            key: facts_value[key]
            for key in (
                "sys_platform",
                "python_major",
                "python_version",
                "python_implementation",
                "platform_name",
            )
            if key in facts_value
        }

        runtime_statuses = {
            module: self._resolution_status(runtime.get(module))
            for module in inventory.modules
        }
        static_statuses = {
            module: self._resolution_status(static.get(module))
            for module in inventory.modules
        }
        occurrence_counts = {module: 0 for module in inventory.modules}
        occurrence_paths: dict[str, set[str]] = {
            module: set() for module in inventory.modules
        }
        for occurrence in inventory.occurrences:
            occurrence_counts[occurrence.module] += 1
            occurrence_paths[occurrence.module].add(occurrence.path)
        resolved_modules = {
            module
            for module in inventory.modules
            if runtime_statuses[module] is ResolutionStatus.RESOLVED
            and (
                self.obligation_profile != "two-layer"
                or static_statuses[module] is ResolutionStatus.RESOLVED
            )
        }
        findings = self._package_findings(packages_value, environment_facts)
        findings.extend(
            StructuredVerifierFinding(
                finding_id="resolved-import-"
                + hashlib.sha256(module.encode()).hexdigest()[:20],
                domain=ConstraintDomain.MODULE,
                subject=module,
                predicate=ConstraintPredicate.PRESENT,
                required=True,
                observed=True,
                disposition=FindingDisposition.SATISFIED,
                provenance={
                    "occurrence_count": occurrence_counts[module],
                    "paths": sorted(occurrence_paths[module])[:20],
                    "runtime_observation": runtime.get(module),
                    "static_observation": static.get(module),
                    "environment_facts": environment_facts,
                    "required_layers": (
                        ["runtime_semantic", "static_source"]
                        if self.obligation_profile == "two-layer"
                        else ["runtime_semantic"]
                    ),
                },
            )
            for module in sorted(resolved_modules)
        )
        for occurrence in inventory.occurrences:
            runtime_observation = runtime.get(occurrence.module)
            static_observation = static.get(occurrence.module)
            runtime_status = runtime_statuses[occurrence.module]
            static_status = static_statuses[occurrence.module]
            if occurrence.module in resolved_modules:
                continue
            runtime_value = (
                runtime_observation if isinstance(runtime_observation, dict) else {}
            )
            static_value = (
                static_observation if isinstance(static_observation, dict) else {}
            )
            assessment = self.import_analyzer.assess(
                MissingImportFinding(
                    occurrence.module,
                    occurrence.path,
                    occurrence.line,
                    str(
                        runtime_value.get("error")
                        or static_value.get("kind")
                        or "module resolution is incomplete"
                    ),
                ),
                occurrence.source,
                facts,
            )
            decision = decide_import_obligation(
                assessment,
                runtime_status,
                static_status,
                fallback_modules=occurrence.fallback_modules,
                runtime_statuses=runtime_statuses,
                static_layer_enabled=self.obligation_profile == "two-layer",
            )
            disposition = FindingDisposition(decision.disposition.value)
            finding_key = (
                f"{occurrence.module}\0{occurrence.path}\0{occurrence.line}"
            ).encode()
            findings.append(
                StructuredVerifierFinding(
                    finding_id="import-" + hashlib.sha256(finding_key).hexdigest()[:20],
                    domain=ConstraintDomain.MODULE,
                    subject=occurrence.module,
                    predicate=ConstraintPredicate.PRESENT,
                    required=True,
                    observed=False if disposition is FindingDisposition.ACTIVE else None,
                    disposition=disposition,
                    provenance={
                        "path": occurrence.path,
                        "line": occurrence.line,
                        "semantic_disposition": assessment.disposition.value,
                        "fallback_modules": list(occurrence.fallback_modules),
                        "required_layers": [
                            layer.value for layer in decision.required_layers
                        ],
                        "active_layers": [
                            layer.value for layer in decision.active_layers
                        ],
                        "unknown_layers": [
                            layer.value for layer in decision.unknown_layers
                        ],
                        "runtime_observation": runtime_value,
                        "static_observation": static_value,
                        "environment_facts": environment_facts,
                        "evidence": [
                            {
                                "kind": item.kind,
                                "detail": item.detail,
                                "source_sha256": item.source_sha256,
                                "line": item.line,
                            }
                            for item in assessment.evidence
                        ],
                    },
                )
            )
        active = sum(item.disposition is FindingDisposition.ACTIVE for item in findings)
        unknown = sum(item.disposition is FindingDisposition.UNKNOWN for item in findings)
        goal_passed = False if active else (None if unknown else True)
        report = StructuredVerifierReport(
            verifier="envsolve-python-deployment-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            environment_id=environment.receipt.environment_id,
            environment_fresh=True,
            bootstrap=result,
            completed=True,
            goal_passed=goal_passed,
            findings=tuple(findings),
            details={
                "checks": [*checks, "project-source-import-closure"],
                "import_inventory": self._inventory_details(inventory),
                "runtime_unresolved_modules": sorted(
                    module
                    for module, status in runtime_statuses.items()
                    if status is not ResolutionStatus.RESOLVED
                ),
                "static_unresolved_modules": sorted(
                    module
                    for module, status in static_statuses.items()
                    if status is not ResolutionStatus.RESOLVED
                ),
                "obligation_contract": (
                    "two-layer-import-obligations-v1"
                    if self.obligation_profile == "two-layer"
                    else "runtime-semantic-ablation-v1"
                ),
                "package_requirements": len(self.package_requirements),
                "package_unresolved": sorted(
                    {
                        item.subject
                        for item in findings
                        if item.domain is ConstraintDomain.PACKAGE
                        and item.disposition
                        in {FindingDisposition.ACTIVE, FindingDisposition.UNKNOWN}
                    }
                ),
                "environment_facts": environment_facts,
            },
        )
        return self.finding_adapter.adapt(report)

    def _package_findings(
        self,
        packages: dict[str, object],
        environment_facts: dict[str, object],
    ) -> list[StructuredVerifierFinding]:
        findings: list[StructuredVerifierFinding] = []
        for requirement in self.package_requirements:
            raw_observation = packages.get(requirement.name)
            observation = (
                raw_observation if isinstance(raw_observation, dict) else {}
            )
            status = self._resolution_status(observation)
            provenance = {
                "repository_evidence_id": requirement.evidence_id,
                "repository_evidence_source": requirement.source,
                "package_observation": observation,
                "environment_facts": environment_facts,
            }
            presence_disposition = (
                FindingDisposition.SATISFIED
                if status is ResolutionStatus.RESOLVED
                else FindingDisposition.ACTIVE
                if status is ResolutionStatus.MISSING
                else FindingDisposition.UNKNOWN
            )
            findings.append(
                StructuredVerifierFinding(
                    finding_id=f"{requirement.evidence_id}-presence",
                    domain=ConstraintDomain.PACKAGE,
                    subject=requirement.name,
                    predicate=ConstraintPredicate.PRESENT,
                    required=True,
                    observed=(
                        True
                        if presence_disposition is FindingDisposition.SATISFIED
                        else False
                        if presence_disposition is FindingDisposition.ACTIVE
                        else None
                    ),
                    disposition=presence_disposition,
                    provenance=provenance,
                )
            )
            if requirement.specifier is None or status is not ResolutionStatus.RESOLVED:
                continue
            version_value = observation.get("version")
            try:
                version = Version(str(version_value))
            except InvalidVersion:
                findings.append(
                    StructuredVerifierFinding(
                        finding_id=f"{requirement.evidence_id}-version",
                        domain=ConstraintDomain.PACKAGE,
                        subject=requirement.name,
                        predicate=ConstraintPredicate.VERSION,
                        required=requirement.specifier,
                        observed=None,
                        disposition=FindingDisposition.UNKNOWN,
                        provenance=provenance,
                    )
                )
                continue
            findings.append(
                StructuredVerifierFinding(
                    finding_id=f"{requirement.evidence_id}-version",
                    domain=ConstraintDomain.PACKAGE,
                    subject=requirement.name,
                    predicate=ConstraintPredicate.VERSION,
                    required=requirement.specifier,
                    observed=str(version),
                    disposition=(
                        FindingDisposition.SATISFIED
                        if version in SpecifierSet(requirement.specifier)
                        else FindingDisposition.ACTIVE
                    ),
                    provenance=provenance,
                )
            )
        return findings

    @staticmethod
    def _resolution_status(value: object) -> ResolutionStatus:
        if not isinstance(value, dict):
            return ResolutionStatus.UNKNOWN
        try:
            return ResolutionStatus(value.get("status"))
        except (TypeError, ValueError):
            return ResolutionStatus.UNKNOWN

    @staticmethod
    def _probe_payload(stdout: str) -> dict[str, object] | None:
        for line in reversed(stdout.splitlines()):
            if not line.startswith(_PROBE_MARKER):
                continue
            try:
                value = json.loads(line[len(_PROBE_MARKER) :])
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None
        return None

    @staticmethod
    def _inventory_details(inventory: ImportInventory) -> dict[str, object]:
        return {
            "source_files": inventory.source_files,
            "source_bytes": inventory.source_bytes,
            "module_count": len(inventory.modules),
            "occurrence_count": len(inventory.occurrences),
            "excluded_occurrences": inventory.excluded_occurrences,
        }
