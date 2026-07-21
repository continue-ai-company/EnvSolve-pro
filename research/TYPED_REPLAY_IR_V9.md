# Typed Replay IR v9

## Purpose

Typed Replay IR converts a successful interactive trajectory into a clean deployment
program. Environment mutations are retained, observations are omitted, and shell
segments with unknown effects remain rejected. This revision prevents read-only test
commands from making an otherwise valid external-agent trajectory unreplayable.

Replay policy identifier: `typed-replay-ir-v9`.

Complete-candidate policy identifier:
`complete-candidate-v4+typed-replay-ir-v9`.

## Change from v8

V9 recognizes dotted modules under the standard `tests`, `test`, `pytest`, and
`unittest` namespaces as test observations when invoked with `python -m`. Read-only
pipelines composed of `cut`, `grep`, `head`, `sort`, `tail`, `uniq`, or `wc` remain
observations. They are executed in the interactive episode and preserved in the raw
trajectory, but omitted from the replay script.

The change adds no environment mutation, package source, shell authority, or
repository-specific command. Test commands piped to a shell, redirected to a file, or
using an arbitrary module namespace remain rejected. All v6-v8 corpus cases continue
to run unchanged.

## Motivation and Scope

The external-baseline qualification stage exposed a harness-only failure: a strong
agent completed its model loop, but replay finalization rejected successful test
commands solely because their module name was dotted. This failure occurred after the
agent stopped and before official evaluation, so it could not be counted as a method
failure. V9 repairs that generic interface without changing any model prompt, tool,
feedback, stopping policy, or generated mutation.

## Validation

The v9 synthetic delta contains positive dotted-test observations and negative shell,
file-write, and arbitrary-module counterexamples. Focused replay, distillation,
candidate, recorded-runner, and harness tests must pass before the policy is frozen.
Old v8 protocol and result artifacts remain immutable.
