# EnvSolve-Pro Operation-Relevance Contract v1

Status: design-frozen before implementation and before selecting another development
repository.

## Motivation

The postcondition-persistence qualification preserved the right unresolved findings but
did not make the next operation causally relevant. On the consumed OpenQASM trajectory,
different methods repeatedly tried equivalent build paths without new evidence. This
motivates one minimal Operation-layer change. OpenQASM is a counterexample used to define
the generic failure class; it must not be used to choose packages, commands, paths, or
thresholds.

## Contract

The model remains free to emit any complete, cumulative Bash deployment program. It does
not choose from a package, runtime, or build-action vocabulary. Alongside the program it
must emit:

1. `target_finding_ids`: currently active executable-goal findings addressed by the new
   repair;
2. `precondition_evidence_ids`: identifiers of evidence already visible in the model
   projection and used to justify feasibility;
3. `expected_resolved_finding_ids`: a non-empty subset of the targets predicted to
   disappear;
4. `operation_family`: open strings naming the repair's tool, mechanism, and target.

Before the first goal observation, a synthetic goal target represents the initial
deployment attempt. The family describes the newly introduced repair, not the cumulative
setup retained from an earlier candidate.

## Machine Checks

The policy rejects a proposal before environment allocation when:

- a target is not currently active;
- an expected resolution is not one of the proposal's targets;
- cited precondition evidence was not exposed to the model;
- a repair proposal after executable feedback cites no execution, repository, or retained
  candidate evidence;
- its complete script already produced a conclusive goal failure; or
- the same failed operation family is retried against an overlapping target without
  citing evidence absent from the earlier attempt.

These checks validate relevance and provenance, not the semantic correctness of an
arbitrary shell program. The operation family is model-declared and therefore auditable
but not adversary-proof. Exact-script suppression remains harness-derived. This
limitation must be reported rather than hidden.

## Progress Certificate

For each executed contract, the next model projection records:

- the active finding set before execution;
- the expected resolved set;
- the observed active set after execution;
- expected findings resolved or still active;
- newly introduced findings; and
- whether the delta is conclusive, unknown, met, or not met.

Absence discharges a finding only under a complete same-goal snapshot. A missing or
partial report yields `unknown`, never synthetic progress. Passing the executable goal
resolves the synthetic initial target.

## Frozen Counterexamples

Synthetic tests must reject:

1. a nonexistent target identifier;
2. a nonexistent evidence identifier;
3. an expected finding outside the target set;
4. a repeated conclusively failed script;
5. a same-family retry with no newly cited evidence.

They must allow:

1. an initial open-program deployment grounded in the public repository profile;
2. a repair targeting a current finding and citing its verification;
3. a same-family retry that cites newly observed execution feedback;
4. a different open operation family; and
5. an unknown progress result after incomplete feedback.

## Qualification Rule

Implementation is first tested synthetically and against already consumed artifacts.
Only after code, prompts, parser, progress analysis, and method mapping are frozen may a
metadata-selected repository-disjoint Dev batch be opened. The primary comparison is
`envsolve-pro-operation-contract` versus the frozen fresh
`envsolve-pro-goal-contract-evidence-anchor` control. Official Pass is primary; contract
validity, post-failure recovery, duplicate suppression, and progress calibration are
mechanism metrics. Tokens and time remain reported outcomes, not success cutoffs.
