# EnvSolve-Pro M1 Evidence Correction

Date: 2026-09-10

This note corrects the first M1 closeout. The corrected machine-readable record is `experiments/analyses/envsolve_pro_m1_project_progress_closeout_20260910.json` version 1.1.

## Corrected Evidence

Raw postepisode EnvBench Official outcomes are:

| Arm | Pass | Nonpass | Missing |
|---|---:|---:|---:|
| `P` | 8 | 0 | 0 |
| `R0` | 6 | 2 | 0 |
| `R1` | 7 | 1 | 0 |

The first closeout incorrectly called position-22 R0 and R1 outcomes unknown. Both raw Official runs returned `exit_code=1, issues_count=0`. Position-23 R1 returned `exit_code=0, issues_count=0`; its raw pass remains counted even though its run audit is invalid.

Raw score, protocol validity, and causal attribution are separate. Position-22 P switched from conda to system Python plus venv and passed, while R0/R1 retained conda and encountered HTTP 000. Because arms ran sequentially, this may be a deployment-policy effect, temporal network variation, or both. It is not automatically an external censor and is not a leaderboard result.

## Claim Limits

The P/R1 token comparison is confounded. R1 always forked history and requested improvement; P and R0 skipped the model after a passing replay. The observed 58.5% input reduction therefore applies only against this always-call full-history policy. It does not reject adaptive full-history reuse.

P versus R0 is a tradeoff, not domination: P used 6.6% more total input and 12.6% more output, but 14.0% less uncached input. The independent sample size is four projects, not eight conditions.

M1 did not complete its original cumulative-progress test. State versions v1/v2/v3 exist, but no state-version by fixed-Q probe matrix was run. Three R1 v3 files also failed to persist D2 as the current condition. Current evidence is therefore a sequential reuse-and-repair screen.

## Scientific Decision

Do not promote the current P candidate. This means its mechanism gain is unestablished, not that explicit state is useless or R0 is optimal. The strongest alternative explanation is that the successful executable program already contains most reusable benefit, while position-22 differences came from the chosen deployment path and execution time.

The minimum next experiment should use only these four projects and existing artifacts: interleave repeated zero-model clean replays of each exact pre-update v2 program and exact post-update submitted program on the same fixed D2 condition. State is never updated. Report repeated success first and update cost separately. This directly asks whether repair leaves reusable progress and whether that progress can amortize its construction cost.

No supplemental run has been started. M2 and protected data remain unauthorized.
