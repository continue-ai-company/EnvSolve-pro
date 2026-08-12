# EnvSolve-Pro Dev Bad-Case Census v1 Protocol

Date: 2026-08-09

## Purpose

Before designing the next EnvSolve-Pro mechanism, measure where the frozen strong-Agent
control actually fails. The census must produce the complete Dev bad-case list and an
A-only failure taxonomy before any B/C treatment is run or any core batch is selected.

This is a development study. It supports error analysis and algorithm design, not a
held-out or leaderboard claim.

## Dataset Boundary

The EnvBench paper evaluates the complete `python_baseline_failure` benchmark of 329
Python repositories. It does not use the EnvSolve-Pro development partition below as
its paper protocol. The pinned upstream dataset revision also contains a 100-case
`python_baseline_failure_test` subset; EnvSolve-Pro protects that subset, but the
paper's reported main results use all 329 cases.

EnvSolve-Pro partitions the 329 Python cases for research hygiene:

- Dev census: 209 cases, the union of frozen Dev-5 and Train-Rest-204.
- Canary: 20 cases, untouched during core algorithm design.
- Protected test: the upstream 100-case test subset, untouched until confirmation.

The three sets are disjoint. This partition is ours, not Repo2Run's and not the
EnvBench paper's main evaluation split.

## Frozen Control

Condition A is `codex-cli-qualified-boundary-v5`: one continuous Codex session using
`gpt-5.5` with high reasoning effort, one persistent construction environment, and no
clean replay visible to the Agent. Post-session qualification and Official evaluator
feedback are withheld from the Agent.

Four artifact-valid outcomes produced by this exact identity are reused once. The
remaining 205 cases run A only, in two deterministic non-overlapping Mac lanes. A
change to the model, boundary, goal, evaluator, or result semantics starts a new census
version.

This census executes the official multi-architecture image on `linux/arm64`. It measures
the frozen Agent on that deployment platform, not architecture-neutral difficulty.
Published results with unreported architecture are not directly comparable; a SOTA claim
requires rerunning all compared methods on one common architecture.

## Outcomes And Classification

Every case receives exactly one terminal outcome: Official Pass, Official Fail, Agent
Noncompletion, Qualification Fail, or Infrastructure Unknown. Infrastructure Unknown
is censored and may receive one semantics-identical retry; it is not an algorithmic
failure. A valid Agent Noncompletion remains a Pass@1 failure and cannot be replaced by
a later diagnostic run.

Bad cases are classified from A-only trajectory evidence into Observation,
Constraint, Operation, Cross-layer, or Unresolved failures. Each non-unresolved label
requires evidence anchors. B/C outcomes, historical treatment repairability, expected
ease of repair, Canary content, and protected-test content are forbidden inputs.

The taxonomy cannot grow during the census. A novel mechanism is recorded as
Unresolved and may motivate a separately frozen taxonomy v2 after this study closes.

All bad cases receive a primary annotation. A deterministic subset of size
`min(N, max(30, ceil(0.25N)))` receives a second independent annotation using the same
A-only evidence, with the primary label, aggregate frequencies, and all B/C data hidden.
Original disagreements are preserved and agreement is reported before adjudication. The
separate reliability preregistration fixes sampling, blinding, and metrics.

## Fixed Core Batch

Only after all 209 outcomes and all bad-case classifications are published, select up
to 12 bad cases. Stratify by terminal outcome, primary layer, and primary subtype;
order strata by descending census frequency and then lexical identifier; order cases
inside each stratum by the frozen salted SHA256 rank; then sample round-robin across
strata.

All unselected bad cases become the frozen validation pool. Their outcomes may not be
used to design the first core algorithm. B/C execution and mechanism changes begin only
after both identities are frozen.

## Primary Artifacts

- Preregistration: `experiments/validations/pro_dev_bad_case_census_v1_preregistration.json`
- Annotation reliability: `experiments/validations/pro_dev_bad_case_census_v1_annotation_reliability_preregistration.json`
- Platform interpretation: `experiments/validations/pro_dev_bad_case_census_v1_platform_interpretation_amendment.json`
- Universe: `experiments/cases/dev_pro_bad_case_census_v1_209.jsonl`
- Taxonomy: `experiments/protocols/envsolve_pro_dev_bad_case_taxonomy_v1.json`
- Pending cases: `experiments/cases/dev_pro_bad_case_census_v1_pending205.jsonl`
- Lane schedules: `experiments/schedules/pro_dev_bad_case_census_v1_mac_lane1.json` and
  `experiments/schedules/pro_dev_bad_case_census_v1_mac_lane2.json`
