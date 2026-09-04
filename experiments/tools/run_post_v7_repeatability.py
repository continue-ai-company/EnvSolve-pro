"""One-off, model-free execution of the approved 3 x 5 repeatability study."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def schedule() -> list[tuple[int, str]]:
    return [(round_id, position) for round_id in range(1, 6) for position in ("02", "07", "08")]


def workspace_snapshot(repo: Path) -> dict:
    distributions = sorted(
        str(path.relative_to(repo))
        for path in repo.glob(".venv/lib/python*/site-packages/*.dist-info")
    )
    version = repo / "control/_version.py"
    try:
        version_text = version.read_text() if version.is_file() else None
    except OSError:
        version_text = None
    return {
        "repo_present": repo.is_dir(),
        "distribution_directories": distributions,
        "control_version_file": version_text,
        "pyright_output_present": (repo / "build_output/pyright_output.json").is_file(),
        "qualification": "Read-only in-flight sample, not a certified final environment inventory.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--executor-root", type=Path, required=True)
    parser.add_argument("--envbench-root", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)
    outcomes = []
    for round_id, position in schedule():
        name = f"round-{round_id:02d}-case-{position}"
        root = args.output_root / name
        original = json.loads(
            (args.pilot_root / "online" / f"{position}-P0" / "input.jsonl").read_text()
        )
        script = args.pilot_root / "inputs" / position / "P0.sh"
        if script.read_text() != original["script"]:
            raise ValueError(f"Original script and execution input disagree: {position}")
        repository, revision = original["repository"], original["revision"]
        command = [
            args.python, "-m", "experiments.tools.run_envsolve_pro_v7_candidate",
            "--mode", "postepisode", "--case-id", f"envbench-python-{repository.replace('/', '__')}@{revision}",
            "--repository", repository, "--revision", revision,
            "--script", str(script), "--envbench-root", str(args.envbench_root),
            "--output-root", str(root), "--cache-root", str(args.pilot_root / "source-cache"),
            "--image", args.image,
        ]
        print(json.dumps({"event": "start", "run": name, "command": command}), flush=True)
        repo = root / "repos" / f"{repository.replace('/', '__')}@{revision}"
        with (args.output_root / f"{name}.stdout").open("w") as log, (
            args.output_root / f"{name}.samples.jsonl"
        ).open("w") as samples:
            process = subprocess.Popen(command, cwd=args.executor_root, stdout=log, stderr=subprocess.STDOUT)
            previous = None
            while process.poll() is None:
                snapshot = workspace_snapshot(repo)
                if snapshot != previous:
                    samples.write(json.dumps({"observed_at": datetime.now(timezone.utc).isoformat(), **snapshot}) + "\n")
                    samples.flush()
                    previous = snapshot
                time.sleep(2)
        outcome = {"run": name, "process_returncode": process.returncode, "execution_record_present": (root / "execution.json").is_file()}
        outcomes.append(outcome)
        print(json.dumps({"event": "finished", **outcome}), flush=True)
        if not outcome["execution_record_present"]:
            # An unaccounted process failure is not permission to advance or retry.
            break
    (args.output_root / "schedule_result.json").write_text(json.dumps(outcomes, indent=2) + "\n")
    return 0 if len(outcomes) == 15 and all(x["execution_record_present"] for x in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
