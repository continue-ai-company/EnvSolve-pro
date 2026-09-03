from __future__ import annotations

import json

from experiments.run_envsolve_pro_v7_branches import branch_prompt
from envsolve_harness.adapters.envbench_executor import (
    withheld_envbench_feedback_payload,
)


def test_branch_prompt_differs_only_by_structured_payload() -> None:
    real = {
        "schema_version": "1.0.0",
        "status": "completed",
        "withheld": False,
        "bootstrap": {
            "terminal_class": "bootstrap_completed",
            "exit_code": 0,
            "git_ownership_error": False,
        },
        "goal_report": {"present": True, "issues_count": 2, "error_count": 2},
        "missing_imports": [{"path": "src/a.py", "module": "missing", "count": 2}],
        "active_project_python": ".venv/bin/python",
        "infrastructure": None,
    }
    null = withheld_envbench_feedback_payload()

    real_prompt = branch_prompt(real)
    null_prompt = branch_prompt(null)

    assert real_prompt.replace(
        json.dumps(real, ensure_ascii=True, indent=2, sort_keys=True),
        "<payload>",
    ) == null_prompt.replace(
        json.dumps(null, ensure_ascii=True, indent=2, sort_keys=True),
        "<payload>",
    )
    assert "request tools" in real_prompt
    assert '"withheld": true' in null_prompt
