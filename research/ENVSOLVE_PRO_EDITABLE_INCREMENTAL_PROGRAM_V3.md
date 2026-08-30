# EnvSolve-Pro Editable Incremental Program V3

## Research Question

V2 showed that a strong Agent naturally distinguishes inspection from persistent
deployment operations and can use replay feedback in the same session. It also showed
that two states with different semantics had been conflated:

1. execution evidence is historical fact and should be append-only;
2. the current deployment program is a hypothesis and must change when replay falsifies
   an earlier step.

V3 asks one narrow question: does allowing the same Agent to revise one recorded program
step turn a replay counterexample into a cleaner executable repair path?

## Minimal Algorithm

V3 preserves V2's continuous session and single annotated arbitrary-Bash shell:

- `envbench_shell(command, effect=inspect)` executes only in the active construction
  environment;
- `envbench_shell(command, effect=persist)` executes there and appends the exact command
  after construction success;
- every successful append runs the complete public goal, and goal Pass triggers clean
  replay from the target initial state.

V3 adds one non-shell plan operation:

`revise_program(step_index, replacement_command)`

- a non-empty replacement substitutes the indexed current step;
- an empty replacement deletes that step;
- the edit changes only the current candidate program, not the active construction
  environment;
- every edit immediately clean-replays the complete revised program and returns the
  result to the same Agent session;
- each result exposes the refreshed, one-based indexed program.

The operation is not a second mutation shell. It cannot inspect or modify the active
construction environment, install a package directly, or bypass replay. It edits the
object being certified. The Agent may call it whenever a recorded step is wrong; there is
no controller classifier or hard rule deciding when revision is allowed.

## Three Layers

**Observation.** Ordinary shell output, complete public-goal observations after appends,
and exact clean-replay counterexamples after candidate Pass or plan edits.

**Constraint.** Case-local unresolved contradictions derived by the same Agent from those
executable observations. Historical observations remain immutable; the harness does not
create package or compatibility rules.

**Operation.** The Agent may inspect the active environment, append a new persistent step,
or revise one existing program step. Program revision is non-monotonic even though the
evidence trajectory is monotonic.

## What V3 Does Not Add

V3 adds no checkpoint, container snapshot, package classifier, version rule, command
filter, cross-case memory, candidate graph, fixed observation cadence, prompt patch for
HARK, new hash, frozen contract, or safety gate. Existing evaluator isolation and
integrity auditing remain shared experimental infrastructure rather than algorithmic
treatment.

Compound persistent commands remain legal. V3 records whether an edit targets a compound
step, but command decomposition and path minimization are later orthogonal treatments.

## Qualification and Claims

Deterministic tests first establish append, replace, delete, index-refresh, replay, and
same-session feedback semantics. A consumed HARK episode may then test natural activation
because V2 already exposed a replay-invalidated prefix there. If the fresh trajectory never
produces an invalid earlier step, the edit opportunity is absent and the episode is
censored for activation rather than counted as failure.

The mechanism qualifies only when an observed replay counterexample referring to an
earlier step is followed by a model-selected replacement or deletion and the revised
program is actually replayed. Qualification cannot establish success-rate, efficiency,
generalization, or SOTA. After qualification, V3 must be fixed before an outcome-blind
paired development comparison against V2 or Minimal B.

Report Official Pass@1 as the primary endpoint in effect experiments. Diagnostic outcomes
include edit activation, before/after program length, invalid-prefix retention, replay
sequence, counterexample-to-edit latency, replay/Official agreement, requests, tokens,
wall time, traffic, and path completeness. Tokens and resources are measurements, not hard
termination thresholds.
