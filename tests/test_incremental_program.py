from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from envsolve_harness.core.io import read_jsonl
from envsolve_harness.incremental_program import IncrementalProgram


def successful_result() -> dict[str, object]:
    return {
        "command": "ignored by the program state",
        "exit_code": 0,
        "output": "",
        "duration_seconds": 0.1,
        "timed_out": False,
        "infrastructure_error": None,
    }


def test_successful_steps_form_the_exact_ordered_program() -> None:
    with tempfile.TemporaryDirectory() as directory:
        program = IncrementalProgram(Path(directory))
        first = program.append_successful(
            "python -m venv .venv\nsource .venv/bin/activate",
            successful_result(),
        )
        second = program.append_successful(
            "python -m pip install -e .",
            successful_result(),
        )

        persisted = program.program_path.read_text(encoding="utf-8")
        records = read_jsonl(program.steps_path)

    assert first["step"] == 1
    assert second["step"] == 2
    assert persisted == (
        "python -m venv .venv\nsource .venv/bin/activate\n\n"
        "python -m pip install -e .\n"
    )
    assert [record["command"] for record in records] == [
        "python -m venv .venv\nsource .venv/bin/activate",
        "python -m pip install -e .",
    ]


@pytest.mark.parametrize(
    "result",
    [
        {**successful_result(), "exit_code": 1},
        {**successful_result(), "timed_out": True},
        {**successful_result(), "infrastructure_error": "docker exited"},
    ],
)
def test_failed_operations_never_enter_the_program(result: dict[str, object]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        program = IncrementalProgram(Path(directory))
        with pytest.raises(ValueError, match="successful executed command"):
            program.append_successful("false", result)

        assert program.steps == []
        assert not program.steps_path.exists()
        assert not program.program_path.exists()
