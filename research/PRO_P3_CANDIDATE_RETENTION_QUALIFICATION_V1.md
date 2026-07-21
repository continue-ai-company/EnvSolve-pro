# EnvSolve-pro P3 Candidate-Retention Qualification v1

## Purpose

Qualify one minimal P2-derived mechanism before spending untouched cases. Internal
verification is partial evidence, not a terminal oracle. EnvSolve now distinguishes
certified candidates from complete but uncertified admissible candidates and retains the
best admissible one when search ends.

## Frozen Diagnostic Cohort

Replay `uk-polling-stations`, `spelling`, and `supervision` under paired retention and
no-retention conditions. These cases were selected and observed in P2, so they can test
implementation behavior but never support an effectiveness claim. Both conditions use the
same commit, model, seed, five-candidate limit, open-program interface, terminal-only
evaluator, and Python verifier v8. The only switch is whether the best admissible candidate
is emitted at candidate-budget exhaustion.

## Prediction And Gate

Frozen P2 emitted no script for all three cases despite at least one complete zero-exit
candidate per case. The primary prediction is terminal reach in at least two of three new
episodes, and at least one more terminally reached case than no retention. A retained
candidate must be labeled `uncertified`, keep the internal goal `blocked`, carry a typed
assessment, and pass repository integrity. Official Pass is not predicted.

Failure of this gate rejects or revises candidate retention before any new Dev ablation.
Passing it permits a preregistered unseen paired experiment; it does not qualify runtime
closure or any effectiveness claim.
