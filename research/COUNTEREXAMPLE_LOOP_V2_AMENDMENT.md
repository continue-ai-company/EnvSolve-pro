# Counterexample Loop v2 Amendment

Status: pre-real-case synthetic amendment to Counterexample Loop v1.

The v1 synthetic audit found that successful normalization alone is not a
sufficient repair gate. A malformed adapter could emit a requirement and an
observation that agree, producing valid but already satisfied constraints from a
reported verifier failure. Allowing another candidate would make the loop stateful
without making the feedback semantically corrective.

Version 2 adds one invariant: a failed executable verification may permit another
candidate only when its newly admitted typed evidence leaves at least one explicit
constraint conflict. A normalized but non-contradictory failure terminates blocked
as an adapter-contract violation.

No real repository, held-out case, model response, or benchmark outcome was observed
while making this amendment. All other v1 state ordering, freshness, fail-closed,
budget, and admission rules remain unchanged.
