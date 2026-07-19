# P6 Q10 Candidate Failure Analysis

Status: post-batch analysis of consumed development trajectories. No algorithm or
evaluator outcome is changed by this analysis.

## Stage Decomposition

The deterministic analyzer partitions all 50 proposed candidates by recorded state
transition. The partition is exhaustive and uses event schema, exit codes, and
structured verifier fields; it does not classify repository-specific log text.

| Terminal candidate stage | EnvSolve | Ablation | Total |
| --- | ---: | ---: | ---: |
| Candidate-command failure | 10 | 13 | 23 |
| Fixed internal-check failure | 5 | 5 | 10 |
| Structured obligations active | 5 | 3 | 8 |
| Shared candidate-validation reject | 2 | 4 | 6 |
| EnvSolve operation-guard reject | 3 | 0 | 3 |

Nine proposals were rejected before a fresh environment; 41 were executed. Of the
executed candidates, 23 (56.1%) failed in a candidate command, ten (24.4%) reached a
fixed internal check and failed there, and eight (19.5%) completed fixed checks but
retained structured obligations. Forty candidates had a later proposal opportunity.

Full EnvSolve produced more structured-verifier outcomes than the ablation (5 vs.
3) and fewer candidate-command failures (10 vs. 13), but both conditions exhausted
all five candidate budgets on every case. These are developmental mechanism counts,
not an effectiveness estimate.

## Dominant Contradiction

The immediate bottleneck is pre-evaluator calibration. Candidate-command failures
occur in every selected repository and span runtime compatibility, unavailable
package or source mappings, native-build prerequisites, and dependency acquisition.
This suggests that textual execution feedback is richer than the current typed
feasibility state. However, ten additional candidates were blocked by fixed checks,
and eight were blocked by the structured approximation of the official objective.
Without terminal calibration, relaxing either verifier layer could merely hide real
Official failures.

One trajectory demonstrates the intended stateful behavior but also its latency. A
runtime mismatch became a hard runtime operation obligation; an ineffective runtime
mutation was rejected; a later candidate configured Python 3.11 and reduced runtime
unresolved modules to zero. This occurred only on candidate five, leaving no repair
slot for the remaining static obligation. The result supports stateful constraint
propagation while showing that operation feasibility and search efficiency remain
insufficient under the frozen budget.

## Next Falsifiable Test

Before changing solver or verifier scope, run a no-model post-episode calibration on
exactly one deterministic script per Q10 run: the last candidate that received a
`verification_recorded` event. Selection uses only frozen trajectory structure and
is fixed before any new Official result. Each script is replayed once through the
unchanged EnvBench evaluator in a fresh environment.

The calibration distinguishes two hypotheses:

1. If terminal evaluation fails on the same obligations, action feasibility and
   candidate efficiency are the main target; internal scope should remain frozen.
2. If terminal evaluation passes or bypasses a repeated internal blocker, the
   internal verifier is miscalibrated; a generic synthetic counterexample must define
   the smallest scope correction before any new solver feature.

The calibration is development-only, contributes no leaderboard estimate, makes no
new model calls, and cannot rerun or replace a Q10 generation trajectory.
