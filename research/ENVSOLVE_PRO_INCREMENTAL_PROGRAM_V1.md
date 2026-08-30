# EnvSolve-Pro Incremental Executable Program V1

Status: the separate-shell-tool interface was rejected in consumed mechanism
qualification. See `research/ENVSOLVE_PRO_INCREMENTAL_PROGRAM_V1_RESULT.md`. The
incremental-program hypothesis was not tested for effectiveness.

## Problem

Minimal B asks a strong Agent to work freely and then rewrite its successful construction
history as one bootstrap program. Bad4 shows two distinct failures: the environment may
never become sufficient, or it may already satisfy the public goal but still never become
a delivered program. Clean replay acts only after that second transition and therefore
cannot repair an absent candidate.

Prior handoff and incumbent variants do not close this gap. Handoff detects a goal Pass
and then asks the model to synthesize the whole program. Incumbent retention starts only
after a complete program has passed replay. Both leave terminal program reconstruction as
a separate model task.

## Minimal Algorithm

EnvSolve-Pro V1 makes the deployment program grow with the environment:

1. `envbench_shell` is used for inspection and diagnosis.
2. `apply_environment_step` executes a model-selected persistent operation. A successful
   command is appended verbatim to the current ordered deployment program; a failed
   command is not appended.
3. After every appended step, the harness executes the complete public goal in the active
   environment.
4. On goal Pass, the harness immediately executes the already existing program from the
   target initial state. Replay Pass terminates with that program; replay Fail returns its
   executable counterexample to the same session for another model-selected step.
5. The Agent may explicitly call `replay_current_program`, but it never needs to rewrite
   the complete history at submission time.

The Observation layer is operation-triggered executable measurement. The Constraint layer
is the current goal residual or clean-replay counterexample. The Operation layer remains a
free strong Agent choosing arbitrary Bash commands and deciding which successful changes
belong to the deployment. No package rule, action vocabulary, checkpoint, cross-case
memory, fixed observation cadence, candidate graph, or new integrity gate is added.

## Distinction From Earlier Treatments

| Method | When the program first exists | Remaining gap |
| --- | --- | --- |
| Minimal B | Agent writes it near the end | Candidate may never be formed |
| Verifier handoff | After a detected goal Pass | Agent must still reconstruct history |
| Certified incumbent | After replay Pass | Cannot help before first candidate |
| Incremental program | During each successful environment operation | Replay tests completeness of an already existing program |

This is not command logging: inspection, failed attempts, and diagnostics are excluded by
the Agent's explicit tool choice. It is also not a closed planner: the model retains the
full Bash operation space.

## Development Qualification

Deterministic tests must establish ordered step persistence, exclusion of failed commands,
automatic goal observation, target-state replay on Pass, Fail-to-repair continuity, and
termination on replay Pass. These tests qualify implementation semantics only.

The first live qualification will use already consumed goal-to-delivery failures. Its
purpose is to test whether the mechanism activates before candidate loss, not to estimate
generalization. Only after a fixed consumed qualification is complete will we choose an
outcome-blind comparison batch. Official Pass@1 remains primary; activation, recorded-step
coverage, replay outcomes, completeness, requests, tokens, time, traffic, and storage are
reported separately.

## Falsification

The treatment is rejected if Agents routinely bypass the operation-linked path, if the
accumulated program cannot represent successful deployment paths, if automatic replay
does not occur at a sufficient state, or if a fixed matched comparison shows no success
gain and higher cost. A benchmark Pass from a metric-minimal environment is success on the
primary endpoint but not evidence of deployment completeness.
