# P6 Constraint-Operation Qualification V11 Results

Status: closed as terminal-reach insufficient after operator interruption. No rerun
or replacement is allowed.

## Outcome

Q11 preserved all ten frozen positions. Nine runs are artifact-valid and eight are
scientifically eligible. Position 8 failed at provider acquisition before any model
usage, candidate, environment, command, or evaluator information was produced.
Position 10 was stopped by the operator after one candidate had started and is
scientifically ineligible. No run reached a Boolean Official result. Consequently,
all five pairs are censored, the preregistered minimum of two eligible Official pairs
is unmet, and Q11 provides no method-effectiveness estimate.

The narrow same-identity retry condition technically applies to position 8, but its
paired control already has no Official result. Retrying it cannot recover an eligible
pair or alter the Q11 decision. Position 10 has no preregistered interruption retry.
Both positions remain immutable, all five identities are consumed, and 141
development identities remain untouched.

## Failure Decomposition

Post-episode analysis includes only the eight scientifically eligible trajectories.
It partitions all 43 candidate transitions: 38 candidates reached fresh execution,
five were rejected by the shared validator, and seven executions ended with active
structured obligations. Candidate-command failure accounts for 31 of 38 executions
(81.6%).

| Method | Runs | Candidates | Executed | Command failure | Validation reject | Structured obligations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Constraint-driven EnvSolve | 4 | 19 | 18 | 15 | 1 | 3 |
| Free-form ablation | 4 | 24 | 20 | 16 | 4 | 4 |

These method totals are descriptive. They are neither paired Official outcomes nor
an effectiveness comparison. Relative to the consumed Q10 trajectories, where
23/41 executions were command failures, Q11 strengthens only the diagnostic that
action feasibility is the dominant development bottleneck; the batches cannot be
compared causally.

## Architecture Diagnosis

The observation layer records the complete candidate result and the exact failed
command. The constraint normalizer, however, admits only a small subset of that
feedback, such as runtime mismatches, missing executables, and missing modules.
Deterministic package-provider rejection, invalid paths, and build failures remain
raw text. The operation guard remembers failed command prefixes, but does not retain
a typed negative fact about the failed operation target across the episode.

The resulting gap is precise: **an observed failed operation often does not become
stateful negative operation knowledge**. The next proposal can therefore spend a new
environment on the same failed target after surrounding commands change, even while
the original module or capability requirement remains unresolved.

## Next Hypothesis

The next revision will test one repository-independent claim: persisting a
deterministic failed operation target as a typed, context-scoped negative feasibility
fact reduces exact failed-operation recurrence. It must not infer that the underlying
module is impossible, block a different provider or operation kind, or harden a
network or infrastructure failure.

This hypothesis must first pass repository-free positive and negative
counterexamples. Only then may it receive a new algorithm/harness freeze and a new
outcome-blind development qualification. Q11 remains error-analysis evidence only;
it cannot validate the revision it motivated.
