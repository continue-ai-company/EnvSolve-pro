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
| P2 (complete) | Identify the dominant contradiction | Cross-method failure decomposition | One frequent, actionable, non-harness bottleneck |
| P3 (complete) | Qualify candidate retention | Certified/admissible state and paired consumed replay | Terminal reach `2/3` vs `1/3`; no Official Pass gain |
| P4 (complete) | Quantify the remaining contradiction | Two independent eight-case Dev censuses on Spark | Single-layer replication failed; interface-level signal frozen |
| P5 (in progress) | Design one minimal intervention | Fresh paired Dev validation | Positive Official Pass or preregistered mechanism signal |
| P6 | Broaden, freeze, and confirm | Multi-model Dev, Canary, Official Test, and paper tables | Code, prompts, baselines, and metrics frozen |

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

### 4.3 P2 Frozen Diagnostic Design

P2 draws six metadata-only cases from the remaining 118 untouched Dev pool and executes
24 salted positions: Codex native, Repo2Run, raw ReAct, and the P1 EnvSolve-pro scaffold.
The primary analysis unit is the earliest decisive repair opportunity, attributed to
Observation, Constraint, Operation, or unresolved. A new mechanism requires the same
actionable contradiction in at least three repositories and two methods. The complete
batch is immutable; no solver or wrapper change is allowed after selection.

### 4.4 P2 Audit Decision

All 24 positions completed. The batch is not an effectiveness comparison because most
Codex and Repo2Run positions, plus two raw-ReAct positions, were censored by baseline
adapter or integrity failures. EnvSolve-pro and raw ReAct each produced one official
pass on different repositories; reporting these as comparable 1/6 rates would be invalid.

The dominant deterministic contradiction occurred in three repositories: an
integrity-valid candidate completed internal execution with exit code zero, yet any
residual internal constraint caused EnvSolve to discard it without terminal evaluation.
Partial internal evidence had become an exact terminal oracle. P3 therefore introduces
one minimal distinction: **certified** candidates satisfy the internal goal, while
**admissible** candidates completed a safe replay but retain unresolved internal
constraints. The solver keeps the best admissible candidate and may emit it as
`uncertified`; the official evaluator remains terminal-only and the internal goal remains
blocked.

A second cross-repository pattern concerns runtime, dependency-lock, and platform
compatibility. It remains a preregistered secondary hypothesis. P3 does not implement it
until the smaller candidate-retention mechanism is qualified.

### 4.5 P3 Qualification Decision

Candidate retention passed its consumed-case qualification: the treatment reached
terminal evaluation on `2/3` cases versus `1/3` without retention. Official Pass remained
`1/3` in both conditions. The only retained-candidate release was explicitly uncertified,
kept the internal goal blocked, and failed officially with 22 remaining issues. This
qualifies retention as a terminal-censoring repair, not as an effectiveness result.

Before implementing runtime closure or another mechanism, P4 blindly samples eight
fresh Dev cases and classifies complete trajectories as operation nonviability,
observability gap, closure gap, evaluator gap, or success. No algorithm change is allowed
until the aggregate is frozen.

### 4.6 P4 Census Decision

The primary census was led by closure gaps (`4/8`), while an independently selected
replication was led by operation nonviability (`4/8`). The preregistered single-category
replication criterion therefore failed. The stable result is one level higher: operation
and closure jointly account for `6/8` and `5/8` cases, or `11/16` pooled. Mechanism audit
attributes these labels to three recurring causes: missing runtime/platform frontiers,
flat surface obligations without scope or causal parentage, and an effect/evaluator trust
boundary that is both over-strict and spoofable. Twelve cases reached the five-candidate
cap, confirming that it was a binding diagnostic limit rather than a suitable main
protocol.

P5 first repairs the measurement trust boundary without claiming algorithmic gain. It
then tests one minimal causal constraint-frontier mechanism that keeps raw evidence
available, promotes only grounded root conditions, attaches scoped symptoms to their
causes, and leaves the strong model's action space open.

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

Finish protected-evaluator and virtual-environment effect-audit repairs, then freeze a
preregistered mechanism test for the causal constraint frontier. Qualify it first on
synthetic and consumed counterexamples, and only then run an outcome-blind paired Dev
sample. Candidate and token caps must be generous enough to remain nonbinding; shared
wall-clock and container resources define the comparison boundary.
