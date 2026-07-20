# P6 Output Contract Consumed Replay V1

Status: preregistered before execution. This is a one-run mechanism replay, not an
effectiveness experiment.

## Why This Run

The Q10 budget calibration contained one unique run that ended after three consecutive
model responses had empty final content. We reuse that already consumed identity and
method. No new case is selected, and no Official or Canary result is inspected.

## Frozen Intervention

Algorithm v13 and Harness v27 retain the v12 solver, constraint state, operation plan,
guard, verifier, prompt, and primitive execution limits. The only inference-boundary
settings are explicit `reasoning_effort=high` and `response_format=json_object`.
Normal online budget exhaustion now crosses a solver-owned terminal type rather than
the generic policy-exception channel. Reasoning content is never persisted.

## Decision

Practical output qualification requires at least five completed responses to become
parsed candidates with no policy-output failure, empty-final diagnostic, or request
error. If the environment or command budget ends the run, it must be recorded as
`episode-budget-exhausted` with the correct scope and never as
`candidate-policy-exception`.

An earlier internal Pass or infrastructure/provider failure leaves an unobserved
boundary unexercised; it does not permit a replacement. Any empty-final failure,
persisted reasoning content, or budget-as-policy-exception transition contradicts
v13 and blocks a new unseen qualification. Success or failure on this consumed run
cannot support a leaderboard or paper effectiveness claim.
