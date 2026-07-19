# P6 V3 Unseen Dev-5 Qualification V1

Status: preregistered before case selection, repository inspection, model execution,
or official evaluation.

## Objective

Test whether static-source evidence corrects runtime-only internal-Pass
miscalibration without changing the model, repository information, execution probe,
candidate language, fresh-environment policy, or total budget. This is development
qualification, not confirmatory evidence.

## Outcome-blind selection

- Population: `experiments/cases/train_untouched201.jsonl` at SHA256
  `076ef72dbab0bb5cdefa72b10b2a84d4391914716fb640c5ab5f579b46677bfe`.
- Salt: `envsolve-p6-v3-qualification-v1-2026-07-16`.
- Rank ascending by
  `SHA256(salt + \"\\0\" + case_id)` and select the first five cases.
- Selection reads only frozen case metadata. Repository source, package metadata,
  previous trajectories, and evaluator outcomes are forbidden before selection.
- Selected cases become permanently development-only and are removed from the
  remaining untouched-training pool. Canary-20 and Official-Test-100 remain
  untouched.

## Paired methods

Each selected case receives two independent episodes:

1. `envsolve-runtime-only`: V3 inventory and probe, but only runtime-semantic
   evidence may enter the obligation state.
2. `envsolve-full`: the identical implementation with runtime-semantic and
   static-source evidence.

Both methods use `deepseek/deepseek-v4-pro`, temperature zero, the same frozen
pricing, the same five-candidate and global token/request/cost/time budgets, the
same candidate DSL, and fresh containers. They do not share trajectories,
containers, ledgers, or generated scripts. Within each case, method order is
determined before execution by salted hashing.

## Evaluation boundary

The official evaluator may be claimed exactly once per method-case pair and only
after that episode terminates. Its output is terminal and cannot enter either
method's state. Network, artifact, and harness-timeout outcomes remain Unknown and
produce no repair constraint.

## Recorded outcomes

- internal Pass, Fail, or Unknown and candidate index;
- official Pass and missing-import count;
- active and unknown findings by obligation layer;
- repair transitions, repeated constraints, environments, wall time;
- model requests, tokens, and estimated cost;
- audit validity and clean replay.

## Qualification interpretation

This five-case batch cannot establish a leaderboard or paper-level effectiveness
claim. V3 is mechanism-qualified only if all runs pass audit and, whenever the
runtime-only condition reaches an internal Pass that fails terminal static import
evaluation, V3 exposes the corresponding failure before internal Pass or correctly
returns Unknown. Official Pass count, cost, and candidate count are reported
descriptively. Any V3 regression triggers generic error analysis and synthetic
counterexamples; selected-case names or outcomes may not become repair rules.

## Freeze requirement

The selected split, remaining untouched pool, method switch, protocol, tests, and
selection provenance must be included in a new valid harness freeze before the
first model request.
