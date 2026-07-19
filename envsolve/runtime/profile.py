from __future__ import annotations

from pathlib import Path
from typing import Any


PROFILE_NAMES = (
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "tox.ini",
    "pytest.ini",
    "environment.yml",
    "environment.yaml",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "README.md",
    "README.rst",
    "CONTRIBUTING.md",
)


def profile_python_repository(
    root: Path,
    *,
    max_file_chars: int = 8_000,
    max_total_chars: int = 24_000,
) -> dict[str, Any]:
    """Collect bounded project-owned deployment evidence without executing code."""
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ValueError(f"Repository profile root is not a directory: {resolved}")
    files: list[dict[str, Any]] = []
    total = 0
    for name in PROFILE_NAMES:
        path = resolved / name
        if not path.is_file() or path.is_symlink() or total >= max_total_chars:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        remaining = max_total_chars - total
        bounded = content[: min(max_file_chars, remaining)]
        files.append(
            {
                "path": name,
                "content": bounded,
                "truncated": len(bounded) < len(content),
            }
        )
        total += len(bounded)
    top_level = sorted(
        item.name
        for item in resolved.iterdir()
        if item.name != ".git" and not item.is_symlink()
    )[:200]
    has_tests = any(
        (resolved / name).is_dir() for name in ("test", "tests")
    ) or any(resolved.glob("test_*.py"))
    return {
        "schema": "envsolve-python-repository-profile-v1",
        "top_level": top_level,
        "files": files,
        "has_tests": has_tests,
        "total_content_chars": total,
    }
