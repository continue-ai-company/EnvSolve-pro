# Counterexample-Guided Deployment Loop v1

Status: design preregistration; no real-case outcome has been observed with this mechanism.

## Hypothesis

The single treatment over EnvSolve v0 is persistent verifier feedback. After a
candidate deployment is replayed in a fresh environment, an executable verifier
must either pass it or emit typed counterexample evidence. Failed evidence is
normalized into explicit solver constraints and committed to the event log before
the policy may propose another candidate.

This tests whether stateful counterexample accumulation improves environment
construction under the same model, tools, and resource budget. It does not test a
repository map, a larger prompt, a retry policy, or a collection of failure-specific
repair rules.

## State Machine

For candidate round `t`:

1. `propose(S_t) -> C_t`: the policy receives the complete reconstructed state.
2. `verify(C_t) -> O_t`: a pluggable executable verifier evaluates the candidate in
   a fresh environment with a unique execution identity.
3. If `O_t` passes, record the verification and terminate satisfied.
4. If `O_t` is unknown, malformed, stale, or infrastructure-blocked, record it and
   terminate blocked. It is not a repair signal.
5. If `O_t` fails, record the candidate action, verification, failure, and typed
   counterexample evidence. Normalize that evidence through the existing P3
   constraint engine and persist the resulting constraints.
6. Permit `propose(S_{t+1})` only after step 5 is complete. Stop blocked when the
   failure produces no normalized constraint or the candidate budget is exhausted.

The core loop depends only on protocols for candidate policy and executable
verification. EnvBench, Pyright, Docker, P5 collectors, and any model provider stay
behind adapters.

## Invariants

- Every attempted candidate has one immutable action record and one verification.
- Passing requires a successful bootstrap result and no counterexamples.
- A verifier failure never becomes free-form prompt text only; its evidence and
  normalized constraints are auditable state.
- Unknown or infrastructure failure never becomes a package/runtime constraint.
- Environment identities cannot be reused across candidate rounds.
- Unparseable verifier output and unnormalizable failures fail closed.
- The loop adds no repository-name condition, import-to-package guess map, or source
  modification path.

## Admission Experiment

Implementation tests use synthetic policies and verifiers only. Algorithm admission
requires a separately preregistered, outcome-blind development batch not used by
v0 design or Typed Replay IR v5 debugging.

The comparison uses the same model backbone and matched budgets for:

- same-backbone FreeAgent;
- EnvSolve v0;
- EnvSolve with only Counterexample Loop v1 enabled.

The mechanism is admitted only if all artifacts audit successfully, provider and
infrastructure censoring are reported separately, and the loop improves official
case completion over v0 without reducing repository integrity. Secondary measures
are clean-replay completion, verifier-counterexample coverage, requests, tokens,
wall time, and candidate rounds. A single repository cannot justify a new repair
operator or parser rule.

## Explicit Non-Goals

Version v1 does not add search-tree branching, rollback selection, learned value
functions, repository retrieval, benchmark-specific verifier semantics, or automatic
network retries. Those require independent error evidence and separate ablations.
