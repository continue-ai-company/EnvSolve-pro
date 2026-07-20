# Typed Replay IR v8 and Complete Candidate v4

## Purpose

This revision adds provenance for observation admission without changing the
accepted candidate language. The shared validator now emits the canonical command
and typed action kind for every accepted mutation. The verifier may use this metadata
to require agreement between a failed command's kind and a provider error signature.

Replay policy identifier: `typed-replay-ir-v8`.

Complete-candidate policy identifier:
`complete-candidate-v4+typed-replay-ir-v8`.

## Change from v7

All v7 commands, canonicalization, virtual-environment binding, and rejection rules
are inherited unchanged. V8 adds an ordered, deduplicated `actions` record to the
validator result. Each entry contains only `command` and `kind`, both already
produced by the frozen replay parser. The verifier fails closed when this metadata is
missing, malformed, ambiguous, or inconsistent with the failed command.

This is an evidence-interface change, not expanded shell authority. It prevents a
provider-like text fragment produced by a runtime or unrelated operation from being
admitted as a negative package-operation fact.

## Validation

The inherited v6 and v7 corpora remain active. The v8 delta checks the operation kinds
needed by provider-failure admission, and candidate tests verify the emitted action
records. Focused replay, candidate, verifier, constraint, guard, and loop tests pass.
No development repository is rerun to qualify this interface.
