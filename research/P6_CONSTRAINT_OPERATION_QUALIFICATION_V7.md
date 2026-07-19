# P6 Constraint Operation Qualification V7

Status: preregistered before Q7 selection, repository inspection, or execution.

## Purpose

Q6 showed that typed reactive repair was insufficient: the operation plan was empty
before proposal 1, and no pair passed officially. Q7 is the first outcome-blind
development batch for conservative pre-action declaration admission. It tests the
frozen EnvSolve v8 mechanism, not a case-specific repair and not a paper-level
effectiveness claim.

## Frozen comparison

Both conditions use the same model, seed, repository profile, bounded declaration
observer, fresh-container provider, candidate language, Python deployment verifier
v4, terminal evaluator, and primitive limits.

- `envsolve-operation` admits unconditional standard package declarations before
  proposal 1, exposes the typed operation plan, and applies the operation guard.
- `envsolve-operation-ablation` runs the same declaration observer but admits no
  typed initial constraints, hides the operation plan, and has no operation guard.

Both conditions receive the same verifier evidence after an executed candidate.
Official evaluator output remains terminal-only and cannot enter online state.

## Sample and schedule

Five identities are selected from the untouched 166-case development pool by
ascending `SHA256(salt + NUL + case_id)`. Selection uses metadata only. Pair order
and within-pair method order are determined by separate salted hashes. All five
selected identities become permanently development-consumed once materialized,
regardless of Pass, Fail, Unknown, interruption, or infrastructure censoring.

## Outcomes

The primary descriptive outcome is the paired official Boolean result: full-only
Pass, ablation-only Pass, both Pass, or both Fail. A pair is included in this table
only when both runs are scientifically eligible and both official results are
Boolean. All other pairs are reported as censored with their fixed reason.

Mechanism outcomes are computed from immutable online artifacts:

- admitted initial evidence and constraint counts;
- proposal-1 operation requirement count and subjects;
- whether proposal 1 contains a permitted package mutation;
- candidates, environments, commands, model requests, tokens, and wall time;
- repeated candidate or repeated mutation rate;
- internal-Pass and official-evaluator reach rate;
- package requirements closed by positive fresh metadata observations.

No threshold is chosen after observing Q7. With five pairs, results are calibration
evidence and error analysis, not a powered estimate.

## Eligibility and adaptation

Each run must pass artifact integrity, committed-source, schedule-identity,
primitive-budget, complete-heartbeat, and no-host-suspension checks. No failed or
censored episode is overwritten.

No code, parser, prompt, verifier, evaluator, budget, or protocol changes are allowed
after selection. A shared mechanism defect closes Q7 after the current pair; all five
selected identities remain consumed and any correction requires a new freeze and new
outcome-blind cases. Infrastructure failure censors the pair without automatic retry.

## Claim boundary

Q7 may decide whether the mechanism is ready for another development batch. It
cannot support the paper's main effectiveness claim, select the held-out budget,
inspect Canary or Official-Test cases, or introduce repository/package/module rules.

