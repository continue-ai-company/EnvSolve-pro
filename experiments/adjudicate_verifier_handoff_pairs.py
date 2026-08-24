#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.verifier_handoff_screen import adjudicate_paired_schedule


def _mapping(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        source, separator, target = value.partition("=")
        if not separator or not source or not target:
            raise ValueError(f"{label} must have RUN_ID=VALUE form")
        if source in result:
            raise ValueError(f"Duplicate {label} run: {source}")
        result[source] = target
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adjudicate verifier-handoff pairs on Official and protocol axes."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--official-retry", action="append", default=[], metavar="SOURCE=RETRY"
    )
    parser.add_argument(
        "--protocol-invalid", action="append", default=[], metavar="RUN_ID=REASON"
    )
    args = parser.parse_args()

    result = adjudicate_paired_schedule(
        args.schedule,
        args.runs_root,
        official_retries=_mapping(args.official_retry, "Official retry"),
        protocol_invalid=_mapping(args.protocol_invalid, "protocol-invalid reason"),
    )
    write_json(args.output, result)
    official = result["official_paired"]
    protocol = result["protocol_compliant_paired"]
    print(
        f"pairs={result['counts']['pairs']} "
        f"official_control={official['control_passes']} "
        f"official_treatment={official['treatment_passes']} "
        f"protocol_control={protocol['control_passes']} "
        f"protocol_treatment={protocol['treatment_passes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
