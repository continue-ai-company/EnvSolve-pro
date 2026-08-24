from __future__ import annotations

import re
from typing import Any


_NETWORK_FAILURES = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("read-timeout", r"ReadTimeout(?:Error)?|The read operation timed out"),
        ("connection-timeout", r"\bConnection timed out\b"),
        ("connection-error", r"ConnectionError"),
        (
            "conda-http-connection-failed",
            r"CondaHTTPError:\s*HTTP\s+000\s+CONNECTION FAILED",
        ),
        ("dns-temporary-failure", r"Temporary failure in name resolution"),
        ("dns-resolution-failure", r"Could not resolve host"),
        (
            "package-index-dns-exhaustion",
            r"(?:Temporary failure in name resolution|Name or service not known|"
            r"Could not resolve host)[\s\S]{0,12000}"
            r"No matching distribution found",
        ),
        ("tls-timeout", r"TLSV?\s+handshake.*timed out"),
        (
            "git-rpc-tls-truncation",
            r"error:\s*RPC failed;\s*curl 56 GnuTLS recv error[\s\S]{0,1000}"
            r"(?:fatal:\s*early EOF|fatal:\s*fetch-pack: invalid index-pack output)",
        ),
        ("network-unreachable", r"network is unreachable"),
        (
            "upstream-http-5xx",
            r"\b(?:500 Internal Server Error|502 Bad Gateway|503 Service Unavailable|504 Gateway Time-?out)\b",
        ),
        ("apt-connection-failed", r"\bConnection failed \[IP:[^\]]+\]"),
        (
            "package-download-hash-mismatch",
            r"THESE PACKAGES DO NOT MATCH THE HASHES[\s\S]{0,2000}"
            r"\bunknown package:\s*Expected sha256 [0-9a-f]{64}"
            r"\s+Got\s+[0-9a-f]{64}",
        ),
        (
            "package-index-json-truncation",
            r"pip/_internal/index/(?:collector|package_finder)\.py[\s\S]{0,5000}"
            r"json\.decoder\.JSONDecodeError:\s*Unterminated string",
        ),
    )
)
_NETWORK_SIGNATURES = frozenset(name for name, _pattern in _NETWORK_FAILURES)

_TERMINAL_BOOTSTRAP_FAILURES = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"metadata-generation-failed",
        r"No matching distribution found",
        r"Could not build wheels? for",
        r"Failed building wheel for",
        r"C shared or static library ['\"][^'\"]+['\"] not found",
    )
)


def envbench_bootstrap_infrastructure_signature(raw: dict[str, Any]) -> str | None:
    """Classify a terminal evaluation that was censored before Pyright ran."""
    exit_code = raw.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code == 0:
        return None

    pyright = raw.get("pyright")
    summary = pyright.get("summary") if isinstance(pyright, dict) else None
    if isinstance(summary, dict) and isinstance(summary.get("errorCount"), int):
        return None

    logs = raw.get("container_logs")
    if not isinstance(logs, str):
        return None
    network_matches = [
        (match.end(), name)
        for name, pattern in _NETWORK_FAILURES
        for match in pattern.finditer(logs)
    ]
    if not network_matches:
        return None
    last_network_position, signature = max(network_matches)
    last_bootstrap_failure = max(
        (
            match.start()
            for pattern in _TERMINAL_BOOTSTRAP_FAILURES
            for match in pattern.finditer(logs)
        ),
        default=-1,
    )
    if last_bootstrap_failure > last_network_position:
        return None
    return signature


def envbench_evaluation_infrastructure_signature(
    evidence: dict[str, Any],
) -> str | None:
    """Classify retryable infrastructure failures around an official attempt."""
    bootstrap_signature = envbench_bootstrap_infrastructure_signature(evidence)
    if bootstrap_signature is not None:
        return bootstrap_signature

    metadata = evidence.get("metadata")
    adapter_error = metadata.get("adapter_error") if isinstance(metadata, dict) else None
    termination = metadata.get("termination") if isinstance(metadata, dict) else None
    if (
        evidence.get("evaluation_completed") is False
        and isinstance(termination, dict)
        and termination.get("kind") == "infrastructure_unknown"
        and termination.get("scope") == "evaluator_bootstrap"
        and termination.get("signature") in _NETWORK_SIGNATURES
        and adapter_error
        == (
            "EnvBench bootstrap was censored by infrastructure failure: "
            f"{termination.get('signature')}"
        )
    ):
        return str(termination["signature"])
    if (
        isinstance(adapter_error, str)
        and re.fullmatch(
            r"FileNotFoundError: \[Errno 2\] No such file or directory: ['\"]uv['\"]",
            adapter_error,
        )
    ):
        return "evaluator-host-missing-uv"
    return None
