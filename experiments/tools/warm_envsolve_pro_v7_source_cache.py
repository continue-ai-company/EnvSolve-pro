from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from envsolve_harness.core.io import read_jsonl, write_json
from envsolve_harness.core.models import Case
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    cases = [Case.from_dict(item) for item in read_jsonl(args.case_file)]
    args.work_root.mkdir(parents=True, exist_ok=True)
    receipts = []
    failures = []
    for position, case in enumerate(cases, start=1):
        destination = args.work_root / f"case-{position:02d}"
        try:
            receipt = ExactRevisionSourceCache(args.cache_root, args.timeout).acquire(
                repository=case.repository,
                revision=case.revision,
                destination=destination,
            )
            receipts.append(receipt)
        except (OSError, RuntimeError) as exc:
            failures.append(
                {
                    "case_id": case.case_id,
                    "repository": case.repository,
                    "revision": case.revision,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        finally:
            if destination.exists():
                shutil.rmtree(destination)
    write_json(
        args.work_root / "receipts.json",
        {
            "policy": "prewarmed-immutable-cache-independent-no-hardlinks-checkout",
            "case_count": len(cases),
            "receipts": receipts,
            "failures": failures,
        },
    )
    return 0 if len(receipts) + len(failures) == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
