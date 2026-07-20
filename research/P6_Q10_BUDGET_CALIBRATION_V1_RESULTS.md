# P6 Q10 Independent Primitive Budget Calibration Results

Status: closed. This is a consumed-development diagnostic, not an effectiveness or
leaderboard result.

## Result

All ten scheduled runs finished and passed artifact audit. The calibration produced
50 candidate proposals and 41 fresh executions. Three runs crossed the historical
five-proposal cap: seven proposals and five actual executions occurred after proposal
five. Full recovered four such executions across two runs; ablation recovered one in
one run. No run passed the internal verifier and none reached the Official evaluator.

The preregistered decision is therefore
`additional_environments_without_terminal_reach`: coupling cheap proposal rejection
to the expensive environment cap was mechanically harmful, but removing that coupling
was not sufficient to produce an evaluable deployment.

| Outcome | Combined | Full | Ablation |
| --- | ---: | ---: | ---: |
| Audit-valid runs | 10 | 5 | 5 |
| Candidate proposals | 50 | 29 | 21 |
| Fresh executions | 41 | 22 | 19 |
| Pre-environment rejects | 9 | 7 | 2 |
| Proposals after old cap | 7 | 6 | 1 |
| Executions after old cap | 5 | 4 | 1 |
| Internal passes | 0 | 0 | 0 |
| Official evaluator reaches | 0 | 0 | 0 |

The historical Q10 aggregate was also 50 proposals and 41 executions. That equality
does not negate the intervention: the new run redistributed execution opportunities
within trajectories, while stochastic early termination in other runs offset the
recovered slots in the aggregate. Historical differences are descriptive only.

## Error Attribution

The new trajectories expose two solver-boundary defects. One full run received three
model responses with empty final content and exhausted its consecutive policy-output
failure allowance; that run consumed 61,576 output tokens in total. A separate run
ended on one provider-side JSON decode exception. Seven otherwise normal environment-
budget terminations were recorded as `candidate-policy-exception`, which is a terminal
state-classification defect rather than a model failure.

These findings narrow the next revision:

1. Normalize online-budget exhaustion as an explicit budget terminal state outside
   the policy-exception channel.
2. Qualify a provider-portable structured-output contract and reasoning allocation so
   a bounded candidate request retains final-answer capacity.
3. Do not add operation-state machinery until those boundary defects are fixed and
   tested with synthetic counterexamples plus consumed-development replay.

The result artifact is
`experiments/validations/p6_q10_budget_calibration_v1_results.json`. No case-specific
rule, Official feedback, Canary identity, or Official-Test identity was used.
