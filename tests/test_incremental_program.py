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


def test_program_steps_can_be_replaced_and_deleted_with_refreshed_indexes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        program = IncrementalProgram(Path(directory))
        program.append_successful("bad-one", successful_result())
        program.append_successful("keep-two", successful_result())
        program.append_successful("remove-three", successful_result())

        replacement = program.revise(1, "good-one")
        deletion = program.revise(3, "")
        records = read_jsonl(program.steps_path)

    assert replacement == {
        "schema": "envsolve-pro-incremental-program-v1",
        "operation": "replace",
        "step_index": 1,
        "previous_command": "bad-one",
        "replacement_command": "good-one",
    }
    assert deletion["operation"] == "delete"
    assert deletion["previous_command"] == "remove-three"
    assert program.indexed_steps() == [
        {"step": 1, "command": "good-one"},
        {"step": 2, "command": "keep-two"},
    ]
    assert [record["step"] for record in records] == [1, 2]
    assert program.program == "good-one\n\nkeep-two"


@pytest.mark.parametrize("step_index", [0, 2, True, "1"])
def test_program_revision_rejects_invalid_step_indexes(step_index: object) -> None:
    with tempfile.TemporaryDirectory() as directory:
        program = IncrementalProgram(Path(directory))
        program.append_successful("only-step", successful_result())

        with pytest.raises(ValueError, match="step index"):
            program.revise(step_index, "replacement")  # type: ignore[arg-type]
