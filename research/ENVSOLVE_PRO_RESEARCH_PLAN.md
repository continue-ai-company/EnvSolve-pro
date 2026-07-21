# EnvSolve-pro Research Plan

## 1. Objective

EnvSolve-pro studies automatic environment construction for unfamiliar repositories.
The core framing remains unchanged: deployment is a **partially observable,
stateful constraint-solving process**, organized as a three-layer loop:

1. **Observation: what happened?** Preserve repository evidence, execution outcomes,
   environment identity, and uncertainty.
2. **Constraint: what is missing or conflicting?** Maintain provenance-linked facts,
   hypotheses, contradictions, and unresolved obligations.
3. **Operation: how can the environment resolve them?** Let a strong model propose a
   complete deployment program, then validate execution boundaries and state transitions.

EnvSolve-pro inherits the complete EnvSolve v1 code and Git history. The original
`hongleo-Lee/EnvSolve` repository is archived at commit `07a208f` under tag
`envsolve-v1-baseline-freeze-2026-07-21` and remains a runnable baseline. All new
development belongs to `hongleo-Lee/EnvSolve-pro`.

## 2. Research Principles

### 2.1 Success first

Official Pass@1 and clean replay are the primary objectives. Tokens, model calls,
containers, commands, and wall-clock time are efficiency measurements, not part of
the problem definition. Only broad runaway and safety limits terminate the main
protocol. Confirmatory experiments additionally report success-resource curves;
dollar cost is not a primary scientific variable.

### 2.2 Structure augments model reasoning

Strong models retain access to bounded raw observations. The constraint layer is a
provenance-aware external state, not the model's only context. Deterministic hard guards
cover task boundaries, safety boundaries, and exact behavior contradicted by grounded
execution evidence. Other constraints remain revisable beliefs or advice. The model may
propose operations outside the current schema, and execution determines whether the
state should expand.

### 2.3 Baseline first

Before another algorithm change, run Repo2Run, Codex/native agent, and same-backbone
raw ReAct end to end. Source inspection explains implementations but cannot replace
observing full trajectories. Container strategy, feedback loops, stopping decisions,
and recovery behavior must enter a shared trajectory analysis.

### 2.4 Prevent development-set overfitting

Separate diagnostic and validation cases. Each mechanism needs support from a
cross-repository failure pattern or a repository-free counterexample before an
outcome-blind Dev batch tests it. Consumed cases remain diagnostic only. Canary and
Official Test stay untouched until the algorithm, baselines, and analysis are frozen.

### 2.5 Parallel development platforms

Mac and DGX Spark may run Dev cases in parallel. Every trajectory records platform,
architecture, image digest, network state, and provider. Host OS is not an algorithmic
variable during development; paired comparisons should use the same execution image
and platform where possible. Cross-platform consistency is tested separately after the
mechanism stabilizes.

## 3. Audit of Inherited Assets

Keep the benchmark-independent runner, EnvBench adapter, terminal-only evaluator
boundary, fresh environments, artifact audit, schedule coordinator, append-only state,
evidence provenance, baseline runners, summarizers, and tests.

Retain but re-qualify the evidence schema, fixed confidence threshold, domain-to-
operation mapping, typed replay validator, operation guard, and transcript compression.
These are policy choices and ablation targets, not the definition of EnvSolve.

## 4. Experimental Roadmap

| Phase | Goal | Main artifact | Gate |
|---|---|---|---|
| P0 | Observe external baselines | Unified Repo2Run, Codex/native, and raw-ReAct trajectories | At least five new audited Dev cases per method |
| P1 | Establish fair interfaces | Shared cases, evaluator access, observations, and resource reporting | Wrappers preserve native baseline behavior |
| P2 | Identify the dominant contradiction | Cross-method failure decomposition | One frequent, actionable, non-harness bottleneck |
| P3 | Design the minimal three-layer method | Pluggable layer interfaces and ablations | Counterexample, tests, and preregistered prediction |
| P4 | Small paired validation | At least five unseen Dev pairs | Positive success or terminal-repair signal |
| P5 | Broader Dev validation | Multi-case, multi-model, Mac/Spark evidence | Effect persists across cases and models |
| P6 | Freeze and confirm | Canary, Official Test, and paper tables | Code, prompts, baselines, and metrics frozen |

P0 must not produce repository-specific rules from consumed EnvSolve v1 cases. A new
parser, constraint, or guard requires multiple independent trajectories or a deterministic
invariant of the task definition.

## 5. Core Ablation

With a fixed backbone, compare raw-history ReAct; ReAct with structured Observation;
Observation plus advisory Constraint state; advisory state plus grounded hard guards;
and the frozen EnvSolve v1 baseline. Repeat across at least two model capability levels.
If stronger models erase or reverse the benefit of hard planning, reduce the hard
mechanism and locate the contribution in verified state, execution feedback, and
recovery rather than action-space restriction.

## 6. Metrics

The primary metric is Official Pass@1. Secondary outcomes are terminal reach,
post-failure repair success, clean replay, repeated-failure rate, and infrastructure
censoring. Resource metrics report input/output tokens, requests, candidate environments,
commands, and wall-clock time. Report paired effects and confidence intervals. Internal
verification supplies online feedback; the Official evaluator remains terminal-only.

## 7. Immediate Next Step

Pause expansion of the v1 internal ablation. Freeze a small untouched Dev batch and run
real Repo2Run, a native strong agent, raw ReAct, and frozen EnvSolve v1. Inspect every
trajectory. P0 should output an evidence-backed dominant contradiction and the smallest
P3 algorithm hypothesis, not another collection of rules.
