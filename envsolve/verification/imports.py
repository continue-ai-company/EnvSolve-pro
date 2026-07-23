from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import fnmatch
import hashlib
from pathlib import PurePosixPath
from typing import Iterable, Mapping, Sequence


class SourceRole(str, Enum):
    RUNTIME = "runtime"
    TEST = "test"
    DOCUMENTATION = "documentation"
    FIXTURE = "fixture"
    BUILD = "build"
    VENDORED = "vendored"


class ImportDisposition(str, Enum):
    ACTIVE_OBLIGATION = "active_obligation"
    INACTIVE_PLATFORM = "inactive_platform"
    STATIC_ONLY = "static_only"
    PROJECT_EXCLUDED_FIXTURE = "project_excluded_fixture"
    GUARDED_OPTIONAL = "guarded_optional"
    DOCUMENTATION_SCOPE = "documentation_scope"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class MissingImportFinding:
    module: str
    file: str
    line: int
    diagnostic: str


@dataclass(frozen=True)
class EnvironmentFacts:
    sys_platform: str
    python_major: int
    platform_name: str
    python_version: tuple[int, ...] | None = None


@dataclass(frozen=True)
class ExclusionRule:
    tool: str
    pattern: str
    config_sha256: str
    syntax: str = "glob"

    def matches(self, path: str) -> bool:
        if len(self.config_sha256) != 64 or self.syntax not in {"glob", "prefix"}:
            return False
        normalized = path.lstrip("./")
        pattern = self.pattern.lstrip("./").rstrip("/")
        if self.syntax == "prefix":
            return normalized == pattern or normalized.startswith(pattern + "/")
        return fnmatch.fnmatch(normalized, pattern)


@dataclass(frozen=True)
class ImportEvidence:
    kind: str
    detail: str
    source_sha256: str
    line: int


@dataclass(frozen=True)
class ImportAssessment:
    finding: MissingImportFinding
    role: SourceRole
    disposition: ImportDisposition
    evidence: tuple[ImportEvidence, ...]

    @property
    def active_repair_obligation(self) -> bool:
        return self.disposition in {
            ImportDisposition.ACTIVE_OBLIGATION,
            ImportDisposition.DOCUMENTATION_SCOPE,
            ImportDisposition.STATIC_ONLY,
            ImportDisposition.UNRESOLVED,
        }


def source_role(path: str) -> SourceRole:
    candidate = PurePosixPath(path)
    parts = tuple(part.lower() for part in candidate.parts)
    if "fixtures" in parts or "fixture" in parts:
        return SourceRole.FIXTURE
    if any(part in {"docs", "doc", "documentation"} for part in parts):
        return SourceRole.DOCUMENTATION
    if "tests" in parts or "test" in parts or candidate.name.lower().startswith("test_"):
        return SourceRole.TEST
    if "vendor" in parts or "vendored" in parts:
        return SourceRole.VENDORED
    if candidate.name in {"setup.py", "conftest.py"} or "build" in parts:
        return SourceRole.BUILD
    return SourceRole.RUNTIME


class _Unknown:
    pass


UNKNOWN = _Unknown()


class ImportContextAnalyzer:
    def assess(
        self,
        finding: MissingImportFinding,
        source: str,
        facts: EnvironmentFacts,
        exclusions: Iterable[ExclusionRule] = (),
    ) -> ImportAssessment:
        role = source_role(finding.file)
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        evidence = [ImportEvidence("source-role", role.value, source_hash, finding.line)]
        if role is SourceRole.FIXTURE:
            matches = tuple(rule for rule in exclusions if rule.matches(finding.file))
            if matches:
                evidence.extend(
                    ImportEvidence(
                        "project-exclusion",
                        f"{rule.tool}:{rule.syntax}:{rule.pattern}:{rule.config_sha256}",
                        source_hash,
                        finding.line,
                    )
                    for rule in matches
                )
                return ImportAssessment(
                    finding,
                    role,
                    ImportDisposition.PROJECT_EXCLUDED_FIXTURE,
                    tuple(evidence),
                )
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ImportAssessment(finding, role, ImportDisposition.UNRESOLVED, tuple(evidence))
        target = self._target_import(tree, finding.line + 1, finding.module)
        if target is None:
            return ImportAssessment(finding, role, ImportDisposition.UNRESOLVED, tuple(evidence))
        ancestors = self._ancestors(tree, target)
        constants = self._module_constants(tree, facts)
        type_checking_names = self._type_checking_names(tree)
        default_false_names = {
            name
            for ancestor in ancestors
            if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef))
            for name in self._literal_false_defaults(ancestor)
        }
        for ancestor in ancestors:
            if isinstance(ancestor, ast.Try) and self._inside(target, ancestor.body):
                caught = {
                    name
                    for handler in ancestor.handlers
                    for name in self._exception_names(handler.type)
                }
                if "ImportError" in caught or "ModuleNotFoundError" in caught:
                    evidence.append(
                        ImportEvidence("import-fallback", ",".join(sorted(caught)), source_hash, ancestor.lineno - 1)
                    )
                    return ImportAssessment(
                        finding, role, ImportDisposition.GUARDED_OPTIONAL, tuple(evidence)
                    )
            if isinstance(ancestor, ast.If):
                if (
                    self._inside(target, ancestor.body)
                    and self._is_type_checking_test(ancestor.test, type_checking_names)
                ):
                    evidence.append(
                        ImportEvidence(
                            "static-only-branch",
                            ast.unparse(ancestor.test),
                            source_hash,
                            ancestor.lineno - 1,
                        )
                    )
                    return ImportAssessment(
                        finding, role, ImportDisposition.STATIC_ONLY, tuple(evidence)
                    )
                default_disabled = (
                    isinstance(ancestor.test, ast.Name)
                    and ancestor.test.id in default_false_names
                    and self._inside(target, ancestor.body)
                )
                if default_disabled:
                    evidence.append(
                        ImportEvidence(
                            "default-disabled-branch",
                            ast.unparse(ancestor.test),
                            source_hash,
                            ancestor.lineno - 1,
                        )
                    )
                    return ImportAssessment(
                        finding,
                        role,
                        ImportDisposition.GUARDED_OPTIONAL,
                        tuple(evidence),
                    )
                condition = self._evaluate(ancestor.test, facts, constants)
                inactive = (
                    condition is False and self._inside(target, ancestor.body)
                ) or (
                    condition is True and self._inside(target, ancestor.orelse)
                )
                if inactive:
                    evidence.append(
                        ImportEvidence(
                            "inactive-branch",
                            ast.unparse(ancestor.test),
                            source_hash,
                            ancestor.lineno - 1,
                        )
                    )
                    return ImportAssessment(
                        finding,
                        role,
                        ImportDisposition.INACTIVE_PLATFORM,
                        tuple(evidence),
                    )
            if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in ancestor.decorator_list:
                    skip = self._skip_condition(decorator)
                    if skip is not None and self._evaluate(skip, facts, constants) is True:
                        evidence.append(
                            ImportEvidence(
                                "active-skip",
                                ast.unparse(skip),
                                source_hash,
                                decorator.lineno - 1,
                            )
                        )
                        return ImportAssessment(
                            finding, role, ImportDisposition.INACTIVE_PLATFORM, tuple(evidence)
                        )
        if role is SourceRole.DOCUMENTATION:
            return ImportAssessment(
                finding, role, ImportDisposition.DOCUMENTATION_SCOPE, tuple(evidence)
            )
        if role in {SourceRole.TEST, SourceRole.RUNTIME, SourceRole.BUILD}:
            return ImportAssessment(
                finding, role, ImportDisposition.ACTIVE_OBLIGATION, tuple(evidence)
            )
        return ImportAssessment(finding, role, ImportDisposition.UNRESOLVED, tuple(evidence))

    def _target_import(self, tree: ast.AST, line: int, module: str) -> ast.AST | None:
        root = module.split(".", 1)[0]
        for node in ast.walk(tree):
            if getattr(node, "lineno", None) != line:
                continue
            if isinstance(node, ast.Import) and any(alias.name.split(".", 1)[0] == root for alias in node.names):
                return node
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".", 1)[0] == root:
                return node
        return None

    def _ancestors(self, tree: ast.AST, target: ast.AST) -> tuple[ast.AST, ...]:
        path: list[ast.AST] = []

        def visit(node: ast.AST, stack: list[ast.AST]) -> bool:
            if node is target:
                path.extend(stack)
                return True
            for child in ast.iter_child_nodes(node):
                if visit(child, stack + [node]):
                    return True
            return False

        visit(tree, [])
        return tuple(reversed(path))

    def _inside(self, target: ast.AST, nodes: Iterable[ast.AST]) -> bool:
        return any(item is target for node in nodes for item in ast.walk(node))

    def _module_constants(self, tree: ast.Module, facts: EnvironmentFacts) -> dict[str, object]:
        values: dict[str, object] = {}
        for statement in tree.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if not isinstance(target, ast.Name):
                continue
            value = self._evaluate(statement.value, facts, values)
            if value is not UNKNOWN:
                values[target.id] = value
        return values

    @staticmethod
    def _type_checking_names(tree: ast.Module) -> set[str]:
        names = {"typing.TYPE_CHECKING", "typing_extensions.TYPE_CHECKING"}
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom) or statement.module not in {
                "typing",
                "typing_extensions",
            }:
                continue
            for alias in statement.names:
                if alias.name == "TYPE_CHECKING":
                    names.add(alias.asname or alias.name)
        return names

    @staticmethod
    def _is_type_checking_test(node: ast.AST, names: set[str]) -> bool:
        return ast.unparse(node) in names

    def _literal_false_defaults(
        self,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> tuple[str, ...]:
        positional = tuple(function.args.posonlyargs) + tuple(function.args.args)
        pairs = list(zip(positional[-len(function.args.defaults) :], function.args.defaults))
        pairs.extend(zip(function.args.kwonlyargs, function.args.kw_defaults))
        return tuple(
            argument.arg
            for argument, default in pairs
            if isinstance(default, ast.Constant) and default.value is False
        )

    def _skip_condition(self, decorator: ast.AST) -> ast.AST | None:
        if not isinstance(decorator, ast.Call) or not decorator.args:
            return None
        name = ast.unparse(decorator.func).lower()
        return decorator.args[0] if name.endswith("skipif") else None

    def _exception_names(self, node: ast.AST | None) -> tuple[str, ...]:
        if node is None:
            return ()
        if isinstance(node, ast.Tuple):
            return tuple(name for item in node.elts for name in self._exception_names(item))
        if isinstance(node, ast.Name):
            return (node.id,)
        if isinstance(node, ast.Attribute):
            return (node.attr,)
        return ()

    def _evaluate(
        self,
        node: ast.AST,
        facts: EnvironmentFacts,
        bindings: Mapping[str, object],
    ) -> object:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return bindings.get(node.id, UNKNOWN)
        if isinstance(node, ast.Attribute) and ast.unparse(node) == "sys.platform":
            return facts.sys_platform
        if isinstance(node, ast.Attribute) and ast.unparse(node) == "sys.version_info":
            return facts.python_version if facts.python_version is not None else UNKNOWN
        if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "sys.version_info":
            index = self._evaluate(node.slice, facts, bindings)
            if not isinstance(index, int):
                return UNKNOWN
            if facts.python_version is not None and 0 <= index < len(facts.python_version):
                return facts.python_version[index]
            return facts.python_major if index == 0 else UNKNOWN
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = self._evaluate(node.operand, facts, bindings)
            return not value if isinstance(value, bool) else UNKNOWN
        if isinstance(node, ast.BoolOp):
            values = [self._evaluate(item, facts, bindings) for item in node.values]
            if any(value is UNKNOWN for value in values):
                return UNKNOWN
            if isinstance(node.op, ast.And):
                return all(bool(value) for value in values)
            if isinstance(node.op, ast.Or):
                return any(bool(value) for value in values)
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            left = self._evaluate(node.left, facts, bindings)
            right = self._evaluate(node.comparators[0], facts, bindings)
            if left is UNKNOWN or right is UNKNOWN:
                return UNKNOWN
            operator = node.ops[0]
            if isinstance(operator, ast.Eq):
                return left == right
            if isinstance(operator, ast.NotEq):
                return left != right
            if isinstance(operator, ast.In):
                return left in right
            if isinstance(operator, ast.NotIn):
                return left not in right
            try:
                if isinstance(operator, ast.Lt):
                    return left < right
                if isinstance(operator, ast.LtE):
                    return left <= right
                if isinstance(operator, ast.Gt):
                    return left > right
                if isinstance(operator, ast.GtE):
                    return left >= right
            except TypeError:
                return UNKNOWN
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values = [self._evaluate(item, facts, bindings) for item in node.elts]
            return UNKNOWN if any(value is UNKNOWN for value in values) else tuple(values)
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func).lower()
            if name.endswith("get_platform"):
                return facts.platform_name
            for suffix, value in (
                ("is_android", facts.platform_name == "android"),
                ("is_darwin", facts.sys_platform == "darwin"),
                ("is_linux", facts.sys_platform.startswith("linux")),
                ("is_windows", facts.sys_platform.startswith("win")),
            ):
                if name.endswith(suffix):
                    return value
        return UNKNOWN


def exclusion_rules_from_pyproject(
    value: Mapping[str, object],
    config_sha256: str,
) -> tuple[ExclusionRule, ...]:
    tool = value.get("tool")
    if not isinstance(tool, Mapping):
        return ()
    rules: list[ExclusionRule] = []
    mypy = tool.get("mypy")
    if isinstance(mypy, Mapping):
        for pattern in _string_sequence(mypy.get("exclude")):
            if _plain_relative_prefix(pattern):
                rules.append(ExclusionRule("mypy", pattern, config_sha256, "prefix"))
    ruff = tool.get("ruff")
    if isinstance(ruff, Mapping):
        for pattern in _string_sequence(ruff.get("extend-exclude")):
            rules.append(ExclusionRule("ruff", pattern, config_sha256, "glob"))
    return tuple(sorted(rules, key=lambda item: (item.tool, item.pattern, item.syntax)))


def _string_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _plain_relative_prefix(value: str) -> bool:
    if not value or value.startswith(("/", ".")) or ".." in PurePosixPath(value).parts:
        return False
    return all(character.isalnum() or character in "/_.-" for character in value)
