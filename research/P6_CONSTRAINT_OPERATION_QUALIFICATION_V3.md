# P6 Constraint-Operation Qualification V3

Status: protocol amendment before Q3 selection or execution.

Q2 is permanently closed after its first paired case. Both episodes are
audit-valid negative mechanism evidence, but the full treatment exposed a state
transition that violated the intended partially observable semantics: a verifier
failure containing only a hypothesis retired an unresolved fact from an earlier
fresh environment. The pair and all five Q2 cases remain development-consumed;
the remaining eight Q2 positions must not execute.

V3 makes one generic state-transition correction. A fresh-environment verifier
outcome is a partial observation, not a complete environment snapshot. An active
fact is retired only when a later outcome normalizes a fact with the same
`(domain, subject, predicate)` key. A hypothesis-only failure, or a failure that
does not observe that key, preserves the unresolved fact and its operation
obligation. A passing verifier may retire all active facts because the episode
terminates successfully.

The correction is specified and tested only with synthetic names. It adds no
repository rule, package mapping, parser pattern, repair action, model prompt,
verifier signal, budget, metric, or treatment-specific information.

Q3 repeats the frozen paired comparison on five outcome-blind cases selected from
`experiments/cases/train_untouched_after_operation_qualification_v2_186.jsonl`
using salt `envsolve-p6-operation-qualification-v3-2026-07-17` and ascending
`SHA256(salt + NUL + case_id)`. The V1 protocol remains normative except for the
new source pool, salt, run identifiers, V2 closure, and corrected mechanism
freeze. No Q1 or Q2 case may be reused.

