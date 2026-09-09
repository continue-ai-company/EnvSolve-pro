# EnvSolve-Pro M1 Project-Progress Closeout

Date: 2026-09-10

Machine-readable evidence: `experiments/analyses/envsolve_pro_m1_project_progress_closeout_20260910.json`

## Question

M1 tested whether a small, explicit record of executable project progress (`P`) improves on two simpler ways to reuse prior work:

1. `R0`: replay the latest successful bootstrap program and call a new strong Agent only after a real program failure.
2. `R1`: fork the complete prior strong-Agent session and always ask it to improve the deployment.
3. `P`: replay first, then give a new Agent the successful program, verified condition, observed transitions, and unresolved risks after a real failure.

The fixed study used four consumed/Dev projects, a fresh same-Python condition (`D1`), and one predeclared repository-supported adjacent Python version (`D2`). All arms used `gpt-5.6-sol` at `xhigh`, the same public goal, Spark execution environment, and postepisode Official evaluation. Terminal success and new model usage were co-primary.

## Result

| Arm | Observed Official evidence | Input tokens | Cached input | Uncached input | Output tokens |
|---|---:|---:|---:|---:|---:|
| `P` | 8 Pass | 3,881,243 | 3,578,240 | 303,003 | 26,059 |
| `R0` | 6 Pass, 1 external failure, 1 unknown | 3,639,529 | 3,287,168 | 352,361 | 23,136 |
| `R1` | 7 Pass, 1 unknown; 2 trials censored from the primary comparison | 9,355,543 | 8,576,640 | 778,903 | 24,387 |

`P` preserved Official success in all eight cells. This is not evidence of higher success than the controls: all algorithm-adjudicated `R0` and `R1` outcomes also passed, while their remaining cells were censored by external acquisition or invalid qualification evidence rather than deployment-logic failures.

`P` reduced total input by 58.5% relative to `R1`, but used 6.6% more total input and 12.6% more output than `R0`. On the controlled D2 changes alone, `P` used 90.2% more input than `R0`. It therefore fails the preregistered rule requiring preserved success and lower new inference against both controls.

Per-trial execution, qualification, and retry times remain in the position records. We do not make an aggregate causal wall-time claim because the sequential arms encountered unequal package-cache, resolver, download, and censoring conditions.

## Decision

**Do not promote explicit project state into the EnvSolve-Pro core.** Keep it as an ablation and negative result. `R0` is the strongest surviving minimal policy: cleanly replay a successful executable program and invoke a strong Agent only after observed program failure. `R1` is rejected as the default because complete history increased input by 2.57x over `R0` without an adjudicated success gain.

M1 does not authorize M2 and makes no core algorithm change before review.

## What Changed Our Understanding

First, reusable programs matter, but they are not stable environment specifications. In `reproject` D1, the nominally same retained program passed for `P` and `R1`, then later failed for `R0` when dependency backtracking selected an obsolete Shapely build. The repair cost is real, but it cannot be attributed to the arm because the runs occurred at different times.

Second, a strong Agent with full history is not automatically efficient. It spent model inference after passing preflights and often returned byte-identical or semantically equivalent programs. More memory did not produce better terminal outcomes in this study.

Third, Official-passing paths differed in retries, environment mechanism, constraints, and installed extras. We retain completeness and robustness as annotations, but EnvBench Official remains the terminal authority. These annotations cannot be substituted for leaderboard success.

## Stage Review

The next method should not be another larger state schema. The evidence instead points to a narrower question: on fixed real Official bad cases, can failure-triggered clean replay plus a strong Agent convert failures to Official Pass more reliably or with less unnecessary exploration than the strongest external baselines?

Before opening M2, decide whether to test that question directly and whether resolver/acquisition drift requires repeated execution as an experimental condition. No additional constraints, hashes, contracts, or gates are justified by M1.
