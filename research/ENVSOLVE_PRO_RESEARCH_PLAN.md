# EnvSolve-Pro Research Plan

## 1. Objective

EnvSolve-Pro studies automatic environment construction for unfamiliar repositories.
The core framing remains unchanged: deployment is a **partially observable,
stateful constraint-solving process**, organized as a three-layer loop:

1. **Observation: what happened?** Preserve repository evidence, execution outcomes,
   environment identity, and uncertainty.
2. **Constraint: what is missing or conflicting?** Maintain provenance-linked facts,
   hypotheses, contradictions, and unresolved obligations.
3. **Operation: how can the environment resolve them?** Let a strong model propose a
   complete deployment program, then validate execution boundaries and state transitions.

EnvSolve-Pro inherits the complete EnvSolve v1 code and Git history. The original
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
| P5 (complete) | Qualify a causal constraint frontier | V2 measurement rejection and V3 integrity repair | Retained as a diagnostic baseline; no effectiveness claim |
| P6 (complete) | Observe all methods against the official objective | Sixteen consumed repositories across causal-v3, Codex, and Repo2Run | One cross-method, repository-independent contradiction |
| P7 (in progress) | Qualify executable goal-grounded state | Freeze `goal-contract-evidence-anchor-v1`, then run repository-disjoint qualification | Goal fidelity, multi-round repair, and no evaluator leakage |
| P8 | Controlled effectiveness and freeze | Goal-aware baseline pairs, untouched Dev, Canary, and Official Test | Code, prompts, goals, baselines, and analysis frozen |

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
24 salted positions: Codex native, Repo2Run, raw ReAct, and the P1 EnvSolve-Pro scaffold.
The primary analysis unit is the earliest decisive repair opportunity, attributed to
Observation, Constraint, Operation, or unresolved. A new mechanism requires the same
actionable contradiction in at least three repositories and two methods. The complete
batch is immutable; no solver or wrapper change is allowed after selection.

### 4.4 P2 Audit Decision

All 24 positions completed. The batch is not an effectiveness comparison because most
Codex and Repo2Run positions, plus two raw-ReAct positions, were censored by baseline
adapter or integrity failures. EnvSolve-Pro and raw ReAct each produced one official
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

### 4.7 P5 Causal Constraint Frontier

P5 adds neither a closed planner nor case-specific rules. It replaces the flat
obligation projection with a read-only derived view:

```text
provenance-linked raw observations
-> current scope updated per observation channel
-> executable root conditions and surface-to-root edges
-> an unrestricted next deployment program from the strong model
```

Observation channels do not share a destructive global timestamp. If a new candidate
fails before the module probe, the last observed module root remains partially observed;
if a newer module probe shows that the root disappeared, it leaves the current frontier.
The frontier does not mutate hard constraints, discard raw events, or restrict actions.

Offline qualification on the two consumed P4 batches groups `93/94` surface module
obligations into `37` executable roots, with a maximum `25:1` surface amplification.
Full raw artifacts also contain seven exact PyO3/Python compatibility observations in
two repositories that the old bounded state did not retain reliably. This establishes a
cross-repository representation mechanism, not an effectiveness result.

The V1 implementation at `8e79eab` exposed three measurement failures rather than a
valid effect estimate: roots were retired by silence, shell control flow could bypass
postconditions, and host effect auditing could follow container-only interpreter links.
These artifacts remain diagnostic and are not pooled with later outcomes. V2 freezes the
smallest generic repairs at `d250549dd29745887fe7fd1db4026b4d37aca384` and repeats the
same consumed pairing under `pro_p5_causal_frontier_paired_v2_preregistration.json`.
The model, verifier goal, open-program interface, candidate retention, and evaluator
boundary remain fixed; only flat versus causal state differs. Fresh outcome-blind Dev
cases are consumed only after the preregistered integrity and mechanism gate passes.

After the V2 infrastructure retries completed, the frozen analysis still failed its
measurement gate. The three causal episodes persisted 16 model decisions; LangGraph
candidate 2 stored a whole-frontier truncation wrapper rather than a structured object
containing `causal_roots`. A separate posthoc audit identifies exactly this one invalid
decision and sets both measurement integrity and effect admissibility to false. The
apparent causal `1/3` versus flat `0/3` Official Pass difference is therefore diagnostic,
not an algorithmic gain.

The minimal V3 repair versions the complete internal frontier separately from its model
projection. The bounded projection packs causal roots before descriptive environment
facts, reports omitted counts, and never truncates the whole JSON object. A shared generic
verifier correction also evaluates tuple guards over `sys.version_info`, preventing an
inactive compatibility import from becoming an obligation on newer Python. V3 first runs
an integrity-only canary on the same three consumed cases; Official Pass is not part of
this gate. A multi-block flat/causal experiment is frozen only after every model-visible
decision passes digest, schema, structure, and root-completeness checks.

### 4.8 Cross-Method Trajectory Census

The next algorithm revision is selected from paired trajectory statistics rather than
another isolated case. The complete union of the two consumed P4 censuses supplies 16
repositories without opening untouched data. Current EnvSolve-Pro causal-v3, Codex CLI,
and Repo2Run run on the same case identities and unchanged terminal evaluator. The
official objective is exactly bootstrap exit zero plus zero `reportMissingImports`;
other Pyright errors are excluded from mechanism selection.

For each case, analysis identifies the earliest decisive divergence at Observation,
Constraint, Operation, Finalization, or Infrastructure. A next-version mechanism requires
one unique largest category across at least four repositories and a repository-independent
counterexample. Mac runs Codex while Spark runs EnvSolve-Pro and two disjoint Repo2Run
lanes. The batch is diagnostic and cannot support a held-out or leaderboard claim.

An objective-alignment audit on the two earlier consumed censuses found that nine
comparable accepted candidates covered `40/41` official missing-import modules, but
30 of 70 internal module obligations were not official missing imports. Twenty-five
of those excess obligations came from one repository. This is a precision hypothesis,
not yet a dominant mechanism: it must recur as the earliest decisive divergence across
repositories in the frozen cross-method census.

### 4.9 P6 Cross-Method Decision

The completed census identifies one simpler contradiction than another dependency rule:
the executable task goal is not a continuously visible, authoritative state variable.
Native agents often optimize repository tests or documentation proxies without executing
the scoring target. Causal-v3 does execute a rich internal verifier, but semantic
inference can deactivate a real goal obligation or preserve a non-scoring one. The c14
Codex state-parity adjudication confirms that a nominally successful generation can still
contain 37 official missing-import diagnostics when Pyright never runs.

This decision retires the causal frontier as the center of the paper. It remains a
frozen structured baseline and an optional ablation. The next method must first ground
state in the public executable success criterion; semantic compression may annotate that
state but may not override it.

### 4.10 P7 Executable Goal Contract

`EnvSolve-Pro goal-contract-v1` introduces one generic interface. A versioned executable
goal contains a public description, trusted program, report schema, and content digest.
For each candidate, the verifier executes the complete deployment program and the goal
in the same fresh shell. A valid report yields Pass or typed Fail findings; malformed
reports, missing capabilities, and infrastructure incidents yield Unknown. Goal findings
enter the Constraint layer as authoritative active obligations until a later execution
discharges them. Every report also marks its finding set as complete or partial. Only a
complete same-scope snapshot can discharge a prior finding by absence; partial evidence
cannot. The strong model still emits an unrestricted Bash program.

The EnvBench adapter instantiates the public criterion as bootstrap success plus zero
`reportMissingImports`; Pyright-specific code remains outside the generic runtime. The
Official evaluator is terminal-only and never feeds the loop. To isolate objective
visibility from structured state, `codex-cli-goal-aware` receives the same public goal but
no typed constraint loop.

The first consumed qualification case, `jaraco/irc`, reached Official Pass with zero
scoring issues. This establishes end-to-end compatibility only. A second consumed case,
`censys/censys-python`, is selected because frozen causal-v3 lost its sole
`sphinx_rtd_theme` obligation. It tests whether a first-round executable goal failure
persists into a targeted second-round operation.

Both explicit-state and same-model goal-aware raw-history runs repaired c10 on the second
candidate and passed officially. The raw baseline did so with fewer tokens and less time
in this single pair, so c10 supports executable goal feedback but not an incremental
structured-state gain. The audit also found and repaired a stale-state bug: after a goal
Pass, constraints from the same versioned evidence scope are now explicitly superseded.
The first c15 diagnostic then exposed the corresponding Fail transition: an exhaustive
report had resolved three of four findings, but their old requirements remained active.
The report contract now distinguishes complete finding snapshots from partial evidence;
the pre-fix pair is invalid for comparison.

Subsequent integrity-valid c15 runs exposed two partially observable state failures:
goal findings did not include the repository-local build semantics needed to resolve a
dynamic test package, and newer candidates forgot dependencies that earlier candidates
had already satisfied. `goal-contract-evidence-anchor-v1` addresses these with bounded
finding-routed source evidence and a retained, fully executed admissible candidate
anchor. It leaves the Bash action space open. The resulting c15 mechanism run passed
Official evaluation with zero scoring issues after 11 candidates.

On consumed c16, explicit-state and same-model raw-history variants with the same source
evidence and anchor both passed officially in three executed candidates. The explicit
variant used 3 model requests and 40,438 tokens; raw history used 4 requests and 90,748
tokens, including one schema-invalid response rejected before execution. This single
pair supports neither a success-rate nor candidate-count advantage. It motivates a
preregistered test of whether explicit state reduces model-side context and retry burden
on multi-finding cases. None of these cases is held-out evidence; details are recorded in
`PRO_GOAL_CONTRACT_CASEBOOK_V1.md`.

### 4.11 Postcondition-Gated State Reuse

A repository-disjoint five-case qualification compared persistent explicit state,
fresh explicit state, and persistent raw history under the same model, goal, prompt
family, terminal evaluator boundary, and limits. All 15 episodes were integrity-valid
and scientifically eligible. Every condition passed the same four repositories and
failed `openqasm/openqasm`, yielding `4/5` Official Pass for each condition. The
preregistered gate therefore retains the state-reuse mechanism because reuse was
executable and auditable, but it provides no evidence of an Official Pass gain.

The mechanism was exercised rather than merely present: persistent explicit state
recorded six reused-construction verifications, and two reused lineages eventually
produced clean-replay passes. Against persistent raw history, explicit state used 19
rather than 27 candidates, 339,479 rather than 483,988 tokens, and 4,361 rather than
9,064 generation seconds. Against fresh explicit search, however, it used 19 rather
than 21 candidates and fewer tokens, but more wall-clock time because easy cases paid
for mandatory clean replay. With five repositories and one stochastic seed, these are
diagnostic resource differences, not an efficiency claim.

`openqasm` isolates the next algorithmic contradiction. All three conditions retained
a candidate with seven official issues and failed. Explicit persistent state reached
that boundary in roughly half the generation time of persistent raw history, but then
repeated infeasible ANTLR-generation paths and integrity-invalid attempts to materialize
import artifacts. The next method change must therefore improve the Operation layer,
not add more state types. Operation-relevance contract v1 is now implemented as an
isolated post-freeze method. Each candidate names the active executable finding it
targets, cites model-visible evidence for its preconditions, predicts a finding delta,
and declares an open operation-family identity. The harness rejects stale references,
conclusively failed exact scripts, and same-family retries without newly cited evidence;
the next complete goal snapshot produces a progress certificate. V1 deliberately does
not claim to prove arbitrary shell semantics or external-provider availability.

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
Logical model calls and provider transport attempts are reported separately.

Pass@1 distinguishes method non-submission from external censoring. A method that reaches
a frozen candidate, context, or generation limit has not produced a passing answer and
is a primary non-pass, even though its unresolved task state remains Unknown. Provider,
network, evaluator, and measurement failures are externally censored and may be retried
only under a frozen identical-episode amendment.

Dependency caching is method-independent experimental infrastructure, not algorithm
memory. Compared methods must receive the same initial cache snapshot and client image;
their identities are attested before a batch. Cache mode and network bytes are reported
as resource settings and outcomes. A frozen retry cannot adopt a new cache after seeing
source outcomes.

## 7. Immediate Next Step

Operation-relevance contract v1 remains frozen. In the DeepSeek-direct replication, the
first eligible pair was Pass/Pass on Django and the second was Nonpass/Nonpass on Trax.
The treatment used fewer candidates on Trax but repeated the same broad, infeasible
installation family, so this is not evidence of a Pass@1 gain. The UER-py pair and all
later positions were externally censored as VPN degradation produced package-network,
provider-transport, and repository-acquisition failures.

Positions 1-4 are immutable. Positions 5-10 have a new-ID, same-order network retry
schedule that preserves algorithm, model, provider, prompt, seed, config, protocol,
platform, and budgets. The new dependency cache is intentionally disabled for this
retry because adding it would change the frozen setting. Execution resumes only after
provider, Hugging Face, PyPI, Ubuntu, and VPN-capacity preflights pass.

After closure, analyze Official Pass@1 first. If the operation contract does not improve
cross-repository success, archive it as an auditable structured baseline. Its consumed
trajectories currently motivate a simpler next hypothesis: an operation must establish
package/platform feasibility and bounded execution progress, rather than merely cite a
broad goal finding. No redesign may use a qualification outcome before the frozen
comparison closes, and no rule may be tuned to `openqasm` or another individual case.

### 7.1 Dependency-Cache Engineering Qualification

The method-independent cache passed a strict functional canary on the exact EnvBench
Python base image. A fresh container installed one PyPI and one Ubuntu package in 151.63
seconds from direct networks, 191.98 seconds through an initially empty cache, and 12.28
seconds from a warm cache while both cache services were forced offline. Offline warm
replay was therefore 12.35 times faster than direct installation; the cold cache added
26.61% overhead.

This result qualifies the cache as shared experimental infrastructure, not as an
EnvSolve-Pro effect. The full canary binds image identities, configuration hashes, cache
content, process-level offline flags, and apt input/output evidence. Whole-machine
network counters remain descriptive because they include unrelated traffic. A
representative EnvBench trace is still required before estimating batch-scale traffic
reduction, and the frozen DeepSeek-direct retry remains cache-disabled.
