# EnvBench Finding Collector v1

Status: development-informed, recorded-case qualified, and not yet admitted on an
unseen batch.

The collector converts one fresh EnvBench replay into a structured verifier report.
The official goal decision remains exactly `exit_code == 0 && issues_count == 0`.
For successful bootstrap with missing-import issues, exact Pyright
`reportMissingImports` diagnostics are bound to revision-owned source text and
classified by the frozen P5 import-context analyzer. Every attributable official
missing import remains a goal-active module requirement; the P5 semantic disposition
is retained separately in provenance for repair risk and Robust-Pass analysis.
Unresolved source or malformed/count-mismatched diagnostics produce Unknown.

For bootstrap failure, the collector reuses the existing generic action-result
normalizer for Python-version, missing-capability, and missing-module pairs. Known
network signatures produce infrastructure Unknown. Other deterministic bootstrap
failures remain failed but unnormalizable, so the core loop blocks rather than
inventing a repair.

The collector does not map modules to packages, inspect repository identity when
choosing a repair, modify source, parse non-missing-import Pyright errors as
environment obligations, or change official scoring. Seven synthetic tests cover
identity, source provenance, diagnostic cardinality, guarded imports, generic
bootstrap evidence, and network censoring.
