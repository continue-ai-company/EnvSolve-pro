from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness import boundary_v2
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.certification_repair_boundary_v2 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
    ONE_SHOT_METHOD,
    BoundaryV2QualifiedCodexCliRunner,
    BoundaryV2QualifiedMinimalBRunner,
    BoundaryV2QualifiedOneShotRunner,
)


def _runner(runner_type: type, root: Path):
    return runner_type(
        codex_executable=root / "codex",
        harness_root=root,
        source_cache_root=root / "cache",
        image="sha256:fixture",
        timeout=100,
        command_timeout=20,
        container_create_timeout=10,
        git_fetch_timeout=10,
        goal_contract=ExecutableGoalContract(
            "goal-v3",
            "Fixture goal",
            "true",
        ),
    )


def _case() -> Case:
    return Case(
        case_id="fixture",
        repository="owner/repo",
        revision="a" * 40,
        language="python",
        split="consumed-qualification",
    )


def test_boundary_v2_audit_accepts_namespace_package_and_rejects_shim() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project = root / "project"
        namespace = project / "src" / "acme" / "widgets"
        namespace.mkdir(parents=True)
        (namespace / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

        environment = root / "environment"
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(environment)],
            check=True,
        )
        python = environment / "bin" / "python"
        site_packages = Path(
            subprocess.run(
                [
                    str(python),
                    "-I",
                    "-c",
                    "import sysconfig; print(sysconfig.get_paths()['purelib'])",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        distribution = site_packages / "synthetic_shim-0.dist-info"
        distribution.mkdir(parents=True)
        (site_packages / "synthetic_shim.py").write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )
        (distribution / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: synthetic-shim\nVersion: 0\n",
            encoding="utf-8",
        )
        (distribution / "top_level.txt").write_text(
            "synthetic_shim\n",
            encoding="utf-8",
        )
        local_origin = root / "outside-project"
        local_origin.mkdir()
        (distribution / "direct_url.json").write_text(
            json.dumps({"url": local_origin.as_uri()}),
            encoding="utf-8",
        )
        (distribution / "RECORD").write_text(
            "synthetic_shim.py,,\n"
            "synthetic_shim-0.dist-info/METADATA,,\n"
            "synthetic_shim-0.dist-info/top_level.txt,,\n"
            "synthetic_shim-0.dist-info/direct_url.json,,\n"
            "synthetic_shim-0.dist-info/RECORD,,\n",
            encoding="utf-8",
        )

        marker = "ENVSOLVE_TEST_AUDIT="
        completed = subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                boundary_v2.boundary_v2_local_distribution_audit(),
                str(project),
                marker,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout.removeprefix(marker))

        assert "acme" in payload["provided_modules"]
        assert [item["undeclared_modules"] for item in payload["violations"]] == [
            ["synthetic_shim"]
        ]


def test_boundary_v2_audit_installation_is_idempotent(monkeypatch) -> None:
    original = boundary_v2.minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT
    monkeypatch.setattr(
        boundary_v2.minimal_b_mcp,
        "_LOCAL_DISTRIBUTION_AUDIT",
        original,
    )

    boundary_v2.install_boundary_v2_local_distribution_audit()
    installed = boundary_v2.minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT
    boundary_v2.install_boundary_v2_local_distribution_audit()

    assert "for item in child.rglob(\"*\")" in installed
    assert boundary_v2.minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT == installed


def test_boundary_v2_methods_select_the_public_goal() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        fixtures = (
            (BoundaryV2QualifiedCodexCliRunner, CONTROL_METHOD),
            (BoundaryV2QualifiedOneShotRunner, ONE_SHOT_METHOD),
            (BoundaryV2QualifiedMinimalBRunner, MINIMAL_B_METHOD),
        )
        for runner_type, method in fixtures:
            runner = _runner(runner_type, root)
            selected = runner._goal_contract_for_run(
                RunSpec("run", method, "gpt-5.5")
            )
            assert selected is runner.goal_contract


def test_boundary_v2_replay_runners_use_versioned_mcp_modules() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        trace = root / "generation" / "commands.jsonl"
        trace.parent.mkdir(parents=True)
        one_shot = _runner(BoundaryV2QualifiedOneShotRunner, root)
        minimal_b = _runner(BoundaryV2QualifiedMinimalBRunner, root)

        one_shot_args = one_shot._mcp_server_args(
            trace_path=trace,
            container_id="container-1",
            case=_case(),
            image_digest="sha256:fixture",
        )
        minimal_b_args = minimal_b._mcp_server_args(
            trace_path=trace,
            container_id="container-1",
            case=_case(),
            image_digest="sha256:fixture",
        )

        assert (
            "envsolve_harness.codex.one_shot_mcp_boundary_v2_qualified"
            in one_shot_args
        )
        assert (
            "envsolve_harness.codex.minimal_b_mcp_boundary_v2_qualified"
            in minimal_b_args
        )
