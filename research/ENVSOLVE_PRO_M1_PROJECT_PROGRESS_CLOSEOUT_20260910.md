# EnvSolve-Pro M1 Project-Progress Screen

Date: 2026-09-10

Machine-readable evidence: `experiments/analyses/envsolve_pro_m1_project_progress_closeout_20260910.json` version 1.1. The concise correction note is `research/ENVSOLVE_PRO_M1_EVIDENCE_CORRECTION_20260910.md`.

## Question and Arms

M1 screened whether a small explicit progress record (`P`) improves later deployment over:

1. `R0`: replay the latest successful program and call a new Agent only after failure.
2. `R1`: fork the completed Agent session and always request another improvement.
3. `P`: replay first; after failure, give a new Agent the program plus a compact record of conditions, transitions, and risks.

The fixed sample contains four consumed/Dev projects. Each project has a same-Python deployment (`D1`) and one predeclared adjacent supported Python version (`D2`). All arms used `gpt-5.6-sol`, `xhigh`, the same public goal, Spark target execution, and postepisode Official evaluation. No protected data or replacement project was used.

## Raw Official Results

| Arm | Pass | Nonpass | Missing |
|---|---:|---:|---:|
| `P` | 8 | 0 | 0 |
| `R0` | 6 | 2 | 0 |
| `R1` | 7 | 1 | 0 |

Raw Official scores are not rewritten by later audits. R0 position-10 D1, R0 position-22 D2, and R1 position-22 D2 are raw nonpasses. R1 position-23 D2 is a raw pass despite its invalid run audit.

For mechanism attribution, all eight P and R0 cells are audit-valid; six of eight R1 cells are audit-valid. Position-22 P used system Python plus venv, whereas R0/R1 retained conda and hit HTTP 000. Sequential timing and deployment-policy choice are inseparable here, so P's better raw table is not yet a causal reliability result.

## Model Usage

| Arm | Input | Cached | Uncached | Output |
|---|---:|---:|---:|---:|
| `P` | 3,881,243 | 3,578,240 | 303,003 | 26,059 |
| `R0` | 3,639,529 | 3,287,168 | 352,361 | 23,136 |
| `R1` | 9,355,543 | 8,576,640 | 778,903 | 24,387 |

The independent unit is the project (`n=4`). P used 6.6% more total input and 12.6% more output than R0, but 14.0% less uncached input. This is a tradeoff, not domination. P used 58.5% less input than R1, but R1 also changed the trigger policy: it always invoked the model after replay, while P/R0 could skip. The result only argues against the tested always-call policy.

Per-project token records and invalid engineering attempts are retained in the machine-readable record. Two interrupted false-positive Agent invocations consumed 317.2 and 717.8 observed wall seconds and 6 and 12 recorded container commands; their token usage is unavailable and is not silently treated as zero.

## Missing Test

This is a sequential reuse-and-repair screen, not the completed cumulative-progress experiment originally planned. Four v1 seeds and 24 v2/v3 state files exist, but no D0/D1/D2 state-version comparison was run on the same fixed condition Q without updates. In addition, three R1 v3 files failed to persist D2 as their current condition.

Consequently, the study does not establish whether a repaired new version reduces later re-exploration enough to justify first-deployment, update, and validation costs. It also does not establish that explicit state is useless or that R0 is optimal.

## Decision

**Do not promote the current P candidate. Keep M1 open for stage review.** R0 remains a strong simple comparator. The R1 result rejects only always-call full-history improvement as the default.

The minimum proposed supplement uses the same four projects and existing submitted programs. On each fixed D2 condition, interleave repeated zero-model clean replays of the exact pre-update v2 and post-update programs for P and R0, without state updates. Primary evidence is repeated replay success; prior update tokens and time are reported separately to test amortization. No supplemental run, M2 expansion, or protected evaluation has started.
