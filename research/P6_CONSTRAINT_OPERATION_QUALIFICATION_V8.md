# P6 Constraint Operation Qualification V8

Status: preregistered before Q8 selection, repository inspection, or execution.

## Purpose

Q7 showed that package-state admission alone did not preserve runtime
compatibility across fresh candidates. Q8 is the first outcome-blind development
batch for EnvSolve v9. It tests whether image-bound runtime observations,
conditional runtime-constraint admission, and cumulative operation preservation
work on new cases. It is not a case-specific repair and cannot support the paper's
main effectiveness claim.

## Frozen Comparison

Both conditions use the same model, seed, repository profile, bounded declaration
observer, network-disabled base-runtime observer, fresh-container provider,
candidate language, Python deployment verifier v5, terminal evaluator, and
primitive limits.

- `envsolve-operation` admits eligible package and runtime constraints before
  proposal 1, exposes the typed operation plan, and applies operation guard v3.
- `envsolve-operation-ablation` runs both observers but admits no typed initial
  constraints, hides the operation plan, and has no operation guard.

Both conditions receive the same raw repository profile and executed-candidate
feedback. Official evaluator output remains terminal-only.

## Sample and Schedule

Five identities are selected from the untouched 161-case development pool by
ascending `SHA256(salt + NUL + case_id)`. Selection uses identity metadata only;
there is no repository inspection or runtime-trigger prescreen. Pair order and
within-pair method order are fixed by separate salted hashes. Once materialized,
all five identities are permanently development-consumed.

## Preregistered Outcomes

The primary outcomes are runtime-state mechanism invariants:

1. the base-runtime observation and candidate environments use the same image
   digest in every run;
2. every full-condition runtime mismatch becomes a hard runtime conflict and a
   `runtime_configure` operation obligation before the next executed candidate;
3. while that conflict remains, or after candidate-scoped evidence satisfies the
   runtime requirement, the next full candidate preserves a runtime operation;
4. a localized failed command prefix is not executed unchanged again, while a
   candidate changed before the failure point remains admissible;
5. no operation-guard exception, malformed plan, or false novelty requirement
   blocks an otherwise covering candidate.

The runtime mechanism is **exercised** only if at least one scientifically eligible
full run observes an incompatible runtime declaration or deterministic runtime
mismatch and has a later proposal opportunity. If this trigger count is zero, Q8
is reported as unexercised and cannot qualify v9; no replacement case is selected.
Any invariant violation is a shared mechanism defect and closes Q8 after the
current pair.

Secondary descriptive outcomes are paired official Boolean results, internal-Pass
and evaluator reach, candidate and token use, repeated attempts, runtime operation
counts, and package/runtime requirements closed by fresh positive observations.
A paired official category is reported only when both runs are scientifically
eligible and both official outcomes are Boolean.

## Eligibility and Adaptation

Each run must pass artifact integrity, committed-source, schedule-identity,
primitive-budget, complete-heartbeat, and no-host-suspension checks. No failed or
censored episode is overwritten.

No code, parser, prompt, verifier, evaluator, budget, or protocol change is allowed
after selection. A shared defect closes Q8 after the current pair; all selected
identities remain consumed and any correction requires a new freeze and new cases.
Infrastructure failure is recorded as Unknown and censors the pair without an
automatic Q8 retry.

## Claim Boundary

Q8 may qualify runtime-state v9 for another development batch. It cannot establish
paper-level effectiveness, choose a held-out budget, inspect Canary or Official-Test
cases, or introduce a repository, package, module, or version mapping.
