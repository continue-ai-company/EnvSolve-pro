# P2 Explicit Environment State Protocol

## Purpose

EnvSolve represents environment synthesis as transitions over an explicit
machine-readable state. The state is not reconstructed from an LLM summary.
It is deterministically reduced from an append-only event trajectory that can
be verified independently of the solver.

## Event envelope

Every JSONL event contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | State-event schema version |
| `case_id` | Frozen repository and revision identity |
| `sequence` | Zero-based contiguous event sequence |
| `timestamp` | UTC observation or transition time |
| `event_type` | Typed state transition |
| `payload` | Structured transition data |
| `previous_hash` | SHA256 of the preceding event, or the genesis hash |
| `event_hash` | SHA256 over the canonical unsigned event |

The store uses an exclusive file lock for appends, validates the complete
existing trajectory before each write, appends one line, flushes it, and calls
`fsync`. Readers take a shared lock and validate both hash-chain and reducer
invariants.

## State dimensions

The reducer reconstructs repository profile, evidence, constraints,
hypotheses, goals, observed environment facts, actions, failures,
verifications, and rollbacks. Each inferred object retains its evidence IDs or
action relationship plus the event sequence, event hash, observation time, and
object revision that produced its current state. Every reconstructed snapshot
has a deterministic `snapshot_hash`.

Current event types are:

- `run_started`, `repository_profiled`, `evidence_recorded`;
- `constraint_upserted`, `hypothesis_upserted`, `goal_upserted`;
- `environment_updated`;
- `action_proposed`, `action_started`, `action_finished`;
- `failure_recorded`, `verification_recorded`, `rollback_recorded`.

## Enforced invariants

- A run starts exactly once and its payload matches the frozen `case_id`.
- Event sequences are contiguous and the SHA256 chain is unbroken.
- Confidence values are in `[0, 1]`.
- Constraints and hypotheses may only cite existing evidence.
- Actions may only cite existing constraint preconditions.
- An action transitions `proposed -> running -> succeeded|failed` and may then
  become `rolled_back`; transitions cannot be skipped.
- Failures cannot cite unknown actions.
- Verification levels are limited to `V0` through `V6` and pass values are
  boolean.
- A rejected append leaves the event log unchanged.

## CLI

Initialize a trajectory from a frozen case:

```bash
python3 experiments/state_log.py init \
  --log runs/p2-state-smoke/state.jsonl \
  --case-file experiments/cases/smoke.jsonl
```

Append a structured event:

```bash
python3 experiments/state_log.py append \
  --log runs/p2-state-smoke/state.jsonl \
  --case-id '<case-id>' \
  --event-type evidence_recorded \
  --payload '{"evidence_id":"ev-1","kind":"metadata","source":"pyproject.toml","value":"python>=3.10","confidence":1.0}'
```

Verify the chain and reconstruct a snapshot:

```bash
python3 experiments/state_log.py inspect \
  --log runs/p2-state-smoke/state.jsonl \
  --case-id '<case-id>' \
  --snapshot-out runs/p2-state-smoke/snapshot.json
```

## P2 exit criterion

P2 is complete when every solver observation and action is emitted through
this protocol, a complete state can be reconstructed from trajectory alone,
and deterministic replay yields the same snapshot hash. The event kernel and
standalone reconstruction are implemented.

## Solver-loop integration

`SolverStateSession` is the only write path for the EnvSolve loop. It:

- initializes `run_started` once and rejects a mismatched resumed case;
- appends each event through the locked, hash-chained store;
- atomically refreshes a derived snapshot after every accepted event;
- recursively redacts credential-shaped strings and bounds terminal output;
- turns every live or recorded action result into citable evidence;
- records executor exceptions and non-zero exits as terminal actions plus
  structured failures.

`StatefulSolverLoop` passes a freshly reconstructed `EnvironmentState` to the
policy on every step. The policy can return only an `ActionSpec` or explicit
`StopDecision`; it does not receive a direct executor handle. Action-budget and
policy failures become state events, and the goal ends as `satisfied` or
`blocked`.

The shell-trace bridge imports baseline trajectories without changing their
outcomes. Every shell interaction becomes one action lifecycle and one
action-result evidence item. This bridge is an analysis adapter; EnvSolve's
live loop uses the same session API directly.

Audit a materialized state independently:

```bash
python3 envsolve/tools/audit_state.py \
  --event-log runs/<state-run>/state.jsonl \
  --snapshot runs/<state-run>/snapshot.json \
  --case-id '<case-id>'
```

The audit reconstructs the complete state from JSONL, compares it with the
persisted snapshot, and rejects non-terminal actions.

## P2 validation

Seven solver-layer synthetic tests cover successful and failed actions,
executor exceptions, recursive secret redaction, session resume, snapshot
tampering, action-budget termination, policy stop, and complete shell-trace
capture. The separate 44-test P0 suite still passes and Harness Freeze v2
remains valid.

The already recorded `scylladb/sphinx-scylladb-theme` development trajectory
was imported without another model or benchmark execution. Its 25 shell
interactions produce 103 events: 25 terminal actions, 25 action-result evidence
items, and one failure. Twenty commands are classified as observations and five
as typed actions. Independent audit passes, and repeated reconstruction yields
snapshot hash
`e961d43c18dae044ad60ca354e780ecb471022d59dc1db9c6621bc45a0f06706`.

P2 is complete. P3 begins with evidence normalization, constraint propagation,
and pre-action satisfiability checks; no learned policy or benchmark-specific
repair rule is part of P2.

The frozen P2 source and validation contract is recorded in
`envsolve/protocols/p2_state_freeze_v1.json`. Generate or verify it with:

```bash
python3 envsolve/tools/p2_freeze.py
python3 envsolve/tools/p2_freeze.py --verify
```
