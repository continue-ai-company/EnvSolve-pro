#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "experiments/cases/train_untouched_after_pro_trajectory_census_replication_v1_96.jsonl"
)
EXCLUSIONS = (
    ROOT
    / "experiments/cases/dev_pro_postcondition_persistent_qualification_v1_5.jsonl"
)
SELECTED = (
    ROOT
    / "experiments/cases/dev_pro_operation_relevance_contract_v1_5.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/train_untouched_after_pro_operation_relevance_contract_v1_86.jsonl"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_preregistration.json"
)
PROVIDER_PROBE = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_provider_probe.json"
)
PROVENANCE = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_selection.json"
)
SALT = "d00539b:operation-relevance-contract-qv1"
EXPECTED_SOURCE_SHA256 = (
    "8c00f9012821eb67b1035807fef2cb2274d580da954c55f258f72eb7642d8240"
)
EXPECTED_EXCLUSIONS_SHA256 = (
    "f0a732d194bca15199a0989d11831d62fe2c8b77a17e79d823f719dedd14fb30"
)
SAMPLE_SIZE = 5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def main() -> int:
    if sha256(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Untouched source pool hash changed")
    if sha256(EXCLUSIONS) != EXPECTED_EXCLUSIONS_SHA256:
        raise RuntimeError("Consumed exclusion set hash changed")
    if not PREREGISTRATION.is_file():
        raise RuntimeError("Study must be preregistered before selection")
    if not PROVIDER_PROBE.is_file():
        raise RuntimeError("Provider-format probe must pass before selection")
    probe = json.loads(PROVIDER_PROBE.read_text(encoding="utf-8"))
    if probe.get("result", {}).get("qualified") is not True:
        raise RuntimeError("Provider-format probe is not qualified")
    for output in (SELECTED, REMAINING, PROVENANCE):
        if output.exists():
            raise RuntimeError(
                f"Refusing to overwrite selection artifact: {output}"
            )

    rows = read_jsonl(SOURCE)
    excluded_repositories = {
        str(item["repository"]) for item in read_jsonl(EXCLUSIONS)
    }
    eligible = [
        row
        for row in rows
        if str(row["repository"]) not in excluded_repositories
    ]
    if (
        len(rows) != 96
        or len(eligible) != 91
        or len({row["repository"] for row in eligible}) != 91
    ):
        raise RuntimeError("Unexpected repository pool cardinality")
    ranked = sorted(
        eligible,
        key=lambda row: hashlib.sha256(
            (
                f"{SALT}\0{row['repository']}@{row['revision']}"
            ).encode("utf-8")
        ).hexdigest(),
    )
    selected_ids = {row["case_id"] for row in ranked[:SAMPLE_SIZE]}
    selected = [
        {
            **row,
            "split": "dev-pro-operation-relevance-contract-v1-5",
        }
        for row in rows
        if row["case_id"] in selected_ids
    ]
    remaining = [
        {
            **row,
            "split": (
                "train-untouched-after-pro-operation-relevance-"
                "contract-v1-86"
            ),
        }
        for row in eligible
        if row["case_id"] not in selected_ids
    ]
    write_jsonl(SELECTED, selected)
    write_jsonl(REMAINING, remaining)
    provenance = {
        "schema_version": "1.0.0",
        "preregistration": str(PREREGISTRATION.relative_to(ROOT)),
        "preregistration_sha256": sha256(PREREGISTRATION),
        "provider_probe": str(PROVIDER_PROBE.relative_to(ROOT)),
        "provider_probe_sha256": sha256(PROVIDER_PROBE),
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "exclusions": str(EXCLUSIONS.relative_to(ROOT)),
        "exclusions_sha256": EXPECTED_EXCLUSIONS_SHA256,
        "salt": SALT,
        "algorithm": (
            "ascending SHA256(salt + NUL + repository@revision)"
        ),
        "eligible_repositories": len(eligible),
        "selected_case_ids": [row["case_id"] for row in selected],
        "selected_path": str(SELECTED.relative_to(ROOT)),
        "selected_sha256": sha256(SELECTED),
        "remaining_path": str(REMAINING.relative_to(ROOT)),
        "remaining_sha256": sha256(REMAINING),
    }
    PROVENANCE.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
