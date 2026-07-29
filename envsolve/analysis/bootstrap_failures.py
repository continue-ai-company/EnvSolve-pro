from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from envsolve.state import EnvironmentState


_RUNTIME_PATTERNS = (
    re.compile(
        r"\b(?:python|python_version)\s*[=:]\s*['\"]?(?P<version>3\.\d+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bpython(?P<version>3\.\d+)\b",
        re.IGNORECASE,
    ),
)
_LOG_RUNTIME = re.compile(
    r"(?:^|[/\\])python(?P<version>3\.\d+)(?:[/\\]|$)",
    re.IGNORECASE,
)
_FAILURE_PATTERNS = (
    (
        "infrastructure-network-failure",
        re.compile(
            r"(?:\b(?:502 Bad Gateway|503 Service Unavailable|"
            r"504 Gateway Time-?out)\b|"
            r"\bConnection failed\b|"
            r"\b(?:ReadTimeout|ConnectTimeout|ConnectionError|"
            r"ProtocolError|RemoteDisconnected|ProxyError)\b|"
            r"Temporary failure (?:in name resolution|resolving)|"
            r"Could not resolve host|"
            r"connection reset by peer|"
            r"network is unreachable)",
            re.IGNORECASE,
        ),
    ),
    (
        "removed-runtime-api",
        re.compile(
            r"(?:module\s+)?['\"]?(?P<subject>[A-Za-z_][\w.]*)['\"]?"
            r"\s+has no attribute "
            r"['\"](?P<attribute>[A-Za-z_][\w]*)['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "runtime-c-api-incompatibility",
        re.compile(
            r"error:\s+too (?:few|many) arguments to function "
            r"['\u2018\u2019\"](?P<subject>_[A-Za-z0-9_]+)['\u2018\u2019\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "provider-target-unavailable",
        re.compile(
            r"(?:Could not find a version that satisfies the requirement|"
            r"No matching distribution found for)\s+(?P<subject>[^\s;]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "missing-build-dependency",
        re.compile(
            r"(?:ModuleNotFoundError|ImportError):\s+No module named "
            r"['\"](?P<subject>[^'\"]+)['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "missing-system-build-input",
        re.compile(
            r"(?:fatal error:\s*(?P<header>[^:\r\n]+):\s*No such file|"
            r"Cannot find pkg-config name for (?P<pkgconfig>[^\s]+)|"
            r"command ['\"](?P<compiler>gcc|g\+\+|cc|clang)['\"] failed)",
            re.IGNORECASE,
        ),
    ),
    (
        "source-build-failure",
        re.compile(
            r"(?:Failed to build ['\"](?P<quoted>[A-Za-z0-9_.+-]+)['\"]|"
            r"Failed building wheel for (?P<wheel>[A-Za-z0-9_.+-]+)|"
            r"Building wheel for (?P<building>[A-Za-z0-9_.+-]+).*error)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "package-metadata-failure",
        re.compile(
            r"(?:metadata-generation-failed|"
            r"Preparing metadata \(pyproject\.toml\).*error)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)
_FAILED_GOAL_SUMMARY = "Candidate did not return control to the executable goal"


@dataclass(frozen=True)
class BootstrapFailure:
    failure_class: str
    subject: str | None
    excerpt: str

    @property
    def signature(self) -> str:
        encoded = json.dumps(
            {
                "failure_class": self.failure_class,
                "subject": self.subject,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_class": self.failure_class,
            "subject": self.subject,
            "signature": self.signature,
            "excerpt": self.excerpt,
        }


def _match_subject(match: re.Match[str]) -> str | None:
    groups = match.groupdict()
    if groups.get("subject") and groups.get("attribute"):
        return f"{groups['subject']}.{groups['attribute']}"
    for key in ("subject", "header", "pkgconfig", "compiler", "quoted", "wheel", "building"):
        value = groups.get(key)
        if value:
            return value.strip(" '\".,")
    return None


def _excerpt(text: str, match: re.Match[str], limit: int = 320) -> str:
    start = max(0, match.start() - limit // 3)
    end = min(len(text), match.end() + (limit * 2 // 3))
    value = " ".join(text[start:end].split())
    if start:
        value = "..." + value
    if end < len(text):
        value += "..."
    return value[:limit]


def classify_bootstrap_failure(stdout: str, stderr: str) -> BootstrapFailure:
    text = f"{stdout}\n{stderr}"
    for failure_class, pattern in _FAILURE_PATTERNS:
        matches = tuple(pattern.finditer(text))
        if matches:
            match = matches[-1]
            return BootstrapFailure(
                failure_class,
                _match_subject(match),
                _excerpt(text, match),
            )
    tail = " ".join(text[-600:].split())
    return BootstrapFailure(
        "unclassified-bootstrap-failure",
        None,
        tail[:320],
    )


def runtime_branches(script: str, stdout: str, stderr: str) -> tuple[str, ...]:
    explicit: set[str] = set()
    for pattern in _RUNTIME_PATTERNS:
        explicit.update(
            match.group("version")
            for match in pattern.finditer(script)
        )
    if explicit:
        return tuple(sorted(explicit))
    observed = {
        match.group("version")
        for match in _LOG_RUNTIME.finditer(f"{stdout}\n{stderr}")
    }
    return tuple(sorted(observed)) or ("unknown",)


def bootstrap_strategy(script: str) -> dict[str, str]:
    lowered = script.lower()
    if "--no-build-isolation" in lowered:
        build_isolation = "disabled"
    elif re.search(r"\bpip(?:3)?\s+install\b", lowered):
        build_isolation = "default"
    else:
        build_isolation = "not-observed"

    if "--only-binary" in lowered:
        artifact_policy = "binary-required"
    elif "--no-binary" in lowered:
        artifact_policy = "source-required"
    else:
        artifact_policy = "provider-default"

    project_install = bool(
        re.search(
            r"\b(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?pip(?:3)?\s+install\b"
            r"[^\n]*(?:\s-e\s+|\s)(?:\.[/ ]?|['\"]?\.\s*$)",
            script,
            re.IGNORECASE | re.MULTILINE,
        )
    )
    if project_install and "--no-deps" in lowered:
        dependency_mode = "project-without-dependencies"
    elif project_install:
        dependency_mode = "declared-project-dependencies"
    elif re.search(r"\bpip(?:3)?\s+install\b", lowered):
        dependency_mode = "manual-distribution-set"
    else:
        dependency_mode = "not-observed"

    if re.search(r"\b(?:conda|mamba|micromamba)\b", lowered):
        environment_provider = "conda-family"
    elif re.search(r"\b(?:python|python3)(?:\.\d+)?\s+-m\s+venv\b", lowered):
        environment_provider = "venv"
    else:
        environment_provider = "base-environment"

    return {
        "artifact_policy": artifact_policy,
        "build_isolation": build_isolation,
        "dependency_mode": dependency_mode,
        "environment_provider": environment_provider,
    }


def strategy_signature(strategy: dict[str, str]) -> str:
    encoded = json.dumps(
        strategy,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _verification_by_candidate(
    state: EnvironmentState,
) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for verification in state.verifications:
        details = verification.get("details")
        candidate_id = (
            details.get("candidate_id")
            if isinstance(details, dict)
            else None
        )
        if isinstance(candidate_id, str):
            values[candidate_id] = verification
    return values


def observe_bootstrap_attempts(
    state: EnvironmentState,
) -> tuple[dict[str, Any], ...]:
    verifications = _verification_by_candidate(state)
    actions = sorted(
        state.actions.values(),
        key=lambda item: int(
            item.get("state_metadata", {}).get("event_sequence", 0)
        ),
    )
    attempts: list[dict[str, Any]] = []
    for action in actions:
        candidate_id = action.get("action_id")
        if not isinstance(candidate_id, str):
            continue
        verification = verifications.get(candidate_id)
        details = (
            verification.get("details")
            if isinstance(verification, dict)
            else None
        )
        if not isinstance(details, dict):
            continue
        summary = details.get("summary")
        bootstrap_failed = summary == _FAILED_GOAL_SUMMARY
        bootstrap_succeeded = (
            isinstance(summary, str)
            and summary != _FAILED_GOAL_SUMMARY
            and details.get("bootstrap_exit_code") == 0
        )
        if not bootstrap_failed and not bootstrap_succeeded:
            continue

        observation = action.get("observation")
        if not isinstance(observation, dict):
            observation = {}
        stdout = observation.get("stdout")
        stderr = observation.get("stderr")
        stdout = stdout if isinstance(stdout, str) else ""
        stderr = stderr if isinstance(stderr, str) else ""
        script = action.get("command")
        script = script if isinstance(script, str) else ""
        strategy = bootstrap_strategy(script)
        evidence_sha256 = hashlib.sha256(
            f"{stdout}\n{stderr}".encode("utf-8")
        ).hexdigest()
        attempt: dict[str, Any] = {
            "candidate_id": candidate_id,
            "outcome": "failed" if bootstrap_failed else "succeeded",
            "runtime_branches": list(runtime_branches(script, stdout, stderr)),
            "strategy": strategy,
            "strategy_signature": strategy_signature(strategy),
            "duration_seconds": observation.get("duration_seconds"),
            "raw_execution_evidence_sha256": evidence_sha256,
        }
        if bootstrap_failed:
            failure = classify_bootstrap_failure(
                stdout,
                stderr,
            )
            attempt["failure"] = failure.to_dict()
            if failure.failure_class.startswith("infrastructure-"):
                attempt["outcome"] = "infrastructure-censored"
        attempts.append(attempt)
    return tuple(attempts)
