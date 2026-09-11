# EnvSolve-Pro M1b Artifact Replay Stage Report

Date: 2026-09-11

## Question and scope

M1b asks whether the exact programs produced after D2 repair are reusable in fresh
environments, and whether P artifacts show an execution-reliability or execution-cost
advantage over simple controls. It uses four already-consumed Dev projects, three
predeclared interleaved repeats, no model calls, no state updates, and 51 physical clean
replays on Spark.

This is public-goal qualification, not a new EnvBench Official evaluation. It is an
artifact-level supplement. It cannot by itself establish Official success, a structured-
state mechanism, progressive optimality, or an empirical repair-cost break-even point.

## Fixed results

`A` is dependency acquisition failure, `T` is transport censoring, and `M` is target-
interpreter mismatch. Entries with shared programs use one physical measurement and are
not independent observations.

| Position | Final P | Final R0 | Final R1 | Important identity |
|---|---:|---:|---:|---|
| 10, ceph-ansible | 3 pass | 3 pass | 3 pass | P = R0 |
| 17, mpmath | 3 pass | 2 pass + 1 A | 2 pass + 1 A | distinct |
| 22, fontbakery | 3 pass | 2 pass + 1 A | 2 pass + 1 A | R0 = R1 |
| 23, reproject | 2 pass + 1 T | 3 pass | 2 pass + 1 A | distinct |

The arm-expanded totals are P: 11 pass + 1 transport censor; R0: 10 pass + 2
acquisition failures; R1: 9 pass + 3 acquisition failures. The independent unit remains
the four projects, not the 12 arm-project cells or 36 arm-expanded replays. Every final
arm-project artifact produced at least two clean-replay passes, so P has no exclusive
artifact-level success.

Across the 21 physical pre-update replays, there were 18 interpreter mismatches and three
acquisition failures. Across the 30 final physical replays, there were 25 passes, four
acquisition failures, and one transport censor. The pre-to-final contrast primarily shows
that the D2 program selects the required Python version; it is not evidence for a novel
memory mechanism.

## What the trajectories say

The observed reliability pattern has an actionable but non-causal explanation. At
position 17, P adds shell-level retries around pip; at position 22, P uses `venv` while
R0/R1 use a network-sensitive Conda creation step. At position 23, however, the more
selective R0 program is the only 3/3 artifact. Temporal network variation remains another
plausible explanation.

Therefore, M1b supports ordinary executable-program reuse and retains retry/environment-
path selection as an operation-layer research opportunity. It does not identify explicit
structured state as the source of the pattern. Historical R1 state files also failed to
persist D2 for three positions, so researcher-recovered submitted scripts are authoritative
here; artifact replay must remain separate from end-to-end method performance.

The position-23 P round-2 result is retained as a raw failure but adjudicated as transport-
censored: bootstrap exit 255, no program-level terminal error, and no corresponding remote
replay process when the stale SSH client was terminated. It was neither retried nor
replaced.

## Cost accounting

The shared historical D0 deployments cost 6,169,633 input tokens, 38,505 output tokens,
and 4,718.1 seconds of Agent generation. Their cost is shared across arms, not zero.

| D2 arm | Input | Uncached input | Output | Agent generation (s) |
|---|---:|---:|---:|---:|
| P | 3,881,243 | 303,003 | 26,059 | 3,699.7 |
| R0 | 2,040,710 | 238,854 | 16,234 | 2,882.9 |
| R1 | 6,704,631 | 451,063 | 14,583 | 2,261.6 |

M1b itself used zero model tokens and 9,356.8 replay wall seconds across 51 replays,
including the 1,566.5-second transport-censored observation. Pass-only median replay wall
time was 183.5 seconds for P, 177.4 for R0, and 150.8 for R1. These timings are descriptive:
programs install different dependency sets, and network transfer dominates several runs.

Four earlier invalid engineering attempts remain charged separately. Three have 1,330.7
known wall seconds in total; two interrupted Agent attempts have unavailable token usage.
No counterfactual future repair-token cost or empirical break-even count is imputed.

## Stage decision

Decision: retain the executable-artifact/replay hypothesis and the operation-level
reliability opportunity; do not promote current P or explicit persistent state into the
EnvSolve-Pro core.

The strongest simpler explanation is that a strong Agent wrote a usable target-specific
program and ordinary replay preserved it. P's extra D2 cost did not produce an exclusive
success, a clear execution-time advantage, or evidence that its state representation was
causal.

The next most informative core experiment is a matched test on fixed real Dev bad cases:
the same strong Agent, continuous session, prompts, tools, trigger, and resource reporting,
with the only treatment being complete-program clean replay feedback returned inside that
session. Terminal EnvBench Official success is primary. Structured state, checkpoints,
hypothesis search, and minimization remain separate later treatments. No such next batch is
started by this report.

## Evidence

- Schedule: `experiments/schedules/envsolve_pro_m1b_artifact_replay_v1.json`
- Aggregate: `experiments/analyses/envsolve_pro_m1b_artifact_replay_result_20260911.json`
- Transport adjudication: `experiments/validations/envsolve_pro_m1b_position23_transport_censor_20260911.json`
- Raw runs: `runs/envsolve-pro-m1b-artifact-replay-v1/`

