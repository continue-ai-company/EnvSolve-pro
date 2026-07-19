from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from envsolve.verification.imports import SourceRole, source_role


SCANNED_SOURCE_ROLES = {
    SourceRole.RUNTIME,
    SourceRole.TEST,
    SourceRole.BUILD,
}
PRUNED_DIRECTORIES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    "__pycache__",
    "build",
    "dist",
    "site-packages",
}


@dataclass(frozen=True)
class SourceImport:
    module: str
    path: str
    line: int
    source: str
    fallback_modules: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportInventory:
    occurrences: tuple[SourceImport, ...]
    modules: tuple[str, ...]
    source_files: int
    source_bytes: int
    excluded_occurrences: int


def collect_source_imports(
    root: Path,
    *,
    max_files: int = 5_000,
    max_source_bytes: int = 32_000_000,
) -> ImportInventory:
    """Collect bounded project import obligations without executing source."""
    if max_files <= 0 or max_source_bytes <= 0:
        raise ValueError("Import inventory bounds must be positive")
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ValueError("Import inventory root must be a directory")

    sources: list[tuple[Path, str]] = []
    source_bytes = 0
    for path in _python_files(resolved):
        if len(sources) >= max_files:
            raise ValueError(f"Import inventory exceeds {max_files} source files")
        payload = path.read_bytes()
        source_bytes += len(payload)
        if source_bytes > max_source_bytes:
            raise ValueError(
                f"Import inventory exceeds {max_source_bytes} source bytes"
            )
        sources.append((path, payload.decode("utf-8", errors="replace")))

    occurrences: list[SourceImport] = []
    excluded = 0
    for path, source in sources:
        relative = path.relative_to(resolved).as_posix()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        role = source_role(relative)
        for node in ast.walk(tree):
            modules = _node_modules(node)
            for module in modules:
                root_module = module.split(".", 1)[0]
                if root_module == "__future__" or _is_project_module(
                    resolved, path, module
                ):
                    continue
                if role not in SCANNED_SOURCE_ROLES:
                    excluded += 1
                    continue
                occurrences.append(
                    SourceImport(
                        module,
                        relative,
                        node.lineno - 1,
                        source,
                        _fallback_modules(node, parents),
                    )
                )

    unique = tuple(
        sorted(
            set(occurrences),
            key=lambda item: (item.module, item.path, item.line),
        )
    )
    return ImportInventory(
        occurrences=unique,
        modules=tuple(sorted({item.module for item in unique})),
        source_files=len(sources),
        source_bytes=source_bytes,
        excluded_occurrences=excluded,
    )


def _python_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        children = sorted(directory.iterdir(), key=lambda item: item.name)
        for child in children:
            if child.is_symlink():
                continue
            if child.is_dir():
                if child.name in PRUNED_DIRECTORIES or (child / "pyvenv.cfg").is_file():
                    continue
                pending.append(child)
            elif child.suffix == ".py" and child.is_file():
                files.append(child)
    return tuple(sorted(files))


def _node_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return (node.module,)
    return ()


def _is_project_module(root: Path, source_path: Path, module: str) -> bool:
    parts = module.split(".")
    bases = []
    base = source_path.parent
    while True:
        bases.append(base)
        if base == root:
            break
        if root not in base.parents:
            raise ValueError("Import source path escapes the project root")
        base = base.parent
    for base in bases:
        candidate = base.joinpath(*parts)
        if candidate.with_suffix(".py").is_file() or (
            candidate / "__init__.py"
        ).is_file():
            return True
    return False


def _fallback_modules(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> tuple[str, ...]:
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.ExceptHandler):
            caught = _exception_names(parent.type)
            owner = parents.get(parent)
            if not isinstance(owner, ast.Try) or not {
                "ImportError",
                "ModuleNotFoundError",
            }.intersection(caught):
                return ()
            return tuple(
                sorted(
                    {
                        module
                        for statement in owner.body
                        for descendant in ast.walk(statement)
                        for module in _node_modules(descendant)
                    }
                )
            )
        current = parent
    return ()


def _exception_names(node: ast.AST | None) -> tuple[str, ...]:
    if node is None:
        return ()
    if isinstance(node, ast.Tuple):
        return tuple(name for item in node.elts for name in _exception_names(item))
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    return ()
