from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from packaging.version import Version


_PYO3_RUNTIME_FRONTIER = re.compile(
    r"configured Python interpreter version \((?P<observed>[0-9]+(?:\.[0-9]+)+)\) "
    r"is newer than PyO3's maximum supported version "
    r"\((?P<maximum>[0-9]+(?:\.[0-9]+)+)\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeCompatibilityFinding:
    provider: str
    runtime: str
    observed_version: str
    maximum_supported_version: str
    signature: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def parse_runtime_compatibility(text: str) -> tuple[RuntimeCompatibilityFinding, ...]:
    """Extract only explicit provider/runtime incompatibility statements."""
    findings = {
        (
            str(Version(match.group("observed"))),
            str(Version(match.group("maximum"))),
        )
        for match in _PYO3_RUNTIME_FRONTIER.finditer(text)
    }
    return tuple(
        RuntimeCompatibilityFinding(
            provider="pyo3",
            runtime="python",
            observed_version=observed,
            maximum_supported_version=maximum,
            signature="pyo3-maximum-python",
        )
        for observed, maximum in sorted(findings)
    )
