#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


SIZE_MARKER = re.compile(
    r"[\[(](?P<value>[0-9]+(?:\.[0-9]+)?)\s*"
    r"(?P<unit>kB|MB|GB)[]\)]"
)
URL_HOST = re.compile(r"https?://(?P<host>[^/\s:'\"]+)")
DECIMAL_MULTIPLIER = {
    "kB": 1_000,
    "MB": 1_000_000,
    "GB": 1_000_000_000,
}


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events


def analyze_run_root(run_root: Path) -> dict[str, Any]:
    ledgers = sorted(run_root.glob("**/generation/budget_ledger.json"))
    episodes = sorted(run_root.glob("**/generation/episode.jsonl"))
    totals = {
        "candidates": 0,
        "commands": 0,
        "fresh_environments": 0,
        "model_requests": 0,
    }
    for path in ledgers:
        value = json.loads(path.read_text(encoding="utf-8"))
        usage = value.get("usage", {})
        totals["candidates"] += int(usage.get("candidates", 0))
        totals["commands"] += int(usage.get("commands", 0))
        totals["fresh_environments"] += int(usage.get("environments", 0))
        totals["model_requests"] += int(usage.get("requests_started", 0))

    matched_markers = 0
    logged_bytes = 0
    bytes_by_channel = {"pip": 0, "apt": 0, "other": 0}
    marker_count_by_channel = {"pip": 0, "apt": 0, "other": 0}
    network_host_mentions: dict[str, int] = {}
    cached_artifact_markers = 0
    action_outputs = 0
    truncated_outputs = 0
    for path in episodes:
        for event in _read_json_lines(path):
            if event.get("event_type") != "action_finished":
                continue
            observation = event.get("payload", {}).get("observation", {})
            output = "\n".join(
                str(observation.get(name, "")) for name in ("stdout", "stderr")
            )
            action_outputs += 1
            if "[truncated" in output:
                truncated_outputs += 1
            for host_match in URL_HOST.finditer(output):
                host = host_match.group("host").lower()
                network_host_mentions[host] = (
                    network_host_mentions.get(host, 0) + 1
                )
            for line in output.splitlines():
                normalized = line.lstrip()
                is_cached = "Using cached " in normalized
                if is_cached:
                    cached_artifact_markers += 1
                if normalized.startswith(("Downloading ", "Using cached ")):
                    channel = "pip"
                elif normalized.startswith(("Get:", "Fetched ")):
                    channel = "apt"
                else:
                    channel = "other"
                if is_cached:
                    continue
                for match in SIZE_MARKER.finditer(line):
                    size_bytes = round(
                        float(match.group("value"))
                        * DECIMAL_MULTIPLIER[match.group("unit")]
                    )
                    matched_markers += 1
                    logged_bytes += size_bytes
                    marker_count_by_channel[channel] += 1
                    bytes_by_channel[channel] += size_bytes

    return {
        "schema_version": "1.0.0",
        "run_root": str(run_root.resolve()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measurement": {
            "interpretation": (
                "Lower bound from package-size markers in persisted "
                "action-finished stdout/stderr."
            ),
            "excludes": [
                "bytes omitted by output truncation",
                "Docker image pulls",
                "official evaluator replay downloads",
                "repository acquisition",
                "package-manager metadata without size markers",
            ],
        },
        "episodes_with_ledgers": len(ledgers),
        "episodes_with_event_logs": len(episodes),
        "action_outputs": action_outputs,
        "truncated_action_outputs": truncated_outputs,
        "matched_download_size_markers": matched_markers,
        "logged_download_bytes_lower_bound": logged_bytes,
        "logged_download_decimal_gb_lower_bound": logged_bytes / 1_000_000_000,
        "download_channels_lower_bound": {
            channel: {
                "bytes": bytes_by_channel[channel],
                "decimal_gb": bytes_by_channel[channel] / 1_000_000_000,
                "marker_count": marker_count_by_channel[channel],
            }
            for channel in ("pip", "apt", "other")
        },
        "cached_artifact_markers": cached_artifact_markers,
        "network_host_mentions": dict(sorted(network_host_mentions.items())),
        **totals,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate a lower bound on dependency downloads."
    )
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.run_root.is_dir():
        raise ValueError(f"Run root is not a directory: {args.run_root}")
    result = analyze_run_root(args.run_root)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
