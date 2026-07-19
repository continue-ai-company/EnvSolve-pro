# P6 Constraint-Operation Qualification V5

Status: protocol amendment before Q5 selection or execution.

Q4 completed all five outcome-blind pairs. All ten trajectories are audit-valid.
Among four uncensored pairs, full EnvSolve produced one full-only official pass,
one both-pass result, and two both-fail results; no pair produced an ablation-only
pass. One additional pair was censored by a full-condition network timeout. Four
full episodes produced typed operation requirements. In two uncensored triggering
pairs, those requirements changed successful repair behavior: one pair became a
full-only pass, and another reached a shared pass in two full candidates versus
five ablation candidates. These are development mechanism observations, not an
aggregate effectiveness claim.

Q4 also exposed a method-neutral candidate-language defect. A candidate could
create `.venv`, install through `.venv/bin/python`, and end without activating the
environment. The appended verifier then used the base interpreter and repeatedly
reported a missing tool that was already installed in the unbound environment.
Because no candidate-attributable module conflict was admitted, the operation
layer could not trigger.

V5 adds one generic environment-binding invariant to the shared candidate
validator: every `.venv` or `venv` created by a candidate must be activated after
its creation before the candidate ends. The path must match. This invariant applies
identically to full and ablation conditions and is specified with synthetic paths.
It adds no repository rule, package or provider mapping, evidence parser,
constraint, verifier signal, operation kind, evaluator access, or treatment-only
instruction.

Q5 repeats the frozen paired comparison on five outcome-blind cases selected from
`experiments/cases/train_untouched_after_operation_qualification_v4_176.jsonl`
using salt `envsolve-p6-operation-qualification-v5-2026-07-17` and ascending
`SHA256(salt + NUL + case_id)`. No Q1-Q4 case may be reused.

Compared methods share fixed limits on primitive resources: candidates, model
requests and tokens, environments, commands, and wall-clock time. The existing
dated USD estimate remains only a nonbinding operational circuit breaker and an
auditable derived field. It is not part of the task definition, method-matching
criterion, or scientific outcome.
