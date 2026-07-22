# EnvSolve-Pro P3 Candidate Retention Results

Status: completed consumed-development qualification. This is not a held-out
effectiveness result.

## Decision

Best-admissible candidate retention passed both preregistered qualification gates:

- terminal evaluations with retention: `2/3`;
- terminal evaluations without retention: `1/3`;
- terminal-reach delta: `+1`.

The mechanism is therefore qualified to enter unseen-case evaluation without
case-specific changes. It has not demonstrated an Official Pass improvement:
both conditions passed `1/3` cases.

## What changed

On `roboflow/supervision`, the no-retention condition exhausted five candidates
and emitted no environment. The retention condition preserved candidate 2 after a
complete zero-exit replay with a valid repository-effect audit, zero Unknowns, and
22 residual constraints. Later candidates failed or timed out, so the frozen ranker
released candidate 2 as explicitly `uncertified`, while the internal goal remained
`blocked`.

EnvBench then completed independently. Bootstrap exited zero, but 22 official
issues remained, including eight unresolved import modules, so Official Pass was
false. Retention corrected terminal censoring; it did not solve the remaining
dependency closure.

## Interpretation

The result supports a narrow mechanism claim: an incomplete internal verifier
should not erase an executable, auditable environment at budget exhaustion. It
does not support a success-rate claim. The next algorithmic question is whether
the dominant remaining error lies in operation viability, constraint closure, or
internal-to-official verifier coverage. The preregistered eight-case trajectory
census on Spark will estimate that distribution before another intervention.

## Audit

All six scheduled artifacts passed integrity and scientific-eligibility checks.
Position 6 was rerun from a fresh run root after an operator-requested interruption;
two launcher preflight failures and one Docker infrastructure failure were archived
and excluded. The valid attempt used the frozen implementation, received no prior
attempt feedback, and retained full recovery provenance.
