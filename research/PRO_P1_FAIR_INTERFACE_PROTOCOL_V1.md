# EnvSolve-pro P1 Fair-Interface Protocol v1

## Question

Can a deployment method's native success be transferred to the terminal evaluator
without a closed command vocabulary changing its behavior, while preserving the task's
safety and repository-integrity boundaries?

P0 showed two distinct failures that must not be conflated:

1. **Representation loss:** a successful native operation was rejected or removed only
   because the post-hoc parser did not recognize its shell form.
2. **State mismatch:** generation or internal verification began without evaluator-owned
   workspace artifacts, so a candidate passed under easier preconditions than the
   terminal evaluator.

P1 repairs the measurement interface before making an algorithmic effectiveness claim.

## Interface

### Open candidate program

The submitted artifact is a complete Bash program, not a sequence in a closed action
grammar. Shell syntax is not evidence of invalidity. The program is sourced from the
project root, matching EnvBench. A candidate is bounded by size, execution time, a fresh
container, and the absence of host credentials or host-control sockets.

### Fresh execution and effect audit

Every EnvSolve candidate executes in a new checkout and container. Acceptance requires
fixed executable postconditions and an effect audit after execution: the requested
revision remains checked out, tracked repository files remain unchanged, no untracked
import or dependency-configuration artifact is injected, and adapter-owned preconditions
remain present. Command schemas may summarize effects and localize failures, but schema
coverage is not a correctness condition.

### Adapter-declared preconditions

The benchmark adapter declares non-outcome workspace state that exists before the
bootstrap program. For EnvBench Python v1 this includes `build_output/`, because the
official build script creates it before sourcing the candidate. Internal verification
must materialize the same state. The official evaluator remains terminal-only.

### Baseline trajectory transfer

EnvBench raw ReAct follows the upstream rule: preserve successful commands in their
original order, comment or omit failed commands, and relocate only the native project
root. Repo2Run additionally compiles its explicit sandbox control actions and captures
its documented ambient Python 3.10 runtime. Read-only probes and shell compounds are not
deleted merely because they are absent from a replay schema.

## Frozen Predictions

The already consumed P0 cases are diagnostic data and may be replayed without new model
calls.

1. Raw ReAct `marimo` and `futaba` trajectories will no longer be rejected solely for
   `mkdir`, compound environment replacement, parent-directory probes, or successful
   Python probes.
2. Repo2Run `futaba` will preserve the Python 3.10 state in which its native Poetry
   installation succeeded; terminal Pyright may still fail for an independent reason.
3. Raw ReAct `importlib_metadata` may still fail when replayed because its native loop
   did not observe EnvBench's pre-bootstrap `build_output/`. Such a failure supports
   state mismatch, not parser loss.
4. The frozen EnvSolve `importlib_metadata` candidate that passed the old internal
   verifier will not be accepted when `build_output/` is materialized first.
5. Repository-neutral fixtures that modify tracked source, inject importable files, or
   delete adapter-owned preconditions will fail the effect audit. Benign generated
   environment artifacts will remain admissible.

## Qualification Gate

P1 passes only if synthetic tests establish the safety boundary and consumed P0 replays
separate representation loss from state mismatch as predicted. A result may be Pass,
Fail, or Unknown; infrastructure failures are censored. No untouched Dev repository is
opened until implementation, tests, prompts, and this protocol are frozen in Git.

Passing P1 establishes a fair execution interface, not that EnvSolve-pro outperforms a
baseline.
