# EnvSolve-Pro V2 Target-State Replay Qualification V1

Status: complete development qualification with a disclosed forensic correction

## Question

Does repeatedly executing the complete deployment program from the target initial state,
and returning failures to the same active Agent session, merit evaluation on a larger
development batch?

This four-pair study was fixed from a pre-existing randomized Dev16 schedule before source
acquisition or model execution. It is a mechanism qualification, not held-out evidence or
an estimate of leaderboard performance.

## Result

| Pair | Repository | A: free feedback | B: free feedback + target replay | Mechanism evidence |
|---|---|---:|---:|---|
| 1 | probatus | Fail | Pass | B passed its first replay; no feedback repair |
| 2 | pika | Pass | Pass | B passed its first replay |
| 3 | importlib_metadata | Pass | Pass | B replayed Fail, Fail, Pass and repaired the complete program |
| 4 | cellrank | Fail | Fail | Replacement B exhausted 120 requests before candidate formation |

The primary fixed-replacement result is A `2/4` versus B `3/4`: two both-pass pairs, one
B-only pair, no A-only pair, and one both-fail pair. Exact McNemar is `p=1.0` because
there is only one discordant pair. Excluding the operator-affected cellrank pair gives A
`2/3` versus B `3/3`. Neither table supports an effectiveness estimate.

## What The Mechanism Did

Three eligible B episodes formed candidates and ran five completed replays. Final replay
and Official outcomes agreed in all three. Probatus and pika passed on their first replay.
Importlib_metadata is the causal mechanism example: replay first exposed unavailable
setuptools in build isolation and a missing required `build_output` directory; the second
program passed the executable goal but still omitted that directory; the third program
fixed both and passed Official.

Cellrank exposes the complementary failure: replay cannot help before a candidate exists.
The replacement B session spent 120 model requests and 4.48M tokens without submission.
The algorithm therefore needs broader measurement before any claim that replay improves
success in expectation.

## Causal Reading

Probatus is a treatment-level B-only pass, but B independently selected a different virtual
environment path and passed its first replay. It may reflect ordinary stochastic trajectory
variation rather than feedback-conditioned repair. Importlib_metadata directly supports the
narrow claim that a target-state counterexample can change and repair a complete program in
the same session.

Cellrank A masked a failed PETSc/SLEPc install and consequently missed `petsc4py` and
`slepc4py` in Official evaluation. This is an Operation-layer state-to-program failure.
Replacement B failed earlier at candidate formation, also in the Operation layer.

## Resources

Across all four primary pairs, A used 200 model requests, 5.40M tokens, and 6,124 seconds
of generation; B used 209 requests, 5.95M tokens, and 10,685 seconds. There is no
unconditional efficiency gain. On the two joint-success repositories only, B used fewer
requests, tokens, commands, and generation time, but that selected slice is descriptive.

Token use remains an outcome, never a success threshold. Success takes priority under the
shared broad safety limits.

## Forensic Correction

The original cellrank B episode was mistakenly stopped after a stale lifecycle status and
a CLOSE-WAIT socket were interpreted as a provider hang. Trajectory and container evidence
later showed that request 58 had already returned a complete `submit_and_replay` call and
the first clean replay was still executing. The original is researcher-interrupted and is
excluded, not labeled infrastructure failure. Its replacement was specified before model
execution with the same case, arm, model, provider, seed, image, prompt, evaluator, and
limits; every summary must also report the sensitivity analysis excluding the entire pair.

## Decision

The preregistered promotion rule is met narrowly: B did not lower paired success, produced
one B-only pass, and produced one genuine Fail-Fail-Pass repair. The treatment advances
unchanged to a larger fixed development batch. This decision qualifies mechanism scaling;
it does not establish an EnvSolve-Pro effect, efficiency gain, held-out generalization, or
SOTA result.

Machine-readable evidence is in
`experiments/validations/envsolve_pro_v2_target_state_replay_qualification_v1_result.json`.
