from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.tools import (
    select_pro_operation_relevance_contract_v1 as selector,
)


ROOT = Path(__file__).resolve().parents[1]
FREEZE = (
    ROOT
    / "experiments/protocols/pro_operation_relevance_contract_v1_freeze.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_preregistration.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_algorithm_freeze_hashes_match_without_mutating_frozen_baseline() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))

    for group in (
        "algorithm_files",
        "preserved_baseline_files",
        "design_files",
    ):
        for relative, expected in freeze[group].items():
            assert _sha256(ROOT / relative) == expected, relative


def test_preregistration_binds_inputs_before_case_selection() -> None:
    preregistration = json.loads(
        PREREGISTRATION.read_text(encoding="utf-8")
    )

    assert preregistration["algorithm_freeze"]["sha256"] == _sha256(FREEZE)
    for key in ("source_case_file", "consumed_exclusion_file"):
        path = ROOT / preregistration["selection"][key]
        assert _sha256(path) == preregistration["selection"][f"{key}_sha256"]
    for key in ("config", "protocol"):
        path = ROOT / preregistration["shared_contract"][key]
        assert _sha256(path) == preregistration["shared_contract"][
            f"{key}_sha256"
        ]
    assert (
        preregistration["analysis"][
            "no_algorithm_prompt_or_threshold_change_after_selection"
        ]
        is True
    )


def test_selection_remains_closed_until_provider_probe_qualifies() -> None:
    for output in (
        selector.SELECTED,
        selector.REMAINING,
        selector.PROVENANCE,
    ):
        assert not output.exists()
    assert not selector.PROVIDER_PROBE.exists()

    with pytest.raises(RuntimeError, match="Provider-format probe"):
        selector.main()
