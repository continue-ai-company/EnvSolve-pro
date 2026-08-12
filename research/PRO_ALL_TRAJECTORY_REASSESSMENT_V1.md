# EnvSolve-Pro All-Trajectory Reassessment v1

Date: 2026-08-03

## Research Question

Before implementing another EnvSolve-Pro mechanism, this reassessment asks one
question: what failure is repeated across the existing trajectories, and what is the
smallest algorithmic change that directly addresses it?

The review does not use consumed cases to estimate generalization. Consumed trajectories
are mechanism evidence only. Any promoted algorithm must be frozen before a new,
repository-disjoint development qualification.

## Evidence Boundary

The local artifact census contains 620 manifests. The mechanism audit covers all locally
synced execution traces associated with them:

- 278 EnvSolve episode logs;
- 86 Codex container-command traces;
- 97 legacy agent trajectories, of which 24 match the currently supported parser;
- 7 completed Repo2Run trajectories with readable native action histories.

The 278 EnvSolve episodes contain 1,055 whole-program actions and 944 executable
verifications. The EnvSolve-Pro subset contains 132 episodes, 512 actions, and 475
verifications. Spark was not reachable during the final census, so this document does
not claim that an unsynchronized remote-only artifact was inspected.

## Main Finding

The dominant problem is not a shortage of cross-candidate constraint rules. It is a
misplaced and overly coarse repair loop.

Current EnvSolve-Pro asks an independent model session to emit a complete cumulative
bootstrap program, replays that program in a fresh environment, summarizes the result,
and starts another model session. A strong coding agent instead makes many small
observations and state transformations inside one active conversation and one
construction environment. EnvSolve-Pro preserves reports across candidates, but it
breaks the reasoning continuity at the point where deployment repair actually happens.

In plain terms: the system keeps rewriting the whole deployment plan when it should be
testing and repairing the next uncertain step.

## Quantitative Evidence

### Candidate diversity is not useful progress

Across the 132 EnvSolve-Pro episodes, 502 of 512 scripts were exact-unique. Only 10
actions repeated an exact script. Exact duplicate suppression therefore cannot address
the main failure.

However, complete executable-goal snapshots contain 18 consecutive no-change
transitions across nine episodes. All observed semantic stagnation occurs in EnvSolve-Pro
methods. Scripts change while the verified missing-import set stays unchanged.

The execution-feedback-v3 screen makes this causal distinction concrete. Among seven
eligible pairs, treatment produced 0 wins, 6 ties, and 1 loss; Official Pass was 3 for
treatment and 4 for the simpler goal-frontier control. Treatment also produced six
stagnant complete-frontier transitions versus four for control. More failure categories
created more candidate variation, not more verified progress.

### The failure surface is operational

The 132 EnvSolve-Pro episodes record:

| Event | Count |
| --- | ---: |
| executable-verifier counterexample | 390 |
| command exit failure | 274 |
| candidate validation rejection | 27 |
| candidate-budget exhaustion | 23 |
| executable-verifier unknown | 16 |

This is not evidence that a closed command vocabulary is needed. The operation-relevance
contract could describe a valid repair, but it did not establish feasibility and did not
produce a treatment-only pass. Exact finding IDs also created projection and grounding
friction. The open terminal should remain.

### Structured mechanisms have not improved Official Pass

No adjudicated paired mechanism study reviewed here contains a reliable treatment-only
Official Pass gain:

| Mechanism | Valid Official result | Interpretation |
| --- | --- | --- |
| candidate retention | 1/3 vs 1/3 | improves terminal reach, not success |
| explicit vs raw goal state | completed valid pairs tied | possible compression signal only |
| persistent vs fresh construction | 4/5 vs 4/5 | reuse is real, no success gain |
| goal frontier | one eligible pair tied | treatment used more resources |
| bootstrap frontier v2 | 1/2 vs 2/2 | treatment loss |
| execution feedback v3 | 3/7 vs 4/7 | treatment loss |
| structured stateful V2.2 | 4/5 vs strong/raw 5/5 | hard semantic veto caused a loss |
| structured stateful V2.4 | 4/4 vs strong/raw 4/4 | repair loop never activated |

The causal-frontier v2 apparent gain is excluded because the exact frontier shown to the
model was truncated. Operation-relevance results are mostly infrastructure-censored;
their valid pairs are ties.

### Command status is not environment state

Codex traces include 2,224 container commands, 234 nonzero outcomes, and 17 timeouts.
Fifteen timeouts occurred during mutating or dependency commands. River and LitGPT show
that a timed-out install can leave a useful environment. LitGPT also shows the opposite
within the same transition: substantial packages were present, but a generated
executable was missing. The state was partly useful and partly damaged.

Therefore neither policy is sound:

- rollback every nonzero or timed-out command;
- preserve every partially completed command.

The decision must be made from executable postconditions after the transition.

## Case-Level Counterexamples

### Lark

The goal-frontier control reduced the complete finding set from seven to four, then two,
then zero. It changed installation strategy and finally solved the remaining QScintilla
binding.

Execution-feedback-v3 repeatedly returned to the same four PyQt findings while changing
`PYTHONPATH`, `.pth` files, Pyright configuration, system packages, and build paths. Some
operations violated protected surfaces. Twelve distinct whole programs did not recover
the successful control path.

### duckdb_engine

Both conditions repeatedly retained the same finding,
`sqlalchemy.base` in `duckdb_engine/__init__.py`. Later candidates changed SQLAlchemy
versions, stubs, temporary packages, and Pyright configuration without first answering a
local question: which installed layout, analyzer path, and package version actually
satisfies that import? The loop regenerated plans instead of probing that hypothesis.

### River and LitGPT

Native Codex did not pass the EnvBench public goal because it was not shown that goal,
so these are not effectiveness comparisons. They are useful operation traces. The agent
preserved a partially materialized environment, probed it, repaired toolchain or Python
compatibility, and migrated verified state without replaying every earlier command.

## Repo2Run Comparison

Repo2Run already has a persistent shell, command history, one-step Docker checkpoint,
and rollback after a nonzero mutating command. Checkpointing itself is therefore neither
new nor sufficient.

Its rollback decision is based primarily on shell return code. Pipelines can mask inner
failures, and timeouts can leave mutations without semantic adjudication. Its native
success target is `runtest` or `poetryruntest`, not EnvBench's public
`reportMissingImports` goal. The seven readable completed trajectories all fail Official
EnvBench evaluation, but objective mismatch prevents attributing those failures to its
checkpoint policy alone.

A Docker commit is a copy-on-write image layer on disk; Repo2Run's `mem_limit='2g'` is a
container memory cap, not 2 GB of snapshot memory. Even so, an unbounded branch frontier
would consume disk and management time. EnvSolve-Pro should not maintain many physical
environment branches.

## Hypothesis Decisions

### Reject as the next core mechanism

- more cross-candidate failure categories;
- hard semantic or provenance constraints above the public goal;
- exact-script no-good rules as the main solver;
- a multi-branch physical checkpoint frontier;
- automatic rollback or retention based only on exit status;
- another independent-session, whole-program candidate loop.

### Retain as supporting infrastructure

- the public executable goal and terminal-only Official evaluator boundary;
- repository integrity and effect auditing;
- full immutable trajectories for post-hoc research;
- best admissible script retention;
- fresh replay of the final self-contained bootstrap program;
- optional bounded checkpointing as an execution optimization.

## Revised Algorithm: ActiveState v1

The next EnvSolve-Pro should keep the three-layer architecture, but place it inside a
strong Agent's active session.

### Observation layer: what changed?

The harness records command output, public-goal output, repository effects, and compact
postcondition probes after meaningful state transitions. A timeout or nonzero status is
an observation, not a state verdict. Complete and partial observations remain distinct.

### Constraint layer: what is currently verified?

Maintain a minimal **verified-state ledger** rather than a growing rule library. Each
entry records a scoped predicate, one of `satisfied`, `violated`, or `unknown`, its
evidence, and the transition that last changed it. Only the executable goal and shared
integrity contract are hard. Package, version, platform, and provenance interpretations
are advisory until an executable probe supports them.

This is the simpler meaning of the earlier compatibility-frontier idea: keep a short
list of what has been proven to work, what is currently broken, and what has not yet been
checked.

### Operation layer: make the next repair

One strong Agent conversation controls one persistent construction environment through
an open terminal. It may inspect, install, migrate, or repair freely. After a risky
transition, the harness classifies the resulting state:

- **useful**: required postconditions hold and no verified invariant regressed;
- **damaged**: a previously verified invariant is now false;
- **unknown**: decisive probes did not complete.

The Agent receives the compact state delta, not a replacement conversation. It decides
the next operation. A failed fresh replay is also returned to the same session for
repair.

### Certification

When the active state satisfies the public goal, the Agent emits one self-contained
bootstrap program. The harness replays it in a fresh checkout, audits repository effects,
and runs the public goal. Only a clean replay can be submitted to the terminal Official
evaluator.

### Checkpoint policy

Physical checkpoints are optional and bounded to the base environment, current verified
state, and at most one pre-risk state. Roll back only when a postcondition proves damage.
Unknown state is probed before rollback. Checkpointing is not the paper's core claim.

## Required Mechanism Gate Before Implementation Expansion

The active-session hypothesis has strong indirect evidence but has not been tested on
the hard DeepSeek screen under the same public goal. The next experiment should first
run the frozen strong single-session goal-aware Codex baseline on a small consumed set,
such as Lark, duckdb_engine, Meerkat, Pysnmp, River, or LitGPT. These runs are for
trajectory observation only.

Proceed to ActiveState v1 only if hard failures show at least one of the following:

- the Agent discovers a useful partial state that whole-program replay discards;
- a local probe changes the next operation without requiring a new conversation;
- a damaging transition is identifiable from postconditions rather than exit status;
- fresh certification fails and the same session repairs the synthesized program.

If the strong goal-aware Agent already solves these cases, EnvSolve-Pro must demonstrate
incremental value over that baseline rather than repackage its loop.

## Evaluation Design After the Gate

Freeze the implementation before selecting repository-disjoint cases. Compare, with the
same strong model and public goal:

1. strong single-session goal-aware Agent;
2. raw active-session Agent with identical tools and no structured ledger;
3. EnvSolve-Pro ActiveState v1;
4. external Repo2Run and Codex baselines under clearly reported native or aligned goals.

Official Pass is primary. Secondary outcomes are failure-conditioned recovery,
fresh-replay certification, verified-regression count, damaging-transition recovery,
commands, time, tokens, and dependency traffic. Tokens and cost are reported metrics,
not success-stopping thresholds.

## Final Judgment

EnvSolve-Pro should not become a larger collection of cross-candidate rules. Its next
testable contribution is a small stateful control layer around a strong active Agent:
observe each environment transition, retain only executable facts, repair in place, and
certify once from a clean checkout.

This conclusion preserves the Observation-Constraint-Operation research thesis while
removing the machinery that has repeatedly failed to improve Official Pass.

The machine-readable adjudication is
`experiments/validations/pro_all_trajectory_reassessment_v1_adjudication.json`.
