# Typed Replay IR v6

## Purpose

Typed Replay IR converts a successful solver shell trajectory into a minimal,
auditable environment bootstrap. Classification depends only on shell semantics
and typed environment effects, not repository identity, benchmark split, or
evaluation outcome.

Policy identifier: `typed-replay-ir-v6`.

## Semantic contract

Every successful source command receives exactly one disposition:

1. `action`: represent one or more proven environment state changes;
2. `drop`: prove the complete expression state-neutral for reconstruction;
3. `reject`: fail closed when syntax, effects, or control flow are not safely
   representable.

Rejected source text is never copied into the replay script.

## Change from v5

The preregistered position-2 development diagnostic exposed an internal
representation mismatch. V5 allowed activation of a project-root virtual
environment, but rejected direct package mutations through the same bounded
environment, such as `.venv/bin/pip install ...`.

V6 makes this existing abstraction consistent. It recognizes `python` and
`pip`, including numbered variants, only at these project-root-relative paths:

- `.venv/bin/` and `venv/bin/`;
- `${PROJECT_ROOT}/.venv/bin/` and `${PROJECT_ROOT}/venv/bin/`.

No arbitrary path is admitted. Absolute paths, nested virtual environments,
unknown executables, shell substitution, and untyped shell text remain
rejected. Accepted commands retain their bounded executable path so package
mutation targets the environment selected by the solver.

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

The machine-readable corpus is `tests/fixtures/replay_ir_v6_cases.json`. It
contains the complete v5 corpus, three positive project-root virtual-environment
cases, and two negative path-boundary controls. The triggering run remains an
immutable development diagnostic and receives no replacement evaluation. V6
may be used only after focused tests, the full harness suite, real Docker
integration, and a new freeze record pass.
