from __future__ import annotations

import shlex
from pathlib import PurePosixPath

from envsolve.runtime.integrity import IMPORT_ALIAS_AUDIT_MARKER
from envsolve.runtime.stateful_integrity_v2 import (
    python_source_provenance_audit_command,
)


MODULE_IDENTITY_VIOLATION_REASON = (
    "project source acquired an undeclared module identity"
)

_MODULE_IDENTITY_AUDIT = f"""\
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

marker = {IMPORT_ALIAS_AUDIT_MARKER!r}
project_root = Path(sys.argv[1]).resolve()
base_output = sys.argv[2]
base_report = {{}}
for line in reversed(base_output.splitlines()):
    if not line.startswith(marker):
        continue
    try:
        value = json.loads(line[len(marker):])
    except json.JSONDecodeError:
        value = {{}}
    if isinstance(value, dict):
        base_report = value
    break

source_roots = [
    path.resolve()
    for path in (project_root, project_root / "src")
    if path.is_dir()
]
module_sources = {{}}
regular_project_namespaces = set()

def module_identity(source_root, path):
    relative = path.relative_to(source_root)
    parts = list(relative.parts)
    filename = parts.pop()
    stem = Path(filename).stem
    if stem != "__init__":
        parts.append(stem)
    if not parts or not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts)

for source_root in source_roots:
    for child in source_root.iterdir():
        if (
            child.is_dir()
            and child.name.isidentifier()
            and (
                (child / "__init__.py").is_file()
                or (child / "__init__.pyi").is_file()
            )
        ):
            regular_project_namespaces.add(child.name)
    for path in source_root.rglob("*"):
        if not path.is_file() or path.suffix not in {{".py", ".pyi"}}:
            continue
        identity = module_identity(source_root, path)
        if identity is None:
            continue
        module_sources.setdefault(identity, []).append(path.resolve())

referenced_modules = set()
for paths in module_sources.values():
    for path in paths:
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                referenced_modules.update(alias.name for alias in node.names)
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
            ):
                referenced_modules.add(node.module)

source_hash_identities = {{}}
for identity, paths in module_sources.items():
    for path in paths:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        source_hash_identities.setdefault(digest, set()).add(identity)

def project_identity(path):
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return None
    candidate = (
        resolved / "__init__.py"
        if resolved.is_dir()
        else resolved
    )
    if not candidate.is_file():
        alternate = resolved / "__init__.pyi" if resolved.is_dir() else resolved
        candidate = alternate if alternate.is_file() else candidate
    for source_root in source_roots:
        try:
            return module_identity(source_root, candidate)
        except ValueError:
            continue
    if not candidate.is_file() or candidate.suffix not in {{".py", ".pyi"}}:
        return None
    try:
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    except OSError:
        return None
    identities = source_hash_identities.get(digest, set())
    return next(iter(identities)) if len(identities) == 1 else None

identity_violations = []
for requested in sorted(referenced_modules):
    root_name = requested.split(".", 1)[0]
    if (
        root_name not in regular_project_namespaces
        or requested in module_sources
    ):
        continue
    try:
        spec = importlib.util.find_spec(requested)
    except (AttributeError, ImportError, ModuleNotFoundError, ValueError):
        spec = None
    if spec is None:
        continue
    locations = []
    if isinstance(spec.origin, str) and spec.origin not in {{"built-in", "frozen"}}:
        locations.append(Path(spec.origin))
    if spec.submodule_search_locations is not None:
        locations.extend(Path(item) for item in spec.submodule_search_locations)
    observed_identities = sorted(
        {{
            identity
            for location in locations
            for identity in (project_identity(location),)
            if identity is not None
        }}
    )
    if not observed_identities or requested in observed_identities:
        continue
    identity_violations.append(
        {{
            "alias": root_name,
            "requested_module": requested,
            "observed_project_identities": observed_identities,
            "origins": [str(item) for item in locations],
            "reason": {MODULE_IDENTITY_VIOLATION_REASON!r},
        }}
    )

violations = list(base_report.get("violations", []))
violations.extend(identity_violations)
print(
    marker
    + json.dumps(
        {{
            **base_report,
            "valid": not violations,
            "violations": violations,
            "identity_violations": identity_violations,
            "policy": "python-module-identity-provenance-v2.2",
        }},
        sort_keys=True,
    )
)
"""


def python_module_identity_audit_command(project_root: str) -> str:
    root = shlex.quote(str(PurePosixPath(project_root)))
    base = python_source_provenance_audit_command(project_root)
    code = shlex.quote(_MODULE_IDENTITY_AUDIT)
    return "\n".join(
        (
            f'ENVSOLVE_V22_BASE_AUDIT="$({base})"',
            'printf \'%s\\n\' "$ENVSOLVE_V22_BASE_AUDIT"',
            (
                f'command python -I -c {code} {root} '
                '"$ENVSOLVE_V22_BASE_AUDIT"'
            ),
        )
    )
