from __future__ import annotations

import re
import shlex
from typing import Any

from envsolve.context.models import SAFE_NAME, normalize_packages, validate_name


APT_FILE_LINE = re.compile(r"^([^\s]+):\s+(.+)$")


def apt_file_capability_command(capability: str) -> str:
    name = validate_name(capability, "capability")
    if not SAFE_NAME.fullmatch(name):
        raise ValueError(f"Invalid capability: {capability!r}")
    expression = f"/{re.escape(name)}$"
    return f"apt-file search --regexp {shlex.quote(expression)}"


def parse_apt_file_capability(
    capability: str,
    stdout: str,
) -> dict[str, Any]:
    name = validate_name(capability, "capability")
    packages: set[str] = set()
    for line in stdout.splitlines():
        match = APT_FILE_LINE.fullmatch(line.strip())
        if match is None:
            continue
        package, path = match.groups()
        if path.rsplit("/", 1)[-1] != name:
            continue
        packages.add(package)
    normalized = normalize_packages(sorted(packages))
    return {
        "capability": name,
        "manager": "apt-get",
        "packages": list(normalized),
    }
