from __future__ import annotations

import re
from typing import Any


_NETWORK_FAILURES = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("read-timeout", r"ReadTimeout(?:Error)?|The read operation timed out"),
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
    return next(
        (name for name, pattern in _NETWORK_FAILURES if pattern.search(logs)),
        None,
    )
