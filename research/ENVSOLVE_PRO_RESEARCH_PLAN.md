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
| P1 (complete) | Establish fair interfaces | Open programs, fresh execution, effect audit, and adapter preconditions | Six consumed trajectories compile without representation rejection |
| P2 | Identify the dominant contradiction | Cross-method failure decomposition | One frequent, actionable, non-harness bottleneck |
| P3 | Design the minimal three-layer method | Pluggable layer interfaces and ablations | Counterexample, tests, and preregistered prediction |
| P4 | Small paired validation | At least five unseen Dev pairs | Positive success or terminal-repair signal |
| P5 | Broader Dev validation | Multi-case, multi-model, Mac/Spark evidence | Effect persists across cases and models |
| P6 | Freeze and confirm | Canary, Official Test, and paper tables | Code, prompts, baselines, and metrics frozen |

P0 must not produce repository-specific rules from consumed EnvSolve v1 cases. A new
parser, constraint, or guard requires multiple independent trajectories or a deterministic
invariant of the task definition.

### 4.1 P0 Audit Decision

The five-case P0 batch is complete. Across 20 scheduled method positions, no official
pass was observed, but the batch is not an effectiveness estimate: four Codex positions
became Unknown after executable drift, and wrapper behavior independently censored
native trajectories. Repo2Run and raw ReAct each solved two cases in their native
environment; frozen EnvSolve internally accepted two fresh-container plans. Three of
those native successes did not reach an equivalent official execution because replay
lost a successful operation or its ambient runtime. Both EnvSolve acceptances also
exposed an internal-versus-terminal contract mismatch.

The dominant P0 contradiction is therefore methodological: a strong native solver can
construct a working environment while a closed post-hoc command parser or mismatched
verification workspace erases that success. P1 must repair this interface before P2
attributes remaining failures to the deployment algorithm.

P1 follows a minimal principle: treat the model's complete candidate program as open,
execute it in an isolated fresh environment, and judge safety and correctness from
audited effects and executable postconditions. Command schemas remain useful for state
summarization and causal replay, but an absent schema entry is not itself proof that a
candidate is invalid. Benchmark adapters must declare workspace preconditions so that
internal and terminal executions begin from equivalent non-outcome state.

### 4.2 P1 Audit Decision

P1 is complete. All six frozen Raw ReAct and Repo2Run trajectories compiled without an
unsupported operation. Five final official replays reached terminal evaluation with no
representation rejection; none passed officially. This negative effectiveness result is
informative: the fair interface exposes genuine residual Pyright failures, a mismatch
between native tests and the benchmark target, and a `build_output/` package-discovery
conflict instead of hiding them behind Unknown.

The frozen EnvSolve `importlib_metadata` candidate also failed internally once the
adapter-declared `build_output/` precondition was materialized. Therefore P1 resolves
the measurement contradiction predicted from P0 without adding a repository-specific
solver rule. Detailed evidence is separated into
`PRO_P1_FAIR_INTERFACE_RESULTS_V1.md`; these consumed cases cannot support the next
effectiveness claim.

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

Freeze the qualified P1 interface in Git, then start P2 with a reproducible salted sample
from the remaining 118 untouched Dev cases. Run the frozen external baselines and the
open-interface EnvSolve scaffold without outcome-driven code changes. Decompose complete
trajectories by Observation, Constraint, and Operation failures, and select one dominant
cross-repository contradiction before designing the first new algorithmic mechanism.
