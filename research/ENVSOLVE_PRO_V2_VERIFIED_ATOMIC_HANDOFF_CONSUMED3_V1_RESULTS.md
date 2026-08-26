# EnvSolve-Pro V2 Verified Atomic Handoff: Consumed-3 Results

## Question

When a trusted full-goal check says the construction environment is ready, can immediate
atomic delivery preserve that candidate and return fresh-state failures early enough for
the same Agent session to repair them?

The three cases were selected because earlier consumed trajectories exhibited a
goal-to-delivery gap. This is mechanism qualification on outcome-conditioned development
cases, not a held-out effectiveness estimate.

## Result

The coupled mechanism activated on all three cases, and every first submission followed
the first trusted goal Pass by one model request.

| Case | First goal Pass | First submit | Replay sequence | Original Official | Attribution |
| --- | ---: | ---: | --- | --- | --- |
| Quacc | request 26 | request 27 | Unknown, Fail, Pass | Pass | direct treatment outcome |
| Ajenti | request 96 | request 97 | Fail | Fail | old harness boundary; censored |
| Hark | request 16 | request 17 | Fail, Pass | Pass | direct treatment outcome |

The original endpoint is `2/3` Official Pass. Ajenti is not retroactively changed to a
Pass. A separately specified, no-model adjudication replayed its exact request-97 program:
the corrected clean replay passed with zero missing imports, and the unchanged Official
evaluator also passed. The original failure is therefore retained but excluded from
algorithm-effect attribution as harness-boundary-induced.

## Mechanism Evidence

Quacc shows why early target-state feedback matters. Its first replay timed out while
building an over-complete environment. Its second candidate over-minimized dependencies
with `--no-deps` and failed imports. The same session restored full CPU-compatible
dependencies, kept selective no-deps installs only where needed, and passed its third
clean replay and Official evaluation. Relative to the independent historical atomic
rollout, requests fell from 120 to 60, tokens from 5.55M to 2.69M, and the outcome changed
from Fail to Pass. Those differences are directional, not paired causal estimates.

Hark's first replay exposed a missing fresh-checkout operation: Git rejected the checkout
as dubious ownership. After replay failure restored unrestricted tool choice, the Agent
voluntarily resubmitted on the very next request with `safe.directory`; replay and
Official passed. Relative to its historical successful rollout, requests fell from 37 to
18 and tokens from 0.58M to 0.20M.

Ajenti exposes a measurement failure rather than a deployment failure. Python 3.10
distribution metadata omitted ordinary packages without `top_level.txt`, and the old
provenance check did not recognize modules owned by the operating-system package manager.
It rejected a candidate that had already completed bootstrap and the full goal. The
Agent then discarded the working environment and exhausted its session. The corrected
boundary recognizes exact installed-distribution files and fixed-path system-package
ownership while still rejecting manually introduced unowned providers.

## Decision

The consumed mechanism is qualified: scheduled trusted observation can identify a usable
construction state, atomic handoff removes delivery delay, and replay failures create
executable case-local constraints without choosing the Agent's repair. This supports a
simple three-layer algorithm:

1. **Observation:** periodically run the complete trusted goal and replay submitted
   programs from the target initial state.
2. **Constraint:** represent goal residuals and replay failures as case-local executable
   facts.
3. **Operation:** leave inspection and repair unrestricted inside one continuous Agent
   session; force only delivery of a candidate that already passes the trusted goal.

The next experiment freezes this coupled mechanism and compares it prospectively with a
matched `F+O` control on an outcome-blind, repository-disjoint bad-case batch. No package
rules, checkpoints, cross-case memory, or harness-selected repair actions are added.

Machine-readable result:
`experiments/validations/envsolve_pro_v2_verified_atomic_handoff_consumed3_v1_result.json`.

