#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_jsonl, write_json, write_text_atomic
from envsolve_harness.scripts.envbench_trajectory import (
    commands_from_trajectory,
    compile_envbench_open_program,
)
from envsolve_harness.scripts.open_program import OPEN_PROGRAM_POLICY
from envsolve_harness.scripts.repo2run import compile_repo2run_open_program
from envsolve_harness.utils.provenance import sha256_file


SOURCES = ROOT / "experiments/validations/pro_p1_consumed_sources"
TARGETS = (
    {
        "target_id": "c03-marimo-raw-react",
        "kind": "envbench-trajectory",
        "source": "c03_marimo_raw_react.jsonl",
        "project_directory": (
            "marimo-team__marimo@537b23093bb75afd57b2c1f1d2f5cd528a08fc66"
        ),
        "repository": "marimo-team/marimo",
        "revision": "537b23093bb75afd57b2c1f1d2f5cd528a08fc66",
    },
    {
        "target_id": "c04-futaba-raw-react",
        "kind": "envbench-trajectory",
        "source": "c04_futaba_raw_react.jsonl",
        "project_directory": (
            "strinking__futaba@2e4d7874f0b99176f7595f776dfebf2eac26afbb"
        ),
        "repository": "strinking/futaba",
        "revision": "2e4d7874f0b99176f7595f776dfebf2eac26afbb",
    },
    {
        "target_id": "c03-marimo-repo2run",
        "kind": "repo2run-inner-commands",
        "source": "c03_marimo_repo2run_inner_commands.json",
        "repository": "marimo-team/marimo",
        "revision": "537b23093bb75afd57b2c1f1d2f5cd528a08fc66",
    },
    {
        "target_id": "c05-importlib-metadata-raw-react",
        "kind": "envbench-trajectory",
        "source": "c05_importlib_metadata_raw_react.jsonl",
        "project_directory": (
            "python__importlib_metadata@f3901686abc47853523f3b211873fc2b9e0c5ab5"
        ),
        "repository": "python/importlib_metadata",
        "revision": "f3901686abc47853523f3b211873fc2b9e0c5ab5",
    },
    {
        "target_id": "c04-futaba-repo2run",
        "kind": "repo2run-inner-commands",
        "source": "c04_futaba_repo2run_inner_commands.json",
        "repository": "strinking/futaba",
        "revision": "2e4d7874f0b99176f7595f776dfebf2eac26afbb",
    },
    {
        "target_id": "c05-importlib-metadata-repo2run",
        "kind": "repo2run-inner-commands",
        "source": "c05_importlib_metadata_repo2run_inner_commands.json",
        "repository": "python/importlib_metadata",
        "revision": "f3901686abc47853523f3b211873fc2b9e0c5ab5",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile consumed P0 trajectories through the frozen P1 interface."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "experiments/validations/pro_p1_consumed_replay_v1",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _compiler_sha256() -> str:
    digest = hashlib.sha256()
    for relative in (
        "envsolve_harness/scripts/envbench_trajectory.py",
        "envsolve_harness/scripts/open_program.py",
        "envsolve_harness/scripts/repo2run.py",
    ):
        path = ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    output_root = args.output_root.resolve()
    if output_root.exists():
        if not args.overwrite:
            raise FileExistsError(f"Qualification output already exists: {output_root}")
        shutil.rmtree(output_root)
    scripts = output_root / "scripts"
    scripts.mkdir(parents=True)

    results: list[dict[str, Any]] = []
    for target in TARGETS:
        source = SOURCES / str(target["source"])
        if target["kind"] == "envbench-trajectory":
            records = read_jsonl(source)
            commands = commands_from_trajectory(records)
            compiled = compile_envbench_open_program(
                commands,
                project_directory=str(target["project_directory"]),
            )
        else:
            commands = _load_json(source)
            if not isinstance(commands, list):
                raise ValueError(f"Repo2Run source is not a command list: {source}")
            compiled = compile_repo2run_open_program(commands)
        script_path = scripts / f"{target['target_id']}.sh"
        write_text_atomic(script_path, compiled.script)
        unsupported = tuple(
            getattr(
                compiled,
                "unknown_commands",
                getattr(compiled, "unsupported_commands", ()),
            )
        )
        results.append(
            {
                **target,
                "source": str(source.relative_to(ROOT)),
                "source_sha256": sha256_file(source),
                "script": str(script_path.relative_to(ROOT)),
                "script_sha256": sha256_file(script_path),
                "kept_count": len(compiled.kept_commands),
                "dropped_count": len(compiled.dropped_commands),
                "unsupported_count": len(unsupported),
                "unsupported_commands": list(unsupported),
            }
        )

    summary = {
        "schema": "envsolve-pro-p1-consumed-interface-qualification-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": OPEN_PROGRAM_POLICY,
        "model_requests": 0,
        "consumed_cases_only": True,
        "compiler_sha256": _compiler_sha256(),
        "targets": results,
    }
    write_json(output_root / "compilation.json", summary)
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if all(item["unsupported_count"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
