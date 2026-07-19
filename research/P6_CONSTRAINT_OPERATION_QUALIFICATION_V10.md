# P6 Constraint Operation Qualification V10

Status: preregistered before Q10 selection, repository inspection, or execution.

## Purpose

Q9 closed when a phase-agnostic `ConnectionError` signature mislabeled an internal
test-collection failure as dependency-acquisition infrastructure. Q10 is the first
outcome-blind development qualification of phase-aware verifier v11. It tests
whether failure provenance, rather than an exception token alone, controls whether
feedback terminates or continues the deployment loop.

## Frozen Comparison

The paired comparison remains unchanged. Both conditions share model, seed,
repository and base-runtime observers, fresh environments, candidate language,
Python verifier v5, terminal official evaluator, and primitive limits. Full
EnvSolve receives typed admission, operation-plan visibility, and the guard; the
ablation receives the same raw observations and executed-candidate feedback without
those three components. Official evaluator feedback is terminal-only.

## Sample and Schedule

Five identities are selected from 151 untouched development cases by ascending
`SHA256(salt + NUL + case_id)`. Selection is identity-metadata-only, with no
repository inspection, failure-signature prescreen, package-manager stratification,
or replacement sampling. Pair and method order use independent frozen hashes. All
five selected identities become permanently development-consumed.

## Primary Phase Mechanism

V11 is exercised when a scientifically eligible run has all of the following:

1. a failed action marker identifies the fixed internal-check phase;
2. the corresponding raw output contains a frozen generic network-like signature;
3. candidate and model budgets permit at least one later proposal.

For every exercised run, the verifier must return candidate Fail rather than
infrastructure Unknown, preserve the action result as online feedback, and reach a
later proposal. The reverse invariant also remains frozen: a grounded network
signature from a candidate-command or unknown phase may still produce
infrastructure Unknown and must not be converted to a hard candidate constraint.

The subject-first runtime diagnostic from v10 is an independent inherited
invariant. If it occurs in a full run, it must create the preregistered hard runtime
conflict and `runtime_configure` obligation; its absence does not qualify v10.

If no run exercises the phase mechanism, Q10 is unexercised and v11 does not
qualify; no replacement identity is selected. Any exercised phase-invariant or
inherited runtime-invariant violation closes Q10 after the current pair. Paired
official outcomes remain secondary and require two eligible Boolean results.

## Eligibility, Retry, and Claims

Artifact integrity, committed clean source, schedule identity, primitive budgets,
complete heartbeat, and absence of host suspension are mandatory. One same-identity
retry is allowed only for pre-episode acquisition failure with zero method
information. One evaluator-only retry may replay an identical frozen script after
terminal evaluator infrastructure failure. Other failures censor the pair.

Q10 can qualify only the phase-aware v11 mechanism for continued development. It
cannot establish deployment effectiveness, tune budgets, inspect held-out cases, or
add repository, service, endpoint, package, module, or version rules.
