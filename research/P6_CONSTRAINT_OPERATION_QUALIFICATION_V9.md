# P6 Constraint Operation Qualification V9

Status: preregistered before Q9 selection, repository inspection, or execution.

## Purpose

Q8 exercised runtime-state v9 but closed on a primary invariant failure: an exact,
deterministic Python mismatch remained ordinary text and did not constrain the next
proposal. Q9 is the first outcome-blind development qualification of v10's narrow
runtime-diagnostic admission repair. It is not an effectiveness experiment and
cannot support a held-out or paper-level performance claim.

## Frozen Comparison

Both conditions use the same model, seed, repository and base-runtime observers,
fresh-container provider, candidate language, Python deployment verifier v5,
terminal official evaluator, and primitive limits.

- `envsolve-operation` admits eligible typed constraints, exposes operation plans,
  and applies the operation guard.
- `envsolve-operation-ablation` receives the same raw observations and executed-
  candidate feedback but has no typed admission, plan visibility, or guard.

Official evaluator output remains terminal-only. Neither condition receives Q8
trajectories, case memory, or repository-specific rules.

## Sample and Schedule

Five identities are selected from the untouched 156-case development pool by
ascending `SHA256(salt + NUL + case_id)`. Selection uses identity metadata only:
there is no repository inspection, package-manager stratification, runtime-trigger
prescreen, or replacement sampling. Pair order and within-pair method order are
fixed by independent salted hashes. Once materialized, all five identities are
permanently development-consumed.

## Primary Mechanism Test

V10 qualifies only if at least one scientifically eligible full run:

1. observes the exact subject-first diagnostic family `Current Python version
   (...) is not allowed by the project (...)` after a failed candidate;
2. has at least one later proposal opportunity;
3. records a hard runtime requirement/fact conflict from that evidence before the
   next proposal; and
4. projects the conflict to a `runtime_configure` obligation that the next executed
   full candidate covers.

The frozen PEP 440 semantic gate must reject malformed, incomplete, hedged, or
range-compatible near-misses without creating hard constraints. This boundary is
validated synthetically before selection and audited in real trajectories whenever
such text occurs. Image identity, fresh-replay preservation, failed-prefix
feasibility, and covering-candidate admission remain inherited safety invariants.

If no eligible full run triggers the new diagnostic family, Q9 is reported as
unexercised and v10 does not qualify; no replacement identity is selected. Any
triggered invariant violation is a shared mechanism defect and closes Q9 after the
current pair. Official paired outcome is secondary and is reported only when both
runs are eligible and Boolean.

## Eligibility and Infrastructure

Each run must pass artifact integrity, committed-source, schedule-identity,
primitive-budget, complete-heartbeat, and no-host-suspension checks. Failed or
censored episodes are never overwritten.

One audited same-identity retry is allowed only for a pre-episode acquisition
failure with zero model requests, candidates, environments, evaluator executions,
and method information. A terminal evaluator infrastructure failure may receive
one evaluator-only retry of the identical frozen script with zero new model calls.
All other infrastructure failures censor the pair without retry.

## Claim Boundary

Q9 can qualify only runtime-diagnostic admission v10 for continued development. It
cannot establish deployment effectiveness, tune the frozen budget, inspect Canary
or Official-Test cases, or add repository, package, tool, module, or version rules.
Poetry declaration and command-language coverage remain separate error hypotheses.
