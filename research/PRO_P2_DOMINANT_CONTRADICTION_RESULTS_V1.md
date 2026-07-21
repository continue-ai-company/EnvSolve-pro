# EnvSolve-pro P2 Dominant-Contradiction Results v1

## Scope

The frozen P2 batch completed all 24 scheduled positions over six metadata-only Dev
cases and four methods. P2 is diagnostic. It does not estimate effectiveness because
Codex, Repo2Run, and two raw-ReAct positions were censored by adapter or integrity
failures.

Two official passes occurred: EnvSolve-pro passed `ansible-zuul-jobs`, while raw ReAct
passed `heltour`. These outcomes are mechanism examples, not a valid 1/6 comparison.

## Dominant Contradiction

The same deterministic EnvSolve failure occurred in three repositories. A candidate
completed execution with exit code zero and passed the effect boundary, but residual
internal constraints prevented any terminal candidate from being emitted:

| Repository | Best complete candidate | Active | Satisfied |
|---|---:|---:|---:|
| `democracyclub/uk-polling-stations` | 5 | 693 | 42 |
| `sphinx-contrib/spelling` | 5 | 2 | 36 |
| `roboflow/supervision` | 3 | 29 | 44 |

The primary attribution is **Constraint**: partial internal evidence was hardened into an
exact terminal decision. The secondary attribution is **Operation finalization**: after
the search budget ended, the solver discarded every replayable candidate. This passes
the preregistered method-specific dominance exception: three repositories, direct
trajectory evidence, one deterministic cause, and a repository-independent intervention.

The minimal intervention is a certified/admissible distinction. A certified candidate
still stops early. Otherwise, EnvSolve retains the best complete, integrity-valid,
zero-exit candidate by residual structured constraints and emits it as `uncertified`
when candidate search ends. The internal goal remains `blocked`; the Official evaluator
still runs once and only after the episode. This changes neither the success criterion
nor the online feedback boundary.

## Why This Mechanism First

A second three-repository pattern concerns runtime, lockfile, dependency, and platform
compatibility in `cellrank`, `heltour`, and `supervision`. It is real but requires a
larger state and operation design. The best-so-far intervention is more directly grounded,
smaller, and immediately testable, so Occam's razor selects it for the next qualification.
Runtime-closure state remains a frozen secondary hypothesis.

## Baseline Validity

- Five Codex positions failed before acting because `container_exec` became a reserved
  GPT-5.5 tool name. The sixth showed strong deployment behavior but hit a build-output
  integrity false positive.
- Four Repo2Run positions crashed after a null response; stale `inner_commands.json`
  could make those failures appear to contain a candidate.
- Legitimate generated files censored raw ReAct on two repositories.

Post-batch repairs rename the Codex tool, isolate Repo2Run output per run, reject empty
provider content, translate private helper effects, and fix project-root namespace
resolution. Consumed-case smoke runs now give both baselines complete, integrity-valid
Official evaluations. Neither passed. This qualifies adapter validity but does not change
the frozen P2 outcomes or support comparative claims.

## Next Gate

Replay the three consumed diagnostic cases to verify the predicted output transition,
then preregister at least five new Dev pairs for EnvSolve-pro with and without admissible
candidate retention. Only unseen paired terminal outcomes can support an effectiveness
claim.
