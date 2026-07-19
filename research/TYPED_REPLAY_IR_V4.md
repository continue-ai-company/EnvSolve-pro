# Typed Replay IR v4

## Purpose

Typed Replay IR converts a successful solver shell trajectory into a minimal,
auditable environment bootstrap. It is benchmark-independent: classification
depends on shell semantics and typed environment effects, not repository names,
benchmark outcomes, or evaluator diagnostics.

Policy identifier: `typed-replay-ir-v4`.

## Semantic contract

Every successful source command must receive exactly one disposition:

1. `action`: one or more state changes are represented by typed replay actions;
2. `drop`: the complete expression is proven state-neutral for environment
   reconstruction;
3. `reject`: an effect, control-flow path, or syntax element cannot be proven
   safe and replayable.

The policy fails closed. A rejected successful command rejects the generated
bootstrap; it is never silently copied into the script.

## Typed effects

The v4 action kinds are:

- Python package installation;
- system package installation;
- package-index update;
- runtime configuration;
- environment export;
- environment activation.

Actions are canonical shell commands with their original source command kept as
provenance. Arbitrary source edits, evaluator configuration, path injection,
download-and-execute pipelines, and unclassified shell fragments have no IR
representation.

## Compound commands

- `A && B`: analyze each segment. Typed actions are retained and proven
  observations are removed. Because the overall command succeeded, every
  executed predecessor in the chain succeeded.
- `A || B`: drop only when every branch is independently proven
  state-neutral. If any branch contains a typed or unknown effect, reject the
  whole fallback expression because the executed branch is ambiguous.
- `A ; B` and multiline sequences: drop only when every command is
  state-neutral. Otherwise reject because the final exit code does not prove
  that earlier mutations succeeded.
- pipelines: drop only when the producer and every filter are read-only.
  Mutation pipelines are accepted only for a typed mutation followed by
  allowlisted log filters; the filters are removed from replay.
- `bash -c`, `bash -lc`, `sh -c`, and `sh -lc`: drop only when the nested body
  recursively proves state-neutral. Nested mutations remain unsupported.

## Observation proof

An observation must use an allowlisted read-only command form. The proof rejects
output redirection except to `/dev/null`, command or process substitution,
mutating `find` predicates, arbitrary Python snippets, and mutation-capable
pipeline filters. Python `-c` is observational only when its AST consists of
imports and safe display expressions.

Plain `echo` and `printf` without redirection are observations. A narrowly
recognized `echo 'export NAME=VALUE' >> ~/.bashrc` form is not dropped: it is
canonicalized to the typed `export NAME=VALUE` action, subject to the same
dangerous-variable and path-injection checks as a direct export.

## Safety invariants

- No command selected for replay is unknown shell text.
- Every replay line has a typed effect and source provenance.
- Observation removal cannot hide a durable filesystem write.
- Fallback control flow cannot select between mutation branches.
- Dangerous import/path environment variables remain prohibited.
- Project paths may be mapped only from the recorded generation root to the
  fresh evaluator root.
- Repository integrity is checked independently before distillation.

## Freeze procedure

The machine-readable synthetic corpus is
`tests/fixtures/replay_ir_v4_cases.json`. Policy behavior is frozen only after
the corpus, unit tests, and full harness regression suite pass. Benchmark
trajectories may be re-distilled after freeze, but cannot be used to add or
special-case grammar rules within the same policy version.
