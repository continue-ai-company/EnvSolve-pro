# P3 Evidence and Constraint Protocol

## Purpose

P3 turns observations in the P2 state trajectory into typed constraints and
checks proposed environment changes before execution. The constraint core is
benchmark-independent: EnvBench result parsing exists only in an experiment
adapter and is not imported by the solver.

The P3 claim is deliberately narrower than full dependency resolution:

> For the supported typed fragment, high-confidence contradictions are
> deterministically detected, explained with evidence references, and blocked
> before a mutating action reaches the executor. Unsupported or uncertain
> statements remain unresolved and cannot cause a hard rejection.

## Canonical constraint model

Each constraint has the following semantic fields:

| Field | Values |
| --- | --- |
| `domain` | `runtime`, `package`, `capability`, `module`, `platform` |
| `subject` | Canonical runtime, package, executable, module, or platform name |
| `predicate` | `version`, `present`, or `equals` |
| `value` | PEP 440 specifier/version, boolean, or string |
| `role` | `requirement` or observed `fact` |
| `confidence` | Number in `[0, 1]` |
| `evidence_ids` | Immutable P2 evidence references |

The constraint ID is a SHA256-derived identifier over canonical semantic JSON;
it excludes confidence and evidence. Repeated observations of the same
semantic statement therefore merge evidence and retain the maximum confidence
without changing identity. Confidence is persisted in the canonical
expression, while every cited evidence ID is validated by the P2 reducer.

Package names follow Python package canonicalization. Runtime and package
versions use `packaging` PEP 440 `Version` and `SpecifierSet`, rather than
custom string comparison.

## Evidence normalization

The deterministic normalizer currently accepts structured evidence for:

- Python/runtime requirements and observations;
- package version or presence requirements and observations;
- executable capability and module presence;
- platform equality;
- command results containing Python-version mismatches, missing executables,
  or missing Python modules.

The command-result detectors contain no repository or benchmark case names.
Unrecognized evidence emits no constraint. Invalid structured values fail
closed instead of being coerced; for example, presence must be a JSON boolean.

## Propagation and explanation

Constraints at or above the frozen confidence threshold `0.8` participate in
hard propagation. Lower-confidence constraints remain `active`, are listed as
`provisional_constraints`, and cannot create a hard conflict.

The current decidable fragment detects:

- different observed versions for one subject;
- an observed version outside the conjunction of requirement specifiers;
- incompatible exact version pins;
- conflicting discrete requirements or facts;
- a required boolean/string value contradicted by an observed value.

Compatible observed facts satisfy their requirements. Requirements without
sufficient observations remain active. General emptiness of arbitrary PEP 440
range intersections is not claimed in P3; such unresolved ranges remain active
unless an exact pin or observed version proves a contradiction.

Every conflict contains a stable conflict ID, subject/domain, participating
constraint IDs, supporting evidence IDs, and a deterministic explanation.
Propagation updates only changed status records, so replay after convergence is
idempotent.

## Pre-action check

`preflight_action` returns one of:

| Disposition | Meaning |
| --- | --- |
| `allow` | Known constraints permit the action |
| `require_evidence` | The action is not disproved, but required evidence or declared effects are missing |
| `reject` | A precondition is unknown/violated, a proposed fact conflicts, or a mutating action is attempted while a hard conflict exists |

Mutating actions declare `metadata.proposed_facts`. A mutating action without
declared effects is not executed. Read-only probes and verifiers may still run
while the state contains a conflict, because collecting evidence is necessary
to resolve it.

`ConstraintCheckedPolicy` wraps any P2 policy. It propagates evidence before
each decision, records the complete preflight report as evidence, and returns a
blocked stop decision for non-allowed actions. The P2 loop remains the sole
executor owner, so rejected actions produce zero action lifecycle events and
zero executor calls.

## Recorded development validation

P3 was validated without a model request or a new benchmark execution. The
experiment adapter replayed two already consumed P0 Dev results:

- `automl/neps`: recovered the requirement `<3.12,>=3.8`, observed Python
  `3.13.2`, and emitted one traced runtime conflict;
- `benadida/helios-server`: recovered required and missing `pg_config` facts
  and emitted one traced capability conflict.

Together they produce four constraints and two conflicts. Both append-only
state artifacts independently audit as valid.

P2 bounds recorded output to 16,000 characters. Since installer diagnostics
often occur at the end of a long log, the experiment adapter records the last
16,000 characters and the SHA256 of the original result file. This is an
explicit adapter boundary, not a benchmark-specific solver rule. A live raw
diagnostic capture adapter remains P4 work.

Run the generic recorded-result experiment adapter with:

```bash
python3 envsolve/tools/replay_recorded_results.py \
  --result '<recorded-result.json>' \
  --output-root runs/p3-constraint-recorded-dev-v1 \
  --summary experiments/validations/p3_constraint_recorded_dev_results.json
```

## Exit criterion and freeze

Seventeen synthetic tests cover semantic identity and evidence merging,
idempotent propagation, PEP 440 compatibility, runtime/capability/exact-pin
conflicts, low-confidence behavior, persisted confidence, all three preflight
dispositions, read-only evidence collection during conflict, and rejection
before executor entry. The frozen P2 and P0 regressions remain green.

Generate or verify the content-addressed P3 contract with:

```bash
python3 envsolve/tools/p3_freeze.py
python3 envsolve/tools/p3_freeze.py --verify
```
