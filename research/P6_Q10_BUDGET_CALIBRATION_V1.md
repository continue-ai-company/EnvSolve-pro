# P6 Q10 Independent Primitive Budget Calibration

Status: closed after all ten preregistered runs. This is a consumed-development
diagnostic, not an effectiveness experiment. Results are reported in
`P6_Q10_BUDGET_CALIBRATION_V1_RESULTS.md`.

## Motivation

Q10 allowed five model-proposed candidates, five fresh environments, and five
verifier commands per run. These limits were implemented through one shared value.
Across ten runs, nine proposals were rejected before environment creation, so only
41 of 50 possible fresh environments were used. The model-request limit was 15, but
the candidate limit usually ended the episode after about five requests.

This creates a simpler explanation for terminal non-reach than a missing solver
mechanism: cheap validation or guard rejects may have consumed the same cap as
expensive fresh executions. The next experiment must eliminate this harness
confound before adding algorithmic structure.

## Intervention

Reuse the five already consumed Q10 development identities and the exact Q10 case
and method order. No case is selected or replaced. The solver, state, prompt,
operation planner, guard, verifier, model, seed, image, and Official protocol remain
unchanged.

Only the primitive vector changes:

| Primitive | Q10 | Calibration |
| --- | ---: | ---: |
| Candidate proposals | 5 | 15 |
| Fresh environments | 5 | 5 |
| Verifier commands | 5 | 5 |
| Model requests | 15 | 15 |

Token, wall-clock, per-command, and evaluator limits are unchanged. A candidate
proposal includes a parsed script rejected by candidate validation or the operation
guard. An environment is counted only after both gates accept the proposal.

## Outcomes

The primary question is whether any run uses a proposal after position five to
recover an otherwise unused fresh-environment slot and reach internal or Official
evaluation. All raw primitive usage and terminal stages are reported. Because the
historical Q10 run is stochastic and the identities are consumed, differences are
diagnostic rather than a causal performance estimate.

If a later proposal reaches terminal evaluation, the coupled cap was a material
harness bottleneck and no new solver mechanism is justified yet. If later proposals
consume the recovered environments but still fail, budget coupling mattered but was
not sufficient; only then may the new trajectories define one minimal generic
operation-state revision. No result from this experiment can support a leaderboard
or held-out claim.

## Closed Outcome

Three runs crossed the old proposal cap and recovered five fresh executions after
proposal five, but no run passed internally or reached the Official evaluator. The
registered decision branch is `additional_environments_without_terminal_reach`:
independent primitive budgets are retained, while further operation-state expansion
is deferred behind the newly observed output and terminal-state boundary defects.
