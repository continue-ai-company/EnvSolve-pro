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

## Result

All 16 scheduled runs completed, passed artifact-integrity audit, and were
scientifically eligible. Both methods reached a Boolean Official result on four of
eight cases and passed two: `pyvespa` and `windpowerlib`. Both failed Official on
`molecule` and `scikit-rf`; both exhausted the online environment or command budget
before Official on the other four. There were no discordant paired outcomes and no
observed pass-rate advantage.

EnvSolve used 34 model requests, 31 fresh environments, 351,825 tokens, and 7,310.9
seconds of recorded episode wall time. The free-form baseline used 36 requests, 31
environments, 341,122 tokens, and 9,253.8 seconds. These small descriptive differences
are not treated as an efficiency result.

## Three-Layer Analysis

The observation layer admitted four unique verified negative-operation facts in
three EnvSolve runs. The constraint layer exposed a nonempty operation plan on 18 of
31 guarded later proposals, but Guard v4 rejected no proposal because no later
candidate repeated an exact failed command under the same context. The plans
contained 316 requirement presentations in total and up to 25 in one proposal;
several trajectories suggest that standard-library and repository-internal modules
can be projected as package-install obligations. The operation layer executed 31
candidates per method, with 11 command failures for EnvSolve and 12 for the baseline.

The preregistered operational gate is passed because EnvSolve produced four Boolean
Official outcomes, all shared invariants held, and no paired regression occurred.
Scientifically, the pilot shows feasibility but zero effectiveness separation. The
next experiment therefore keeps Algorithm v17 and Harness v32 unchanged and repeats
the paired comparison on a new outcome-blind sample before any large Spark batch or
algorithm revision.
