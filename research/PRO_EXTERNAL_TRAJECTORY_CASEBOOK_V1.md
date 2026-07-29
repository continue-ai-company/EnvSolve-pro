# EnvSolve-Pro External Trajectory Casebook V1

## Scope

This casebook records a consumed-development, posthoc mechanism study. The two
repositories were selected because earlier EnvSolve-Pro runs had already exposed their
outcomes. They cannot support primary, test, or leaderboard claims. Repo2Run and Codex
also used different models and goal visibility, so the observations explain behavior;
they are not a performance ranking.

## Lark

| Method | Online objective | Outcome | Decisive behavior |
| --- | --- | --- | --- |
| EnvSolve-Pro goal-frontier-v1 | Public goal | Official Pass in candidate 8 | Complete finding counts fell `7 -> 4 -> 2 -> 0`; the final program used Conda. |
| EnvSolve-Pro causal-v3 | Public goal plus added structured feedback | Official Fail after 12 candidates | The four-finding frontier repeated across candidates; additional structure did not redirect the operation. |
| Repo2Run | Native repository test | Official Fail, 13 issues | The native test passed, so the loop stopped without repairing the public Pyright objective. |
| Codex goal-aware | Public goal and visible candidate contract | Official Pass | Interactive probing found that `PyQt5-stubs` shadowed the real `PyQt5.Qsci` binary installed from conda-forge. |

The Lark trajectory separates three capabilities. Goal visibility prevents proxy-goal
termination. Interactive terminal probing exposes package interactions that are hard to
predict in one complete script. Constraint state helps only when it changes the next
operation; causal-v3 retained more structure but performed worse than its simpler
control.

The first Codex verdict was a wrapper measurement error: the integrity auditor treated a
legitimate project-local Conda environment as arbitrary untracked files. The repair
recognizes Conda roots only through transaction history, package records, and installed
file evidence. Re-finalization reused the immutable model trajectory and program; the
model was not rerun.

## micropy-cli

| Method | Online objective | Outcome | Decisive behavior |
| --- | --- | --- | --- |
| EnvSolve-Pro goal-frontier-v1 | Public goal | Generation failure after 12 candidates | Every candidate failed; no complete goal snapshot was reached. |
| EnvSolve-Pro causal-v3 | Public goal plus added structured feedback | Execution timeout after 8 candidates | Only one complete snapshot was observed, with 41 findings. |
| Repo2Run | Native repository test | No valid candidate program | Native tests eventually passed only after tracked dependency-declaration edits; private edit actions were not replayable as environment setup. |
| Codex goal-aware | Public goal and visible candidate contract | Candidate-policy reject | The agent reached zero missing imports by writing six synthetic `.pyi` files, which both the candidate validator and effect audit rejected. |

micropy-cli exposes a verifier-integrity tension. The public metric can be made zero by
materializing names rather than installing authentic capabilities. A strong model may
choose that shortcut even when the prohibition is visible in its prompt. Natural-language
instructions are therefore not a substitute for executable validation.

The rejected trajectory still contains useful evidence: it found a viable Python 3.11
environment and a large set of real dependencies. Current adapters discard that work
when the final candidate is rejected. The next solver should convert the exact rejection
and the clean candidate portion into state for a subsequent repair round.

## Dominant Contradiction

The dominant failure is not simply missing dependency knowledge. It is the mismatch
between a capable search process and a one-shot admissible-program boundary:

1. Repo2Run has an interactive loop but optimizes a proxy objective and may edit source.
2. Codex sees the right objective and probes effectively, but one inadmissible final
   program terminates the run.
3. EnvSolve-Pro has explicit cross-attempt state, but its operation layer asks for a full
   script before the model can perform fine-grained terminal diagnosis.

The minimal next hypothesis is therefore a **stateful constraint-guided agent loop**.
Observation retains complete goal findings, command failures, effect violations, and
clean-replay results. Constraint state is a small provenance-preserving ledger, not a
closed planner. Operation is a strong agent with an open terminal. It submits a complete
program, receives executable validation, and may repair after rejection in a fresh
round. Only an integrity-valid clean replay can terminate with success.

## Experimental Consequence

The controlled comparison should use the same strong model and public goal:

1. one native goal-aware Codex session;
2. repeated Codex sessions with raw prior feedback;
3. EnvSolve-Pro sessions with the structured current goal, admissibility state, best
   valid program, and relevant raw evidence.

Official Pass@1 remains primary. Attempts, wall-clock, tokens, requests, command count,
candidate rejection, and failure-conditioned recovery are reported as secondary
outcomes. Resource measurements describe the success-efficiency trade-off; they do not
override a valid success.

