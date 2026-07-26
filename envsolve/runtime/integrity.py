from __future__ import annotations

import json
from pathlib import PurePosixPath
import shlex


IMPORT_ALIAS_AUDIT_MARKER = "ENVSOLVE_IMPORT_ALIAS_AUDIT_V1="

_IMPORT_ALIAS_AUDIT = """\
import json
from pathlib import Path
import site
import sys
import sysconfig

project_root = Path(sys.argv[1]).resolve()
provided = set()
for base in (project_root, project_root / "src"):
    if not base.is_dir():
        continue
    for child in base.iterdir():
        if child.is_symlink():
            continue
        if child.is_file() and child.suffix in {".py", ".pyi"}:
            provided.add(child.stem)
        elif child.is_dir() and (
            (child / "__init__.py").is_file()
            or any(item.suffix in {".py", ".pyi"} for item in child.iterdir())
        ):
            provided.add(child.name)

search_roots = {value for value in sys.path if value}
try:
    search_roots.update(site.getsitepackages())
except Exception:
    pass
try:
    search_roots.add(site.getusersitepackages())
except Exception:
    pass
for key in ("purelib", "platlib"):
    value = sysconfig.get_paths().get(key)
    if value:
        search_roots.add(value)

violations = []
for value in sorted(search_roots):
    root = Path(value)
    if not root.is_dir():
        continue
    try:
        resolved_root = root.resolve()
    except RuntimeError:
        continue
    if resolved_root in {project_root, (project_root / "src").resolve()}:
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
                {
                    "alias": alias,
                    "link": str(path),
                    "target": str(target),
                    "reason": "undeclared import alias resolves into project source",
                }
            )

print(
    "ENVSOLVE_IMPORT_ALIAS_AUDIT_V1="
    + json.dumps(
        {
            "valid": not violations,
            "violations": violations,
            "provided_modules": sorted(provided),
        },
        sort_keys=True,
    )
)
"""


def python_import_alias_audit_command(project_root: str) -> str:
    return "command python -c {code} {project_root}".format(
        code=shlex.quote(_IMPORT_ALIAS_AUDIT),
        project_root=shlex.quote(str(PurePosixPath(project_root))),
    )


def marked_json_payload(
    stdout: str,
    marker: str,
) -> dict[str, object] | None:
    for line in reversed(stdout.splitlines()):
        if not line.startswith(marker):
            continue
        try:
            value = json.loads(line[len(marker) :])
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None
    return None
