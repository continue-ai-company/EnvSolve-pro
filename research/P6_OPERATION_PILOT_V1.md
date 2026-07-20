# P6 Operation Pilot V1

## Purpose

Before spending a larger Spark budget, this pilot asks whether frozen EnvSolve v17
can naturally reach the Official evaluator on at least two of eight fresh development cases
and whether it shows an unexplained paired regression against the same-backbone
free-form operation baseline.

The eight identities are selected only after the Mac host and provider gates pass,
using salted metadata-only hashing from the 141 identities untouched after Q11. All
eight become consumed regardless of outcome. No repository is inspected before
selection, and the pilot cannot support a paper effectiveness claim.

## Contrast

The two methods share model, seed, raw execution feedback, repository and runtime
observation, fresh environments, verifier v7, Typed Replay IR v8, primitive limits,
and post-episode-only Official access. EnvSolve receives persistent typed constraints,
the grounded negative-operation view, and Guard v4. The baseline receives raw history
but no operation plan, negative-operation view, or guard.

## Decision Gate

Bulk execution may proceed only if at least two scientifically eligible EnvSolve runs
reach Boolean Official outcomes, no shared invariant fails, and there is no
unexplained case where the baseline reaches or passes Official while EnvSolve does
not. Fewer than two EnvSolve terminal reaches stop the bulk batch for failure analysis. An
EnvSolve-only success is encouraging development evidence, not a result claim.

Any algorithm change after the pilot consumes all eight identities and requires a new
freeze and a new preregistered bulk batch from the 133 remaining identities.

The machine-readable protocol is
`experiments/validations/p6_operation_pilot_v1_preregistration.json`.
