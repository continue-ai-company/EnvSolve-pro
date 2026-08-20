# Target-State Counterexample Replay: Consumed Mechanism Check

Status: complete, 2026-08-20

## Question

Does whole-program replay from the real target cache state expose useful executable
counterexamples to the same active Agent session? This is a three-case check on selected,
previously consumed development cases. It is not an effectiveness or generalization
experiment.

## Result

All three final replay-certified programs passed EnvBench Official. Basxconnect and
Graphium exercised the intended repair loop; cvxportfolio passed its first cold replay.

| Case | Replay sequence | Same-session repair | Official |
|---|---|---:|---:|
| basxconnect | Fail -> Pass | yes | Pass |
| graphium | Fail -> Fail -> Fail -> network Fail -> Pass | yes | Pass |
| cvxportfolio | Pass | no, certification only | Pass |

Across the three episodes, the Agent made 139 model requests, 137 shell operations, and
used 3,133,930 tokens. Eight clean replays produced five failures and three final passes.
Two transient provider connection errors occurred in Graphium and recovered inside the
same session.

## Causal Evidence

Basxconnect replay reproduced the missing Git ownership operation. The Agent added a
repository-root-relative `safe.directory` command, after which replay and Official both
passed.

Graphium is the stronger result. Its old warm replay had passed while Official failed.
Cold replay instead exposed, in order: an unavailable torchvision version, missing Git
ownership handling, and omitted test dependencies. Each failure returned to the same
session and changed the complete program. One later Conda download failed with `HTTP
000`; this was treated as network evidence, not converted into a compatibility rule.
The next replay and Official both passed.

Cvxportfolio passed both cold replay and Official. Its earlier package-index failure did
not recur, so the evidence does not justify a package-specific repair rule.

## What This Does Not Show

The cases were chosen because their old trajectories exposed replay problems. A 3/3 pass
therefore does not estimate expected success. There is no paired control in this check,
and there is one realization per case.

Path quality also remains unsolved. Graphium used 82 requests, 2.32M tokens, about one
hour of generation time, and a 1.2 GiB construction cache. The Agent autonomously
recovered from an accidental CUDA dependency path, but only after substantial download
traffic. Official success and deployment completeness also remain distinct because the
ARM result uses a PopTorch compatibility module rather than an IPU runtime.

## Decision

Retain the simplest candidate algorithm: one free continuous Agent session plus repeated
whole-program target-state counterexample replay. Do not add package rules, scheduled
observation, checkpoints, cross-case memory, or new hard operation constraints.

The next step is an outcome-independent preregistered qualification batch with a
same-model control. Official Pass@1 is primary; path quality is a separate outcome.
