# P6 Constraint-Operation Qualification V2

Status: protocol amendment before Q2 selection or execution.

Q1 is permanently qualification-invalid because the candidate validator accepted
`python -m venv .venv|venv` while the operation guard rejected the same normalized
command. Its first two positions are retained only as harness diagnostics in
`experiments/validations/p6_operation_q1_closure.json`; all five Q1 cases remain
development-consumed.

V2 makes one representation-consistency correction: bounded project virtual-
environment creation is a typed replay action shared by validator and guard. It is
not an allowed witness for runtime, package, capability, or module repair
obligations. No repository rule, package mapping, evidence parser, constraint,
verifier, model, budget, metric, or causal treatment changes.

Q2 repeats the frozen V1 comparison using a new outcome-blind five-case sample from
`experiments/cases/train_untouched_after_operation_qualification191.jsonl`, salt
`envsolve-p6-operation-qualification-v2-2026-07-17`, and the same metadata-only
ascending SHA256 procedure. The complete V1 protocol remains normative except for
the new source pool, salt, run identifiers, and corrected parent freeze.

