#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.adapters.envbench_executor import (
    withheld_envbench_feedback_payload,
)
from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_text_atomic
from envsolve_harness.runners.codex_cli import parse_codex_usage
from envsolve_harness.runners.native_codex_fork import (
    CompletedCodexPrefix,
    NativeCodexForkPlan,
    build_named_tool_free_native_fork,
)


def continuation_prompt(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    return (
        "You have one additional revision opportunity for the complete bootstrap "
        "program from the preceding turn. The only new target-state information "
        "available in this branch is the structured payload below:\n\n"
        f"{serialized}\n\n"
        "Return one complete bootstrap program for the same repository. You may keep "
        "the preceding program unchanged or revise it based on this information. "
        "The program must be self-contained because it will be executed from a fresh "
        "checkout. Do not request tools or additional execution."
    )


def _load_parent(artifacts: Path) -> CompletedCodexPrefix:
    trajectory = read_jsonl(artifacts / "generation/trajectory.jsonl")
    final_output_path = artifacts / "generation/codex-control/final-output.json"
    return CompletedCodexPrefix.from_events(
        trajectory,
        final_output_path.read_text(encoding="utf-8"),
    )


def _run_branch(plan: NativeCodexForkPlan, timeout: int) -> dict[str, object]:
    plan.events_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        list(plan.command),
        input=plan.prompt,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    write_text_atomic(plan.events_path, completed.stdout)
    write_text_atomic(plan.events_path.with_suffix(".stderr"), completed.stderr)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Codex {plan.branch} fork failed with exit code {completed.returncode}: "
            f"{completed.stderr[-2000:]}"
        )
    records = read_jsonl(plan.events_path)
    output_text = plan.output_path.read_text(encoding="utf-8")
    child = CompletedCodexPrefix.from_events(records, output_text)
    output = json.loads(output_text)
    if not isinstance(output, dict) or not isinstance(
        output.get("bootstrap_script"), str
    ):
        raise ValueError(f"Codex {plan.branch} output has no bootstrap_script")
    script = str(output["bootstrap_script"])
    if not script.strip():
        raise ValueError(f"Codex {plan.branch} bootstrap_script is empty")
    script_path = plan.events_path.parent / "generated.sh"
    write_text_atomic(script_path, script.rstrip() + "\n")
    return {
        "branch": plan.branch,
        "parent_session_id": plan.parent.session_id,
        "child_session_id": child.session_id,
        "event_count": child.event_count,
        "completed_turn_count": child.completed_turn_count,
        "usage": parse_codex_usage(records),
        "script_path": str(script_path),
        "summary": output.get("summary"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fork matched C1 and T continuations from one completed C0 session."
    )
    parser.add_argument("--c0-artifacts", type=Path, required=True)
    parser.add_argument("--execution-json", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--branch-order", choices=("C1-first", "T-first"), required=True)
    parser.add_argument("--codex", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="xhigh")
    parser.add_argument("--timeout", type=int, default=18000)
    args = parser.parse_args()

    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Branch output already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    c0_artifacts = args.c0_artifacts.resolve()
    parent = _load_parent(c0_artifacts)
    parent_output = json.loads(parent.final_output)
    c0_program = parent_output.get("bootstrap_script")
    if not isinstance(c0_program, str) or not c0_program.strip():
        raise ValueError("C0 final output has no bootstrap_script")
    write_text_atomic(output_root / "C0" / "generated.sh", c0_program.rstrip() + "\n")

    execution = read_json(args.execution_json.resolve())
    feedback = execution.get("observation") if isinstance(execution, dict) else None
    if not isinstance(feedback, dict):
        raise ValueError("C0 execution record has no observation object")
    payloads = {
        "C1": withheld_envbench_feedback_payload(),
        "T": feedback,
    }
    schema_path = c0_artifacts / "generation/codex-control/output-schema.json"
    plans = {
        branch: build_named_tool_free_native_fork(
            branch=branch,
            parent=parent,
            codex_executable=args.codex.resolve(),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            schema_path=schema_path,
            events_path=output_root / branch / "trajectory.jsonl",
            output_path=output_root / branch / "final-output.json",
            prompt=continuation_prompt(payloads[branch]),
        )
        for branch in ("C1", "T")
    }
    if plans["C1"].parent != plans["T"].parent:
        raise RuntimeError("C1 and T do not share the same completed C0 prefix")

    order = ("C1", "T") if args.branch_order == "C1-first" else ("T", "C1")
    results = []
    for branch in order:
        plan = plans[branch]
        write_text_atomic(plan.events_path.parent / "prompt.txt", plan.prompt)
        write_json(plan.events_path.parent / "command.json", list(plan.command))
        results.append(_run_branch(plan, args.timeout))
    write_json(
        output_root / "result.json",
        {
            "schema": "envsolve-pro-m1c-matched-continuations-v1",
            "c0_session_id": parent.session_id,
            "c0_event_count": parent.event_count,
            "c0_program_path": str(output_root / "C0" / "generated.sh"),
            "branch_order": args.branch_order,
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "tool_free": True,
            "unique_branch_difference": "real replay payload versus typed-null payload",
            "results": results,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
