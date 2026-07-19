from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from .models import Case


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return records


def write_json(path: Path, value: Any) -> None:
    write_text_atomic(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    write_text_atomic(path, content)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_case(path: Path, case_id: str | None = None) -> Case:
    cases = [Case.from_dict(record) for record in read_jsonl(path)]
    if case_id is None:
        if len(cases) != 1:
            raise ValueError(f"{path} contains {len(cases)} cases; pass --case-id")
        return cases[0]
    matches = [case for case in cases if case.case_id == case_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one case named {case_id!r} in {path}, found {len(matches)}")
    return matches[0]
