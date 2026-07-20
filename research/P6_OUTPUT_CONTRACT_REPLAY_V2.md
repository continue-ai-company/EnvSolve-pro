# P6 Output-Contract Consumed Replay V2

Status: preregistered before execution. This is a one-run mechanism replay, not an
effectiveness experiment.

## Identity And Intervention

V2 reuses the exact consumed Q10 identity, method, and seed from replay v1. It does
not select, inspect, or replace another case. Algorithm v14 and Harness v28 retain the
same prompt, constraint state, operation plan, guard, verifier, aggregate budgets,
and terminal-only Official access. The only inference allocation change from v1 is
the synthetically qualified 32,768-token per-request completion ceiling.

Length-finished responses carrying usage must count as completed responses and become
recoverable `candidate-policy-output` failures. Reasoning content is never persisted.

## Decision Rule

Practical qualification requires at least five completed responses to become parsed
candidates and no output failure, empty-final diagnostic, or request error anywhere
in the run. If a length finish occurs, its accounting and category must be correct,
but the practical output contract does not qualify. Any natural budget terminal must
be `episode-budget-exhausted` with the exact scope.

An internal Pass, infrastructure Unknown, or provider exception before five parsed
responses makes the boundary unexercised without replacement. Any empty final,
usage-bearing length response counted as request error or unexpected policy exception,
persisted reasoning content, or budget-as-policy-exception transition contradicts
v14 and blocks unseen qualification.

The run cannot support an effectiveness, leaderboard, or paper test-set claim.
