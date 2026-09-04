from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from experiments.tools.run_post_v7_repeatability import main, schedule, workspace_snapshot


class RepeatabilityStudyTest(unittest.TestCase):
    def test_completed_failures_do_not_trigger_retries(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pilot = root / "pilot"
            for pos in ("02", "07", "08"):
                original = pilot / "online" / f"{pos}-P0" / "input.jsonl"
                original.parent.mkdir(parents=True)
                original.write_text(json.dumps({"repository": f"owner/repo{pos}", "revision": "abc", "script": "exit 1\n"}))
                script = pilot / "inputs" / pos / "P0.sh"
                script.parent.mkdir(parents=True)
                script.write_text("exit 1\n")
            commands = []

            class FailedExecution:
                returncode = 1

                def __init__(self, command, **kwargs):
                    commands.append(command)
                    output = Path(command[command.index("--output-root") + 1])
                    output.mkdir()
                    (output / "execution.json").write_text('{"completed": false}')

                def poll(self):
                    return self.returncode

            argv = ["study", "--pilot-root", str(pilot), "--output-root", str(root / "results"), "--executor-root", directory, "--envbench-root", directory, "--python", "python", "--image", "recorded-image"]
            with patch("sys.argv", argv), patch("subprocess.Popen", FailedExecution), patch("builtins.print"):
                self.assertEqual(main(), 0)
            self.assertEqual(len(commands), 15)
            self.assertEqual(len({c[c.index("--output-root") + 1] for c in commands}), 15)
            self.assertTrue(all(c[c.index("--mode") + 1] == "postepisode" for c in commands))

    def test_fixed_interleaved_schedule(self):
        jobs = schedule()
        self.assertEqual(len(jobs), 15)
        self.assertEqual(jobs[:6], [(1, "02"), (1, "07"), (1, "08"), (2, "02"), (2, "07"), (2, "08")])
        for position in ("02", "07", "08"):
            self.assertEqual(sum(p == position for _, p in jobs), 5)

    def test_snapshot_observes_without_modifying_workspace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / ".venv/lib/python3.10/site-packages/control-1.0.dist-info"
            dist.mkdir(parents=True)
            version = root / "control/_version.py"
            version.parent.mkdir()
            version.write_text('__version__ = "1.0"\n')
            before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            result = workspace_snapshot(root)
            self.assertEqual(result["control_version_file"], version.read_text())
            self.assertEqual(result["distribution_directories"], [str(dist.relative_to(root))])
            self.assertEqual(before, sorted(str(p.relative_to(root)) for p in root.rglob("*")))

    def test_deleted_workspace_is_not_a_final_inventory(self):
        with TemporaryDirectory() as directory:
            result = workspace_snapshot(Path(directory) / "missing")
            self.assertFalse(result["repo_present"])
            self.assertEqual(result["distribution_directories"], [])
            self.assertIn("not a certified final", result["qualification"])
