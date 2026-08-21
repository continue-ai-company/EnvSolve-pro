# EnvSolve-Pro V2 Screened Bad-6 Protocol

Status: preregistered before new source acquisition or model execution, 2026-08-21

## Question

When an independent capable baseline has already failed Official evaluation, does adding
target-state counterexample replay to a matched DeepSeek free Agent improve Official
Pass@1 or produce genuine replay-conditioned repairs?

This is a failure-enriched development stress test. It is designed to avoid another
ceiling-heavy random batch, not to estimate the overall EnvBench success rate.

## Selection

The independent screen is the pre-existing Codex CLI `gpt-5.5` bad-case census. It is used
only to identify repositories with historical Official failures; it is not a control arm.

Start from all 11 confirmed Official failures in the census casebook. Exclude three cases
whose causes were recorded as unresolved package-index behavior. Exclude two additional
repositories already executed under F+C_s+R. Include all six remaining cases:

| Pair | Repository | Historical failure stratum |
|---|---|---|
| 1 | Quantum-Accelerators/quacc | Operation: native/system dependency |
| 2 | ajenti/ajenti | Constraint: build isolation |
| 3 | claritychallenge/clarity | Observation/Operation: checkout ownership |
| 4 | andrew-codechimp/HA-Battery-Notes | Constraint: transitive build dependency |
| 5 | econ-ark/hark | Observation/Operation: checkout ownership |
| 6 | bradenm/micropy-cli | Constraint/Operation: unrealized project import |

No case is ranked by expected treatment behavior or repairability. These historical
failures informed development diagnosis, so the batch remains development evidence rather
than held-out confirmation.

## Comparison

- **A-F:** one continuous DeepSeek session with ordinary execution feedback.
- **B-FCsR:** the same interface plus repeatedly callable whole-program replay from the
  target initial state, with failures returned to the same active session.

Both arms use `deepseek/deepseek-v4-flash-0731`, DeepInfra through OpenRouter, Spark Linux
aarch64, the same image and Official evaluator, private construction caches, empty target
replay caches, and broad success-first limits. Pair seeds are matched. Order is
counterbalanced: three pairs run A first and three run B first. Two sequential lanes may
run concurrently.

## Outcomes

Official Pass@1 is primary. Report the complete paired table and exact McNemar result.
For B, report candidate formation, ordered replay outcomes, program changes after failure,
repair type, and final replay/Official agreement. Every terminal failure receives an
evidence-linked Observation, Constraint, or Operation label; infrastructure is separate.

Resources are descriptive and never hard success thresholds. Report paired differences
and medians alongside totals. Deployment completeness remains a separate axis.

## Interpretation Boundary

A first-replay B-only pass may be treatment-level evidence but does not isolate replay
repair from stochastic search. A replay-conditioned repair requires a failed target-state
replay, a materially changed program in the same session, and later replay and Official
success. Network robustness and compatibility repair are distinct transitions.

The method and taxonomy remain unchanged during the batch. No package, network, checkpoint,
cross-case memory, hard operation rule, or new safety gate may be added from an observed
episode. Results apply only to this screened development stratum.

Machine-readable records:

- `experiments/validations/envsolve_pro_v2_target_state_replay_screened_bad6_v1_selection.json`
- `experiments/validations/envsolve_pro_v2_target_state_replay_screened_bad6_v1_preregistration.json`
- `experiments/schedules/envsolve_pro_v2_target_state_replay_screened_bad6_v1.json`
