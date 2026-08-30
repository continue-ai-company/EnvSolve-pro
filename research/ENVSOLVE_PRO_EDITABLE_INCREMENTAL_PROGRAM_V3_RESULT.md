# EnvSolve-Pro Editable Incremental Program V3 Result

## Decision

V3 passes its consumed-case mechanism qualification. It does not yet pass an effectiveness
or efficiency gate, and it is not promoted from one HARK result.

The eligible retry produced the complete causal sequence required by the design:

1. the active construction environment reached the complete public goal;
2. automatic clean replay falsified earlier `/data/project` program steps;
3. the same Agent session replaced and deleted earlier steps;
4. every successful edit immediately replayed the revised whole program;
5. later persistent steps produced a clean-replay Pass and Official Pass.

This is stronger evidence than tool invocation alone. The replay counterexample changed the
object being certified, not merely the Agent's explanation or its next compensating command.

## Infrastructure Censoring

The first attempt is excluded. At request 12 its first `effect=persist` command succeeded,
but missing runner wiring returned `incremental services are unavailable` and did not record
the step. The repair only constructed the replay service for `incremental-editable` and added
a runner-level regression assertion. Case, model, provider, seed, prompt, tool semantics,
evaluator, and analysis policy were unchanged for the fresh retry.

## Eligible Retry

HARK used 39 model responses and 47 provider attempts, including eight recovered provider
errors. The episode used 1,028,668 tokens, 37 shell calls, eight program-revision calls, and
eight clean replays. Seven replays failed before the final replay passed. End-to-end time was
2,862.0 seconds. Official EnvBench then passed with zero scoring issues.

The first construction-goal Pass occurred at request 30. Replay rejected the in-project
virtual environment and hard-coded `/data/project` assumptions. The first plan edit appeared
at request 34. Six edits succeeded overall: one replacement and five deletions. The resulting
program later reached clean replay Pass and Official Pass.

## New Failure Found

The numeric edit interface does not compose correctly when one model response contains
multiple edits. The Agent emitted six revisions against the program it had seen. Earlier
deletions shifted later indices before those later calls executed, causing two invalid-index
errors. The Agent recovered on the next request, but paid extra model, replay, and environment
work.

The narrow successor, if this defect is repaired before effect testing, is one atomic batch
edit interpreted against a pre-edit snapshot and followed by one replay. This is simpler than
adding stable step IDs, checkpoints, package rules, or controller gates.

## Endpoint Versus Deployment Quality

The final three-step program passes both clean replay and Official EnvBench, but it is not a
complete or faithful HARK deployment. It creates `/opt/harkenv` and never uses it, installs
dependencies into the default Conda environment, does not install the project, and requests
`numba>=0.61` despite the repository declaring `numba<0.60.0`.

Therefore this trajectory separates five outcomes that future experiments must report:
Official success, clean reproducibility, deployment completeness, declaration fidelity, and
path cost. Official Pass@1 remains primary for the leaderboard; the other axes explain what
kind of environment achieved it and whether resource comparisons are meaningful.

## Claim Boundary

This consumed episode qualifies editable program state and the replay-counterexample-to-edit
transition. It cannot estimate generalization, SOTA, success-rate gain, or resource gain.
The next effect test must use an outcome-blind fixed paired development batch and keep path
quality separate from Official Pass@1.

Machine-readable result:
`experiments/validations/envsolve_pro_v2_editable_incremental_program_v3_hark1_result.json`.
