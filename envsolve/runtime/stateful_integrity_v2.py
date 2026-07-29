from __future__ import annotations

import shlex
from pathlib import PurePosixPath

from envsolve.runtime.integrity import IMPORT_ALIAS_AUDIT_MARKER


_SOURCE_PROVENANCE_AUDIT = f"""\
import ast
import json
import os
from pathlib import Path
import site
import sys
import sysconfig

project_root = Path(sys.argv[1]).resolve()
provided = {{}}
for base in (project_root, project_root / "src"):
    if not base.is_dir():
        continue
    for child in base.iterdir():
        if child.is_symlink():
            continue
        if child.is_file() and child.suffix in {{".py", ".pyi"}}:
            provided.setdefault(child.stem, child.resolve())
        elif child.is_dir() and (
            (child / "__init__.py").is_file()
            or any(item.suffix in {{".py", ".pyi"}} for item in child.iterdir())
        ):
            provided.setdefault(child.name, child.resolve())

referenced_project_namespaces = set()
for name, source in provided.items():
    files = [source] if source.is_file() else list(source.rglob("*.py"))
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                referenced_project_namespaces.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    referenced_project_namespaces.add(name)
                elif node.module:
                    referenced_project_namespaces.add(
                        node.module.split(".", 1)[0]
                    )

explicit_search_roots = {{
    value
    for value in os.environ.get("PYTHONPATH", "").split(os.pathsep)
    if value
}}
search_roots = {{value for value in sys.path if value}}
search_roots.update(explicit_search_roots)
distribution_search_roots = set(explicit_search_roots)
try:
    site_roots = site.getsitepackages()
    search_roots.update(site_roots)
    distribution_search_roots.update(site_roots)
except Exception:
    pass
try:
    user_site = site.getusersitepackages()
    search_roots.add(user_site)
    distribution_search_roots.add(user_site)
except Exception:
    pass
for key in ("purelib", "platlib"):
    value = sysconfig.get_paths().get(key)
    if value:
        search_roots.add(value)
        distribution_search_roots.add(value)

violations = []
for value in sorted(search_roots):
    root = Path(value)
    if not root.is_dir():
        continue
    try:
        resolved_root = root.resolve()
    except RuntimeError:
        continue
    if resolved_root in {{project_root, (project_root / "src").resolve()}}:
        continue
    for path in root.iterdir():
        if not path.is_symlink():
            continue
        alias = path.name.split(".", 1)[0]
        if not alias.isidentifier() or alias in provided:
            continue
        try:
            target = path.resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            continue
        if target == project_root or project_root in target.parents:
            violations.append(
                {{
                    "alias": alias,
                    "link": str(path),
                    "target": str(target),
                    "reason": "undeclared import alias resolves into project source",
                }}
            )

project_source_roots = {{project_root, (project_root / "src").resolve()}}
for value in sorted(distribution_search_roots):
    root = Path(value)
    if not root.is_dir():
        continue
    try:
        resolved_root = root.resolve()
    except RuntimeError:
        continue
    if resolved_root in project_source_roots:
        continue
    for name, project_path in sorted(provided.items()):
        if name not in referenced_project_namespaces:
            continue
        candidates = (
            resolved_root / name,
            resolved_root / (name + ".py"),
            resolved_root / (name + ".pyi"),
        )
        overlay = next((item for item in candidates if item.exists()), None)
        if overlay is None:
            continue
        try:
            resolved_overlay = overlay.resolve()
        except RuntimeError:
            continue
        if resolved_overlay == project_path or project_root in resolved_overlay.parents:
            continue
        if overlay.is_file():
            external_sources = {{overlay.name: overlay}}
        else:
            external_sources = {{
                str(item.relative_to(overlay)): item
                for item in overlay.rglob("*")
                if item.is_file() and item.suffix == ".py"
            }}
        divergent_sources = []
        for relative, external_source in sorted(external_sources.items()):
            counterpart = (
                project_path if project_path.is_file() else project_path / relative
            )
            try:
                identical = (
                    counterpart.is_file()
                    and counterpart.read_bytes() == external_source.read_bytes()
                )
            except OSError:
                identical = False
            if not identical:
                divergent_sources.append(relative)
        if not divergent_sources:
            continue
        violations.append(
            {{
                "alias": name,
                "path": str(resolved_overlay),
                "search_root": str(resolved_root),
                "divergent_sources": divergent_sources[:50],
                "reason": (
                    "external import search root contributes divergent project source"
                ),
            }}
        )

print(
    {IMPORT_ALIAS_AUDIT_MARKER!r}
    + json.dumps(
        {{
            "valid": not violations,
            "violations": violations,
            "provided_modules": sorted(provided),
            "policy": "python-import-source-provenance-v2",
        }},
        sort_keys=True,
    )
)
"""


def python_source_provenance_audit_command(project_root: str) -> str:
    code = shlex.quote(_SOURCE_PROVENANCE_AUDIT)
    root = shlex.quote(str(PurePosixPath(project_root)))
    return f"command python -I -c {code} {root}"
