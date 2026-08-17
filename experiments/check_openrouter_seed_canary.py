from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any


PROMPT = (
    "You are a sampling-control canary. Return exactly one compact JSON object "
    "with one key named items. Its value must be an array of six distinct, "
    "uncommon English nouns. Do not add markdown or explanation."
)
MODEL = "deepseek/deepseek-v4-flash-0731"
TRIALS = (
    ("same-seed-1", "same-seed", 271828),
    ("same-seed-2", "same-seed", 271828),
    ("same-seed-3", "same-seed", 271828),
    ("different-seed-1", "different-seed", 314159),
    ("different-seed-2", "different-seed", 161803),
    ("different-seed-3", "different-seed", 141421),
)


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        result = value.model_dump(mode="json")
        if isinstance(result, dict):
            return result
    if isinstance(value, dict):
        return value
    return {}


def _semantic_payload(response: Any) -> dict[str, Any]:
    choice = response.choices[0]
    message = _dump(choice.message)
    return {
        "content": message.get("content"),
        "reasoning": message.get("reasoning"),
        "refusal": message.get("refusal"),
        "tool_calls": message.get("tool_calls"),
        "finish_reason": getattr(choice, "finish_reason", None),
    }


def _sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _request(client: Any, seed: int) -> Any:
    options = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 256,
        "seed": seed,
        "extra_body": {
            "reasoning": {"effort": "xhigh"},
            "provider": {
                "order": ["deepinfra"],
                "require_parameters": True,
                "allow_fallbacks": False,
            },
        },
    }
    last_error: Exception | None = None
    for attempt, delay in enumerate((0, 2, 10), start=1):
        if delay:
            time.sleep(delay)
        try:
            return client.chat.completions.create(**options), attempt
        except Exception as exc:  # The result records terminal canary failures.
            last_error = exc
    raise RuntimeError(f"request failed after 3 attempts: {type(last_error).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set")

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=180,
        max_retries=0,
    )
    records: list[dict[str, Any]] = []
    for trial_id, condition, seed in TRIALS:
        response, attempts = _request(client, seed)
        response_dump = _dump(response)
        semantic = _semantic_payload(response)
        records.append(
            {
                "trial_id": trial_id,
                "condition": condition,
                "requested_seed": seed,
                "attempts": attempts,
                "response_id": response_dump.get("id"),
                "served_model": response_dump.get("model"),
                "provider": response_dump.get("provider"),
                "usage": response_dump.get("usage"),
                "semantic_payload": semantic,
                "semantic_sha256": _sha256(semantic),
            }
        )

    same = {
        item["semantic_sha256"]
        for item in records
        if item["condition"] == "same-seed"
    }
    different = {
        item["semantic_sha256"]
        for item in records
        if item["condition"] == "different-seed"
    }
    result = {
        "schema": "envsolve-pro-v2-sampling-seed-canary-result-v1",
        "study_id": "envsolve-pro-v2-openrouter-sampling-seed-canary",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "request": {
            "model": MODEL,
            "provider_order": ["deepinfra"],
            "allow_fallbacks": False,
            "require_parameters": True,
            "tools": "omitted",
            "max_tokens": 256,
            "reasoning_effort": "xhigh",
            "temperature": "provider default",
            "prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
        },
        "summary": {
            "completed_requests": len(records),
            "requested_seed_bound_records": sum(
                isinstance(item["requested_seed"], int) for item in records
            ),
            "same_seed_unique_semantic_fingerprints": len(same),
            "same_seed_repeatability_observed": len(same) == 1,
            "different_seed_unique_semantic_fingerprints": len(different),
            "different_seed_variation_observed": len(different) > 1,
        },
        "trials": records,
        "claim_boundary": (
            "This canary measures parameter acceptance and observed single-turn "
            "repeatability only. It does not guarantee deterministic multi-turn "
            "agent trajectories or replace independent experimental repetitions."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
