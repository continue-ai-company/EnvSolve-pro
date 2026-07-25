from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


_SKIPPED_DIRECTORIES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


@dataclass(frozen=True)
class _SourceDocument:
    path: str
    text: str
    sha256: str


class RepositoryEvidenceIndex:
    """Bounded read-only source evidence routed by executable findings."""

    schema = "envsolve-constraint-routed-repository-evidence-v1"

    def __init__(
        self,
        root: Path,
        *,
        max_files: int = 2_000,
        max_source_bytes: int = 16_000_000,
        max_file_bytes: int = 512_000,
    ) -> None:
        if min(max_files, max_source_bytes, max_file_bytes) <= 0:
            raise ValueError("Repository evidence bounds must be positive")
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ValueError("Repository evidence root must be a directory")
        self.max_files = max_files
        self.max_source_bytes = max_source_bytes
        self.max_file_bytes = max_file_bytes
        self._documents, self._index_truncated = self._load_documents()
        self._by_path = {document.path: document for document in self._documents}

    def _load_documents(self) -> tuple[tuple[_SourceDocument, ...], bool]:
        documents: list[_SourceDocument] = []
        source_bytes = 0
        truncated = False
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root)
            if any(part in _SKIPPED_DIRECTORIES for part in relative.parts):
                continue
            try:
                if not path.is_file() or path.is_symlink():
                    continue
                size = path.stat().st_size
                if size > self.max_file_bytes:
                    continue
                if len(documents) >= self.max_files or source_bytes + size > self.max_source_bytes:
                    truncated = True
                    continue
                payload = path.read_bytes()
            except OSError:
                continue
            if b"\0" in payload:
                continue
            text = payload.decode("utf-8", errors="replace")
            source_bytes += len(payload)
            documents.append(
                _SourceDocument(
                    path=relative.as_posix(),
                    text=text,
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
            )
        return tuple(documents), truncated

    def _relative_finding_path(self, value: object) -> str | None:
        if not isinstance(value, str) or not value:
            return None
        candidate = PurePosixPath(value)
        if not candidate.is_absolute():
            normalized = str(candidate)
            return normalized if normalized in self._by_path else None
        parts = candidate.parts
        for index in range(1, len(parts)):
            suffix = PurePosixPath(*parts[index:]).as_posix()
            if suffix in self._by_path:
                return suffix
        return None

    @staticmethod
    def _finding_line(provenance: dict[str, Any]) -> int | None:
        range_value = provenance.get("range")
        start = range_value.get("start") if isinstance(range_value, dict) else None
        range_line = start.get("line") if isinstance(start, dict) else None
        if (
            isinstance(range_line, int)
            and not isinstance(range_line, bool)
            and range_line >= 0
        ):
            return range_line + 1
        line = provenance.get("line")
        if isinstance(line, int) and not isinstance(line, bool) and line >= 1:
            return line
        return None

    @staticmethod
    def _excerpt(
        document: _SourceDocument,
        center_line: int,
        *,
        radius: int,
    ) -> dict[str, Any]:
        lines = document.text.splitlines()
        if not lines:
            return {
                "path": document.path,
                "source_sha256": document.sha256,
                "start_line": 1,
                "end_line": 0,
                "text": "",
            }
        center_line = min(max(1, center_line), len(lines))
        start = max(1, center_line - radius)
        end = min(len(lines), center_line + radius)
        text = "\n".join(
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        )
        return {
            "path": document.path,
            "source_sha256": document.sha256,
            "start_line": start,
            "end_line": end,
            "text": text,
        }

    def _related_occurrences(
        self,
        query: str,
        *,
        preferred_path: str | None,
        max_occurrences: int,
    ) -> list[dict[str, Any]]:
        matches: list[tuple[int, str, int, _SourceDocument]] = []
        for document in self._documents:
            for line_number, line in enumerate(document.text.splitlines(), start=1):
                if query in line:
                    matches.append(
                        (
                            0 if document.path == preferred_path else 1,
                            document.path,
                            line_number,
                            document,
                        )
                    )
        return [
            self._excerpt(document, line_number, radius=6)
            for _, _, line_number, document in sorted(matches)[:max_occurrences]
        ]

    @staticmethod
    def _bounded(value: dict[str, Any], max_chars: int) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True)
        if len(encoded) <= max_chars:
            return value
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        queries = value.get("queries")
        if isinstance(queries, list):
            while any(
                isinstance(query.get("related_occurrences"), list)
                and query["related_occurrences"]
                for query in queries
            ) and len(
                json.dumps(value, ensure_ascii=True, sort_keys=True)
            ) > max_chars:
                query = max(
                    (
                        item
                        for item in queries
                        if isinstance(item.get("related_occurrences"), list)
                        and item["related_occurrences"]
                    ),
                    key=lambda item: len(item["related_occurrences"]),
                )
                query["related_occurrences"].pop()
            excerpts = [
                excerpt
                for query in queries
                for excerpt in (query.get("target_excerpt"),)
                if isinstance(excerpt, dict)
                and isinstance(excerpt.get("text"), str)
                and excerpt["text"]
            ]
            while excerpts and len(
                json.dumps(value, ensure_ascii=True, sort_keys=True)
            ) > max_chars:
                excerpt = max(excerpts, key=lambda item: len(item["text"]))
                text = excerpt["text"]
                if len(text) <= 64:
                    excerpt["text"] = ""
                    excerpt["truncated"] = True
                    excerpts.remove(excerpt)
                    continue
                excerpt["text"] = text[: max(64, len(text) // 2)]
                excerpt["truncated"] = True
        value["truncated"] = True
        value["sha256_before_truncation"] = digest
        if len(json.dumps(value, ensure_ascii=True, sort_keys=True)) <= max_chars:
            return value
        compact = {
            key: item
            for key, item in value.items()
            if key not in {"queries", "sha256_before_truncation"}
        }
        compact["queries"] = [
            {
                "subject": query.get("subject"),
                "diagnostic_path": query.get("diagnostic_path"),
                "diagnostic_line": query.get("diagnostic_line"),
            }
            for query in queries
            if isinstance(query, dict)
        ] if isinstance(queries, list) else []
        compact["sha256_before_truncation"] = digest
        if (
            len(json.dumps(compact, ensure_ascii=True, sort_keys=True))
            <= max_chars
        ):
            return compact
        fallback: dict[str, Any] = {
            "truncated": True,
            "sha256_before_truncation": digest,
        }
        if len(json.dumps(fallback, sort_keys=True)) <= max_chars:
            return fallback
        return {"truncated": True}

    def retrieve(
        self,
        findings: Iterable[dict[str, Any]],
        *,
        max_queries: int = 8,
        max_occurrences_per_query: int = 12,
        max_chars: int = 12_000,
    ) -> dict[str, Any]:
        if min(max_queries, max_occurrences_per_query) <= 0 or max_chars < 32:
            raise ValueError("Repository evidence retrieval bounds must be positive")
        input_finding_count = 0
        routed_findings: list[tuple[str, str | None, int | None]] = []
        routed_index_by_subject: dict[str, int] = {}
        for finding in findings:
            input_finding_count += 1
            if not isinstance(finding, dict):
                continue
            subject = finding.get("subject")
            provenance = finding.get("provenance")
            if (
                not isinstance(subject, str)
                or not subject
                or not isinstance(provenance, dict)
            ):
                continue
            path = self._relative_finding_path(provenance.get("file"))
            line = self._finding_line(provenance)
            routed = (subject, path, line)
            previous_index = routed_index_by_subject.get(subject)
            if previous_index is None:
                routed_index_by_subject[subject] = len(routed_findings)
                routed_findings.append(routed)
                continue
            previous = routed_findings[previous_index]
            previous_quality = (
                previous[1] is not None and previous[2] is not None,
                previous[1] is not None,
            )
            current_quality = (
                path is not None and line is not None,
                path is not None,
            )
            if current_quality > previous_quality:
                routed_findings[previous_index] = routed

        queries: list[dict[str, Any]] = []
        for subject, path, line in routed_findings[:max_queries]:
            target = (
                self._excerpt(self._by_path[path], line, radius=8)
                if path in self._by_path and line is not None
                else None
            )
            queries.append(
                {
                    "subject": subject,
                    "diagnostic_path": path,
                    "diagnostic_line": line,
                    "target_excerpt": target,
                    "related_occurrences": self._related_occurrences(
                        subject,
                        preferred_path=path,
                        max_occurrences=max_occurrences_per_query,
                    ),
                }
            )
        value = {
            "schema": self.schema,
            "root_identity": self.root.name,
            "indexed_files": len(self._documents),
            "index_truncated": self._index_truncated,
            "input_finding_count": input_finding_count,
            "distinct_subject_count": len(routed_findings),
            "included_query_count": len(queries),
            "omitted_query_count": max(len(routed_findings) - len(queries), 0),
            "queries": queries,
            "truncated": False,
        }
        return self._bounded(value, max_chars)
