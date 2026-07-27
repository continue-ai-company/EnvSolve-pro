#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCHEDULE = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_schedule.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_deepseek_direct_replication_preregistration.json"
)
PROVIDER_CLOSURE = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_deepseek_direct_provider_closure.json"
)
CONFIG = (
    ROOT
    / "experiments/configs/local_mac_pro_operation_relevance_v1_deepseek_direct.json"
)
OUTPUT = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_deepseek_direct_schedule.json"
)
MODEL = "deepseek-v4-pro"
RUN_ID_SOURCE_PREFIX = "pro-oprel-qv1-"
RUN_ID_DIRECT_PREFIX = "pro-oprel-qv1-ds-direct-"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"Refusing to overwrite schedule: {OUTPUT}")

    source = json.loads(SOURCE_SCHEDULE.read_text(encoding="utf-8"))
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    provider_closure = json.loads(
        PROVIDER_CLOSURE.read_text(encoding="utf-8")
    )
    if preregistration["status"] != (
        "preregistered-before-provider-closure-and-real-execution"
    ):
        raise RuntimeError("Direct replication was not preregistered")
    if provider_closure["result"]["qualified"] is not True:
        raise RuntimeError("DeepSeek direct provider gate is not qualified")
    if source["implementation_freeze"] != (
        preregistration["algorithm_freeze"]["commit"]
    ):
        raise RuntimeError("Source schedule and preregistration freeze differ")

    episodes = []
    for source_episode in source["episodes"]:
        source_run_id = str(source_episode["run_id"])
        if not source_run_id.startswith(RUN_ID_SOURCE_PREFIX):
            raise RuntimeError(f"Unexpected source run ID: {source_run_id}")
        episode = dict(source_episode)
        episode["model"] = MODEL
        episode["source_run_id"] = source_run_id
        episode["run_id"] = source_run_id.replace(
            RUN_ID_SOURCE_PREFIX,
            RUN_ID_DIRECT_PREFIX,
            1,
        )
        episodes.append(episode)

    value = {
        "schema_version": "1.0.0",
        "study_id": (
            "envsolve-pro-operation-relevance-contract-v1-"
            "deepseek-direct-replication"
        ),
        "status": "frozen-before-execution",
        "claim_scope": preregistration["claim_scope"],
        "implementation_freeze": source["implementation_freeze"],
        "source_schedule": str(SOURCE_SCHEDULE.relative_to(ROOT)),
        "source_schedule_sha256": sha256(SOURCE_SCHEDULE),
        "preregistration": str(PREREGISTRATION.relative_to(ROOT)),
        "preregistration_sha256": sha256(PREREGISTRATION),
        "provider_closure": str(PROVIDER_CLOSURE.relative_to(ROOT)),
        "provider_closure_sha256": sha256(PROVIDER_CLOSURE),
        "case_file": source["case_file"],
        "case_file_sha256": source["case_file_sha256"],
        "episode_timeout_seconds": source["episode_timeout_seconds"],
        "model": MODEL,
        "provider": {
            "name": "deepseek-direct",
            "base_url": "https://api.deepseek.com",
            "serving_provider_is_experimental_factor": True,
        },
        "execution": {
            "config": str(CONFIG.relative_to(ROOT)),
            "config_sha256": sha256(CONFIG),
            "protocol": source["execution"]["protocol"],
            "protocol_sha256": source["execution"]["protocol_sha256"],
            "coordinator": source["execution"]["coordinator"],
            "initial_host": "mac",
        },
        "episodes": episodes,
    }
    OUTPUT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
