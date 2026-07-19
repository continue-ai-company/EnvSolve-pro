# Typed Replay IR v5

## Purpose

Typed Replay IR converts a successful solver shell trajectory into a minimal,
auditable environment bootstrap. Classification depends only on shell semantics
and typed environment effects, not repository identity, benchmark split, or
evaluation outcome.

Policy identifier: `typed-replay-ir-v5`.

## Semantic contract

Every successful source command receives exactly one disposition:

1. `action`: represent one or more proven environment state changes;
2. `drop`: prove the complete expression state-neutral for reconstruction;
3. `reject`: fail closed when syntax, effects, or control flow are not safely
   representable.

Rejected source text is never copied into the replay script.

## Change from v4

Round2 discovery exposed a representation mismatch in four independent,
audited EnvSolve v0 trajectories: the agent used the conventional
`eval "$(pyenv init -)"` shell activation, the fixed verifier passed, and v4
then rejected the successful command because arbitrary `eval` is unsupported.

V5 adds one benchmark-independent semantic normalization:

- an exact `eval "$(pyenv init -)"` or `eval "$(pyenv init --path)"` action,
  with either shell quote style, becomes
  `export PATH="$(pyenv root)/shims:$PATH"` with effect
  `runtime_configure`.

The source `eval` is not replayed. The canonical command executes only the
allowlisted `pyenv root` query inside a quoted substitution and exposes the
selected runtime through pyenv's shim directory. Other `eval` expressions,
other programs, unknown `pyenv init` modes, and general command substitution
remain rejected.

## Preserved invariants

- Unknown shell text never enters replay.
- Every replay line has a typed effect and source provenance.
- Observation removal cannot hide a durable filesystem write.
- Ambiguous fallback or sequential mutation control flow remains rejected.
- Dangerous import and path variables remain prohibited.
- Project paths are mapped only from the recorded generation root to the fresh
  evaluator root.
- Repository integrity and EnvSolve completion verification are independent
  prerequisites for recorded redistillation.

## Validation and freeze

The machine-readable corpus is `tests/fixtures/replay_ir_v5_cases.json`. It
contains the complete v4 corpus, positive pyenv initialization cases, and
negative controls for arbitrary `eval` and unknown pyenv modes. V4 artifacts
and Round2 source results remain immutable. V5 may be used only by a separately
preregistered counterfactual replay after focused tests, the full harness suite,
and a new freeze record pass.
