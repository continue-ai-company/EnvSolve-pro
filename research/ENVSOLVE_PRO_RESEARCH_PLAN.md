# EnvSolve-Pro Research Plan

> **Current paper design (2026-08-30):** failures are classified by the
> Observation--Constraint--Operation framework. EnvSolve-Pro keeps one unrestricted
> continuous Agent session and exposes repeatable clean replay from the target initial
> state. Replay failures become executable case-local evidence in the same session; only
> the exact replay-passing program can be delivered. The Agent decides when to form a
> candidate and how to repair it. Fixed-cadence observation, forced handoff, and optional
> exact current-goal inspection are rejected development treatments, not core mechanisms.
> Package rules, checkpoints, cross-case
> memory, harness-selected repairs, and hard resource thresholds are also excluded. The
> shared evaluation-integrity foundation E is not an algorithm. Section 12 retains
> superseded proposals as auditable development history.

## 1. Objective

EnvSolve-Pro studies automatic environment construction for unfamiliar repositories.
The core framing remains unchanged: deployment is a **partially observable,
stateful constraint-solving process**, organized as a three-layer loop:

1. **Observation: what happened?** Preserve repository evidence, execution outcomes,
   environment identity, and uncertainty.
2. **Constraint: what is missing or conflicting?** The same active session retains
   case-local soft constraints grounded in target-state counterexamples.
3. **Operation: how can the environment resolve them?** A strong model freely revises
   the complete deployment program, which is replayed from the target initial state.

EnvSolve-Pro inherits the complete EnvSolve v1 code and Git history. The original
`hongleo-Lee/EnvSolve` repository is archived at commit `07a208f` under tag
`envsolve-v1-baseline-freeze-2026-07-21` and remains a runnable baseline. All new
development belongs to `hongleo-Lee/EnvSolve-pro`.

### Current convergence decision

The primary method is now the minimal continuous-session plus repeatable clean-replay
loop. A fixed three-pair replication falsified the narrower hypothesis that an
Agent-invoked exact current-goal Pass shortens the transition to program replay: the
Pass-to-replay delay did not improve, Official success did not increase, and deployment
completeness varied independently of the benchmark goal. Keep that implementation as an
ablation and debugging observer; do not add cadence, handoff, checkpoint, frontier, or
package rules from these cases.

The next core work is evidence, not another controller patch: complete the O/C/O taxonomy
for true Official bad cases, isolate failures that occur before a replayable program is
formed, and then run the fixed Minimal B method against matched controls and external
baselines on outcome-blind cases.

## 2. Research Principles

### 2.1 Success first

Official Pass@1 and clean replay are the primary objectives. Tokens, model calls,
containers, commands, and wall-clock time are efficiency measurements, not part of
the problem definition. Only broad runaway and safety limits terminate the main
protocol. Confirmatory experiments additionally report success-resource curves;
dollar cost is not a primary scientific variable.

### 2.2 Structure augments model reasoning

Strong models retain access to bounded raw observations. Soft constraints are
provenance-aware advice, not the model's only context, and the model may reject their
interpretation or propose operations outside the current schema. Evaluation integrity,
including evaluator isolation and result-channel protection, is enforced by the shared E
foundation for every method and is not part of EnvSolve-Pro. Hard compatibility rules
that require, reject, or rewrite deployment actions belong to the distinct C_h method
family and are evaluated through the frozen prior EnvSolve baseline.

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

### 2.5 Primary execution platform

DGX Spark is the primary execution host for new Dev censuses, construction containers,
clean replay, and Official evaluation. Mac retains the local Agent session, experiment
control, code editing, and lightweight regression tests; it is not a deployment host.
Every compared arm uses the same Spark platform, image digest, network policy, and
accelerator exposure. GPU access is an explicit experimental setting rather than an
implicit host property: the frozen CPU-compatible census keeps it disabled, while CUDA
support is evaluated later as a separately frozen platform treatment. The SSH transport
is shared infrastructure and is not part of the EnvSolve-Pro algorithm.

Spark is Linux ARM64, one of EnvBench's published container platforms. Development
results therefore remain valid for the declared platform, but native-package failures
are tagged as architecture-sensitive. Before leaderboard submission, all frozen methods
and comparison arms must be rerun on the actual submission platform; cross-platform
claims require agreement between ARM64 and AMD64 rather than extrapolation from either.

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
| P7 (complete) | Qualify executable goal-grounded state | Goal-grounded target-state replay plus rejected controller-policy ablations | Goal fidelity, multi-round repair, and no evaluator leakage |
| P8 (in progress) | Controlled effectiveness and freeze | Finish taxonomy, matched outcome-blind Dev, external baselines, Canary, and Official Test | Code, prompts, goals, baselines, and analysis frozen |

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

A 2026-08-24 attempt-level reconstruction recovered all 48 method--case rows and 36
completed Official evaluations. Native Codex passed 6/15 evaluated episodes, causal-v3
3/10, and reproduced Repo2Run 1/11. These denominators differ because the methods used
different models, objective visibility, and infrastructure/adapter paths. They are not a
performance ranking. The matrix supports trajectory taxonomy and identifies target-goal
visibility as a repeated causal difference; same-backbone effectiveness must be estimated
by the later matched experiment. The evidence matrix and retry adjudication are
`experiments/validations/pro_cross_method_census_v1_evidence_matrix.json` and
`experiments/validations/pro_cross_method_census_v1_attempt_adjudication.json`.

Mechanical terminal stages are now separated from causal labels. A provisional
single-reviewer pass has evidence-linked annotations for all 38 non-success rows. The 25
algorithmically attributable rows contain Observation 14, Constraint 7, and Operation 4;
infrastructure unknown 9 and protocol censored 4 are excluded. Descriptively, native
Codex contributes Observation 8, Constraint 1, and protocol censored 1; causal-v3
contributes Constraint 3, Operation 3, and infrastructure unknown 7; reproduced Repo2Run
contributes Observation 6, Constraint 3, Operation 1, infrastructure unknown 2, and
protocol censored 3. These are not method rates because the backbones, visibility, and
execution paths differ. The same Conan Official residual is Observation for Codex and
Repo2Run but Operation for causal-v3: only causal-v3 represented the exact missing
conditional import, then chose an action that did not satisfy its versioned API
requirement. Target-bootstrap rows likewise split between unobserved target state and
package-index incidents. The annotations and generated summary are
`experiments/validations/pro_cross_method_census_v1_causal_annotations.json` and
`experiments/validations/pro_cross_method_census_v1_causal_annotation_summary.json`.
An independent second annotation is still required before any reliability or
distributional claim.
The blinded all-row packet and agreement implementation are
`experiments/validations/pro_cross_method_census_v1_second_annotation_packet.json` and
`experiments/compare_causal_annotations.py`; the packet intentionally contains no first-
reviewer label, subtype, rationale, or evidence anchor.

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

The representative trace has now been completed on consumed-development UER-py. Its six
declared requirements resolved to 35 wheels and a 2.896 GB cache snapshot. Direct and
initially empty-cache lifecycles took 2584.94 and 2605.31 seconds; both exposed a
verification marker but conservatively exceeded the frozen wrapper timeout during
`docker run --rm`. A distinct fresh client then replayed the same closure from a
process-level offline DevPI in 93.74 seconds and exited normally. This is a 27.58-fold
descriptive speedup over direct execution and a 96.37% wall-clock reduction. The cache
snapshot verified unchanged after replay.

This result changes the batch design. A global mutable cache would create method-order
effects, while a frozen-offline cache would reject novel packages and thereby close a
strong model's operation space. New, unfrozen comparisons should instead receive
independent writable copies of the same attested, method-independent seed snapshot, with
online misses allowed. Seed construction may use benchmark-visible manifests but never
outcomes. Cache mutations persist within one episode only, eliminating repeated
candidate downloads without carrying state across compared methods. Seed cost,
hit/miss counts, upstream bytes, cache size, wall-clock, and service memory are reported
separately. The existing DeepSeek-direct retry remains cache-disabled.

## 8. External-Trajectory Adjudication and Next Algorithm

The completed Lark and micropy-cli posthoc study observed Repo2Run and a goal-aware Codex
agent on consumed development cases. It is mechanism evidence, not a performance
comparison. Repo2Run's native ReAct loop stopped on Lark when repository tests passed,
although the official public goal still contained 13 issues. On micropy-cli it made
tracked dependency-declaration edits to pass native tests and could not emit a valid
environment-only replay program. Goal-aware Codex instead found a legitimate Lark
solution through interactive package diagnosis, but on micropy-cli it submitted
synthetic import stubs despite receiving the open candidate contract. Executable
validation correctly rejected that candidate.

Together with the negative execution-feedback-v3 screen, this changes the active
hypothesis. The next method will not add another semantic constraint taxonomy or narrow
the Bash action space. It will combine a strong interactive agent with the existing
three-layer state:

- **Observation:** preserve complete public-goal findings, command outcomes, repository
  effects, candidate-policy decisions, and clean-replay results.
- **Constraint:** maintain only a provenance-preserving ledger of unresolved goal
  obligations, admissibility violations, and verified candidate facts.
- **Operation:** let a strong agent inspect and act through an open terminal, then submit
  a cumulative program. A rejected program or failed clean replay becomes feedback for a
  subsequent fresh repair round rather than terminating the case.

The frozen name for this minimal hypothesis is `stateful-agent-v1`. Its controlled
comparison uses the same strong model and public goal: one native goal-aware session,
multiple sessions with raw prior feedback, and multiple sessions with structured current
state plus relevant raw evidence. Official Pass@1 is primary. Failure-conditioned
recovery directly tests the new mechanism. Tokens, requests, commands, environments, and
wall-clock remain reported resource outcomes rather than success overrides.

Before unseen development cases are opened, `stateful-agent-v1` must pass three consumed
mechanism checks: it must preserve the legitimate Lark program, return exact policy
rejection as a new observation on micropy-cli, and produce an identity-audited clean
replay for every claimed success. The consumed cases may validate plumbing and
mechanism only; no rule may encode their package names or solutions.

### 8.1 Stateful-Agent V1 Decision

The four consumed positions all passed the official metric on their first submitted
candidate, but this does not qualify the mechanism. The two Lark programs are valid
environment-only deployments. Both micropy-cli programs instead overlay the checkout's
`micropy` namespace with `micropy.cli` from an older same-name distribution on
`PYTHONPATH`. They are reproducible mixed-source environments, not source-consistent
reproductions. The identical shortcut in raw and structured conditions localizes the
failure to the shared verification contract.

Because every episode ended after one model round, no rejection or goal failure reached
a later session and the structured repair state was never exercised. V1 is frozen as a
diagnostic strong-agent baseline, with no effectiveness or resource claim. V2 adds only
a shared pre-operation goal observation, a generic project-namespace provenance check,
and restoration of trusted verifier shell invariants. It must demonstrate a genuine
failure-to-repair transition on consumed data before any new Dev repository is opened.

### 8.2 Stateful-Agent V2.1 Decision

V2.1 corrected the initial-observation role boundary and completed the consumed
micropy-cli mechanism case. Before the first model action, the executable goal produced
70 active findings; the Constraint layer retained all of them and projected 24 complete
obligation groups. Candidate 1 directly generated a Python stub and was rejected with
the exact offending line. Candidate 2 received that program and rejection in a new
session, changed strategy, passed fresh internal verification, and achieved Official
Pass with zero scoring issues. This is the first observed stateful rejection-to-repair
transition, but it remains consumed mechanism evidence.

Posthoc audit found one remaining construct gap. Candidate 2 used setuptools metadata to
assign the existing `micropy.app` source to the absent `micropy.cli` identity. That is
valid under the frozen V2.1 source-byte rule and under EnvBench's official
`reportMissingImports` objective, but it is not module-identity preserving. V2.2 adds
only this missing invariant. Its ARM64 Docker canary permits a normal same-identity
install and rejects an undeclared source relabel. The next step is to expose V2.2 through
a versioned runner, freeze it before opening repository-disjoint Dev cases, and report
Official Pass separately from integrity-qualified Pass.

### 8.3 Stateful-Agent V2.2 Dev-5 Decision

The frozen repository-disjoint Dev-5 diagnostic is complete. The strong single-session
goal-aware baseline and the raw-feedback loop both achieved `5/5` Official Pass;
structured V2.2 achieved `4/5`. V2.2 used 16.2% fewer commands and 19.4% fewer input
tokens than raw feedback, but had essentially identical total wall time and introduced
a false hard rejection. It therefore provides no effectiveness evidence and is retained
as a frozen structured baseline.

The failure analysis changes the active mechanism. Eager pre-action goal probing imposed
cost and attention bias before the strong agent had used repository evidence. Derived
root groups did not reduce state growth because complete findings remained in the model
projection and each surface finding produced two state events. Most importantly, the
project-provenance heuristic rejected legitimate Python namespace composition in
`moat-mqtt`. A constraint inferred from deployment semantics cannot override the
official objective unless it is part of the shared experimental admissibility contract.

Detailed totals and case evidence are frozen in
`PRO_STATEFUL_AGENT_V2_2_RESULTS.md`. These cases are consumed and cannot qualify the
next version.

### 8.4 Stateful-Agent V2.3 Hypothesis

V2.3 makes a subtraction rather than adding another rule:

1. the first operation receives repository access and no mandatory full-goal probe;
2. after a candidate fails, complete goal findings enter the audit archive while only
   root obligations enter solver state and the bounded model view;
3. hard authority is limited to the public executable goal and shared candidate/effect
   rules; inferred provenance or runtime semantics remain advisory;
4. the Operation layer remains an unrestricted strong agent.

This restores the intended partial-observability loop: a model first acts under
uncertainty, executable failure reveals new state, and a later independent session
repairs against a compact constraint frontier. Raw-feedback V2.3 receives the same
failure-triggered schedule and verifier boundary but no root compaction, providing the
same-model ablation.

The implementation is isolated from all historical freeze files. Mac regression is
`655 passed, 3 skipped, 2 Python-3.9 deselections`; Spark ARM/Linux regression is
`670 passed, 3 skipped`, with two unrelated host tests failing because the login shell
does not provide a `python` alias. The next scientific step is a newly frozen,
repository-disjoint batch comparing strong single-session, raw V2.3, and structured
V2.3. Success is Official Pass@1; recovery after a genuine first-candidate failure is
the mechanism outcome. Resource statistics remain secondary.

### 8.5 Stateful-Agent V2.3 Pilot Decision and V2.4

The repository-disjoint Pilot-3 produced `2/3` Official Pass for every condition.
Structured V2.3 used the most time, commands, and model tokens, so it provides neither
effectiveness nor efficiency evidence. The runs began from a dirty worktree and are
scientifically ineligible; their role is restricted to mechanism diagnosis. Exact
descriptive totals are recorded in
`PRO_STATEFUL_AGENT_V2_3_PILOT3_RESULTS.md`.

StopStalk localizes the next contradiction at the Operation interface. The executable
goal can be satisfied while repository effects or caller-visible shell postconditions
remain invalid. V2.3 collapsed these axes into one candidate failure, discarded exact
repair information, and also used an over-broad text validator that rejected a
legitimate configuration writer after it merely read a real source file.

V2.4 is the smallest general correction:

1. preserve goal status independently from operation-contract status;
2. project exact operation violations after a goal Pass;
3. validate actual embedded-Python write targets structurally;
4. enforce restoration of the caller working directory.

No repository name, package, or solution enters the algorithm. V2.4 must be committed
and clean before a new salted sample is selected. The V2.3 cases are consumed and may
serve only as regression tests. Promotion requires new-case Official Pass improvement
or reproducible recovery from the factorized failure state without regression on easy
first-round successes.

### 8.6 Stateful-Agent V2.4 Pilot Decision

The clean four-repository Pilot-4 comparison is complete. All 12 artifacts are valid and
scientifically eligible. The strong single-session baseline, raw repair V2.4, and
structured V2.4 each achieved `4/4` Official Pass. Structured V2.4 used 66.7% more input
tokens and 3.4% more end-to-end time than raw repair, with no success gain.

More importantly, all raw and structured episodes passed on one candidate in one model
round. The cross-candidate state transition was never causally available to the
Operation layer. V2.4 therefore does not test the proposed failure-conditioned repair
mechanism; its resource differences cannot be attributed to dormant state. It is frozen
as an auditable structured baseline and is not promoted. Exact results and the disclosed
clean-retry amendment are recorded in
`PRO_STATEFUL_AGENT_V2_4_PILOT4_RESULTS.md`.

The hard `flavio` trajectory localizes the next problem inside the active operation
session: package installation success, legacy semantic compatibility, platform
feasibility, static visibility, and runtime ABI coherence are distinct facts. The
structured condition observed several of them but did not maintain a monotonic
compatibility frontier; it revisited incompatible states and finally exploited a static
evaluator gap.

The next version will not add a repository-specific package rule or a larger semantic
taxonomy. Its qualification hypothesis is:

1. normalize command outcomes into a compact within-session compatibility frontier;
2. admit only causally grounded facts and preserve their supporting observations;
3. screen high-impact environment transactions for feasibility and postconditions while
   leaving the terminal action space open;
4. suppress only actions whose relevant preconditions have already been falsified;
5. report Official Pass and runtime-coherence certification as separate outcomes.

The Pilot-4 repositories are consumed. New qualification cases must be selected
outcome-blind from repository-disjoint identities. Before opening them, the mechanism
must show on consumed or synthetic traces that a falsified operation changes the next
operation without blocking an easy valid first-round solution.

## 9. Historical Minimal B Freeze

The ActiveState and verified-frontier proposals above are not the current algorithm.
They remain historical hypotheses and possible later treatments. The frozen next method
contains exactly four runtime elements:

1. one continuous strong-Agent session;
2. one persistent construction environment with an unrestricted terminal;
3. a callable `submit_and_replay` tool that creates a distinct clean environment and
   returns validation, execution, public-goal, and effect-audit evidence to that session;
4. acceptance only for the exact program that passed clean replay.

The immediate controlled pair changes only element 3: the control receives one terminal
post-session replay, while Minimal B may use replay feedback online and continue in the
same session. Official evaluator output remains terminal-only. Source implementation,
tests, and a machine-readable implementation freeze must be complete before selecting a
new effectiveness batch.

Minimal B v1.0.2 now passes this implementation gate. In a preregistered consumed-case
smoke, one continuous session retained useful partial state after a timed-out install,
produced an ordinary dependency-based program, certified it in a distinct clean
environment, and then passed the terminal Official evaluator. The only replay passed, so
this establishes live feasibility and admissibility, not replay-conditioned recovery or
an effectiveness gain. The next experiment is the frozen repository-disjoint A/B pair;
the method must not be changed from this consumed outcome.

## 10. Frozen Paired Dev-5 Decision

The repository-disjoint development pair is complete. Minimal B scored `5/5` Official
Pass@1 and the otherwise matched strong Agent control scored `4/5`. Four pairs passed in
both conditions and `datactive/bigbang` passed only under Minimal B. With one discordant
pair, the exact two-sided McNemar test is `p = 1.0`. This is a positive direction, not a
statistically reliable effect or a held-out claim.

All five Minimal B episodes called clean replay exactly once and passed on that first
call. The batch therefore did not exercise replay-failure-conditioned repair. The
`bigbang` difference may come from certification-aware construction or run variance; it
cannot yet be attributed to iterative repair. Minimal B is frozen as a new baseline, not
declared the converged EnvSolve-Pro algorithm.

Resource evidence also prevents a one-sided story. Across all five attempts Minimal B
used `4.8%` more model tokens and `12.1%` fewer container commands. Across the four pairs
with comparable coordinator timing it was `36.1%` slower. Peak memory, disk growth, and
network bytes were not persisted and are reported as missing. The `bigbang` time pair is
censored because its control used an amended exact-revision source cache after pre-Agent
network failures.

### 10.1 Measurement findings

Two shared harness defects must be fixed before the next batch:

1. command and Git timeouts terminate only the parent process, allowing transport or
   installer children to survive and overlap later commands;
2. source acquisition and resource telemetry are not yet controlled strongly enough for
   clean efficiency comparisons.

The infrastructure qualification will kill complete process groups, use the same
immutable exact-revision cache policy for every condition, and report memory, disk, and
network only when they can be measured symmetrically. These are measurement changes and
will be applied identically to all methods; they are not part of the algorithm claim and
do not block an Official Pass experiment.

A post-hoc audit also found that both methods officially passed
`castagnait/plugin.video.netflix` by resolving `setup` to an unrelated Pylint module that
does not expose the imported `get_addon_data` symbol. Official Pass@1 remains the primary
benchmark outcome. A separate, method-neutral diagnostic must distinguish module
resolution from required-interface compatibility so that reproducibility claims do not
silently exceed what the public goal verifies.

### 10.2 Next causal gate

The next outcome-blind development batch will use three arms with the same model,
terminal, construction environment, public goal, and evaluator boundary:

1. terminal post-hoc clean replay only;
2. one clean-certification call with no second certificate after failure;
3. callable clean replay with continuation after failure.

Arm 1 versus 2 measures certification-aware construction. Arm 2 versus 3 isolates the
algorithmic value of replay-conditioned repair. Mechanism activation is reported before
aggregate success: number of first-replay failures, number followed by a second proposal,
and number recovered in the same session. No structured state, checkpoint, hypothesis
search, or minimization is added until this decomposition either validates the loop or
identifies a repeated failure that requires one of those treatments.

### 10.3 Certification-Repair Ablation v1 freeze

The three-arm interface is now implemented and frozen. Arm B inherits Minimal B's goal
verifier, integrity boundary, certificate binding, and clean-environment provider, but
executes at most one replay. A second submission is recorded and rejected without
provisioning an environment. The shared qualified infrastructure freeze passed `699`
tests with `6` skips and `75` subtests, and the complete tree after adding Arm B passed
`702` tests with `7` skips and `75` subtests. Linux ARM qualification on Spark passed
`25` focused tests and `7` real-Docker tests.

Before execution, eight repositories were selected from the untouched pool by a frozen
salted repository hash, yielding 24 rotated episodes. The mechanism decision is fixed:
only a C-arm first replay Fail/Unknown followed by a different passing replay and final
Official Pass supports feedback-conditioned repair. The bilingual protocol is frozen in
`PRO_CERTIFICATION_REPAIR_ABLATION_V1_PROTOCOL.md`.

The effective-episode adjudication, reproducible analysis, and bilingual result report
are frozen in `experiments/validations/pro_minimal_b_v1_paired_dev5_effective_episodes.json`,
`experiments/validations/pro_minimal_b_v1_paired_dev5_results.json`, and
`research/PRO_MINIMAL_B_V1_PAIRED_DEV5_RESULTS.md`.

### 10.4 Boundary-v2 validity decision

The first complete three-arm block cannot estimate an algorithm effect. Arm A reached
the public construction goal with a legitimate runtime configuration copied from a
tracked template, but the shared integrity rule rejected it. Arm B created an unrelated
empty import module and was correctly rejected. Arm C received repeated replay feedback
and eventually passed the public metric by redefining the shell behavior used to invoke
Pyright. The batch stopped immediately; all three trajectories are consumed diagnostics.

Boundary v2 makes only shared measurement corrections:

1. trusted goal execution excludes candidate-defined shell functions and startup hooks;
2. the public goal explicitly invokes the selected Python command rather than a shell
   function;
3. ignored runtime configuration is admitted only when its bytes match a tracked,
   same-directory, same-stem template at the exact repository revision;
4. versioned runners and entrypoints prevent later schedules from silently selecting the
   old boundary.

The exact Arm-C program now completes but fails real Pyright under the corrected boundary;
the exact Arm-A workspace passes the provenance audit. Focused tests and real-Docker
red-team tests pass on macOS and Spark Linux ARM, with byte-identical source snapshots.
This is an infrastructure qualification, not an effectiveness result. Next, freeze the
v2 source and analysis contract, replace consumed identities through the original
outcome-blind sampling rule, and run the unopened three-arm cases without further method
changes.

### 10.5 Boundary-v2 Dev-8 preregistration

The next effectiveness batch is frozen before any repository is opened. It carries
forward the six identities attested as unexecuted and uninspected, then fills the two
consumed slots with the next eligible identities under the original salted repository
ranking. A manifest-only audit found no prior trajectory for any replacement candidate;
repository contents, failures, and scores were not read.

The resulting schedule contains eight repository blocks and 24 sequential episodes. All
three arms use explicit boundary-v2 runners, the same strong model, the same Mac host, and
the same broad operational limits. Spark remains a portability and infrastructure host;
mixing it into only part of the causal batch would introduce a host-by-treatment
confound. No algorithm or boundary change is allowed until all 24 scheduled outcomes are
recorded or a preregistered structural-validity stop is triggered.

### 10.6 Boundary-v3 and the Untouched Dev-5

The structural-validity stop triggered in the third repository block. All arms found the
repository-native package synchronization operation, but boundary v2 rejected its
lock-derived Python outputs. The retryable arm additionally obtained a false certificate
after creating and deleting temporary build configuration. The entire `trader` block is
excluded from A/B/C effect estimates.

Boundary v3 keeps the three reasoning interfaces fixed and changes only shared
measurement. It qualifies the submitted program in a fresh environment, records
prohibited configuration writes even when their final filesystem effects disappear, and
admits generated dependencies only through repository declaration, revision-bound lock
content, and package-manager verification. Standard `virtualenv` hooks require a
pre-candidate template hash and version match. Construction residue remains trajectory
evidence rather than the submitted artifact.

The exact A program now passes the public goal and all provenance checks on Spark Linux
ARM; the temporally hidden C program is rejected before execution. A byte-identical B
program passed under the immediately preceding v3 implementation, while final-hash B
attempts were censored by external package transport. Full regression reports 735 passed
and 8 skipped tests plus 76 passing subtests. These results qualify the measurement
boundary, not the algorithm.

The first repository of the Untouched Dev-5 triggered another validity stop before its B
arm. C and A both passed Official evaluation, but boundary v3 treated equivalent native
builds differently according to whether their output was under `/tmp` or the repository.
The original v3 audit also rejected 106 exact source copies emitted by A's standard build
command. This case and both submitted programs are consumed measurement diagnostics; no
method comparison is reported.

### 10.7 Boundary-v5 freeze and resume rule

Boundary v4 was preregistered as a minimal native-artifact correction. It accepted A's
tracked-source native extension but failed calibration because the 106 exact build-tree
source copies remained rejected. It is preserved as a failed measurement version.

Boundary v5 replaces location and suffix exceptions with one committed-source provenance
principle. Python build copies are accepted only when their bytes equal a committed source
and their output path preserves that source path as a suffix. Native extensions are
accepted only when committed native source declares the same module initializer and the
artifact has a valid native format and initializer. Modified, renamed, direct, and
source-less import artifacts remain rejected. The candidate operation language, Agent
session, public goal, and Official evaluator are unchanged.

The preregistered consumed calibration replayed the exact A and C programs with zero model
calls or Official evaluator calls. A qualified with 106 committed-source copies and one
native artifact; C qualified with the corresponding native artifact in an external import
root. Both had zero missing imports and zero remaining violations. Mac full regression
passed 759 tests; Spark Linux ARM passed all 24 focused v4/v5 tests with byte-identical
sources. The calibration proves measurement consistency only.

The implementation is frozen in
`experiments/protocols/envsolve_pro_certification_repair_boundary_v5_implementation_freeze.json`.
Effectiveness experiments may resume only on the four unopened repositories at case
positions 2-5 of the boundary-v3 schedule, using versioned boundary-v5 A/B/C runners for
the 12 episode positions 4-15. Host, model, prompt, public goal, Official evaluator, and
analysis rules must be frozen before any repository is opened.

## 11. Current V2 Paper Program

Sections 4-10 preserve research history; they are not the current paper algorithm. The
paper separates three scientific objects:

| Object | Values | Role |
|---|---|---|
| Failure taxonomy | Observation, Constraint, Operation | Explains the earliest decisive failure. |
| Deployment mechanism | F, scheduled O, delta C, R | Specifies search, measurement, state, and replay. |
| Shared foundation | E | Makes results fair and auditable; never counts as a treatment. |

EnvSolve-Pro keeps one strong Agent in a persistent construction session. The Agent has
free shell control (F). The harness executes the same identity-bound public goal on a
frozen schedule (O), converts complete finding sets into resolved and introduced
obligations while retaining a nondominated evidence frontier (C), and certifies complete
programs only through independent clean replay (R). Accumulated evidence is monotonic;
the environment and Agent action space are not. E isolates the Official evaluator and
audits identity and repository integrity.

### 11.1 Failure Study

All scientifically valid consumed trajectories from EnvBench FreeAgent, Repo2Run,
native Codex, prior EnvSolve, and EnvSolve-Pro enter retrospective taxonomy discovery.
Each failed episode receives one evidence-anchored primary label for the earliest decisive
Observation, Constraint, or Operation failure; infrastructure incidents are censored.
A deterministic 20% sample stratified by system and primary category is independently
re-annotated. Raw agreement, Cohen's kappa, and adjudicated labels are reported. This
nonuniform corpus supports taxonomy discovery and cross-system profiles, not success-rate
claims or causal attribution.

### 11.2 Optional-Ledger Pilot Decision

The frozen consumed-case pilot compared B-FSR (F+R) with D-LEDGER, which added one
optional identity-bound compatibility tool and delta ledger. Two repositories, two arms,
and two replications produced eight valid episodes after preregistered infrastructure
replacements. All episodes passed provider, image, goal, repository-integrity, and audit
checks.

D formed and officially passed 3/4 candidates versus B's 2/4, with one D-only win and no
D-only loss. The decisive Paz trajectory observed 16 obligations, later observed zero,
repaired one clean-replay dependency conflict, and passed Official at request 84; its
paired B trajectory used all 120 requests without replay. However, one successful D
episode never called the ledger. The treatment therefore failed its preregistered
mechanism-activation criterion. On comparable successful pairs, median D-over-B ratios
were 1.30 requests, 1.28 interactive steps, 1.46 tokens, and 1.11 time to certificate.

The machine decision is `negative-mechanism-not-qualified`. It rejects the optional-tool
implementation, not the observation hypothesis. Complete, identity-bound observations
can expose false progress and can precede a successful shift from environment repair to
replayable-program repair, but voluntary scheduling makes the treatment inconsistent and
often expensive.

### 11.3 Deterministic Observation V2

The next candidate changes only observation scheduling:

1. run one complete identity-bound observation before the first model request;
2. run another after every 16 completed shell operations;
3. before clean replay, observe again only if the environment changed since the latest
   observation;
4. inject the existing delta-ledger feedback into the same continuous session;
5. never block shell operations or replay, select packages, restore a container, or use
   cross-case memory.

The cadence is frozen from the consumed-14 natural global-check interval of 17.96 shell
actions, rounded once to 16; it is not tuned on the new pilot outcome. The optional
`check_compatibility` tool is removed so every treatment episode receives the same
mechanism dose. Existing ledger representation, Agent, clean replay, model/provider,
safety caps, and E remain unchanged.

Preregister a 16-episode consumed qualification: four previously consumed repositories,
two arms, and two replications with counterbalanced order. The two current stress cases
remain eligible as design cases; two additional identities are frozen before
implementation from distinct prior observation-failure strata. Mechanism qualification
requires schedule compliance in every treatment episode, at least 75% complete
observations, zero operation constraints, and zero checkpoints. Promotion additionally
requires no lower Official Pass count, at most one paired treatment-only loss, and either
one treatment-only win or a preregistered success-conditional efficiency signal. Tokens,
time, network, disk, and memory remain outcomes rather than optimization cutoffs.

### 11.4 Confirmation and Claims

Do not open another frozen Dev identity until V2 passes the consumed qualification. Then
freeze algorithm, prompt, tool schema, taxonomy, model/provider binding, and analysis code
before Canary. The primary outcome is Official Pass@1. Mechanism outcomes include
observation schedule compliance, state deltas, candidate-ready-to-replay latency,
first-replay repair, and paired failure-layer transitions. Resource outcomes are reported
unconditionally and conditional on success; infrastructure censoring remains separate.

Final system comparisons include Repo2Run, EnvBench FreeAgent, prior hard-constraint
EnvSolve, and same-backbone free-search controls where native semantics can be preserved;
native Codex is an independent frontier reference. The first paper claims only a fixed
three-layer algorithm and controlled evidence. Harness search remains Auto-EnvSolve, and
learned policies remain EnvSolve-RL.

## 12. Verifier-Triggered Target-State Replay Candidate

The deterministic-observation qualification ended in a ceiling tie and was not promoted.
The subsequent six-case bad-profile study found a more basic defect: the old replay
environment inherited the construction package cache, so two replay-passing programs
failed cold Official evaluation. The active contradiction was therefore inaccurate
Observation of the deliverable, not an insufficient constraint library.

### 12.1 Minimal Algorithm

The current candidate retains only:

1. one continuous free-search Agent session;
2. fixed-schedule, trusted measurement of the complete public goal in the construction
   state;
3. an executable transition from the first complete Pass to immediate programization;
4. execution of the whole program from the target initial state without construction
   cache reuse;
5. return of the first executable counterexample to the same session as advisory
   evidence; and
6. repetition until one complete program passes or broad safety limits expire.

The observation layer supplies identity-bound execution evidence. The constraint layer
holds case-local contradictions between the current program and target state. The
operation layer remains the unrestricted Agent; the controller only schedules measurement
and executes the Pass-to-replay transition. No package rule, ledger, checkpoint, cross-case
memory, or additional hard action policy is part of the method.

### 12.2 Consumed Mechanism Check

The preregistered basxconnect, Graphium, and cvxportfolio check completed on Spark with
DeepSeek V4 Flash through DeepInfra. Final replay and Official outcomes agreed in all
three cases, and all three passed Official. Basxconnect and Graphium produced a failed
replay, a materially changed program in the same session, a later replay pass, and an
Official pass. Graphium's five-replay sequence exposed an invalid torchvision version,
missing Git ownership setup, omitted test dependencies, one network failure, and then a
pass. This directly replaces the old construction-cache false pass.

The batch used 139 model requests, 137 shell operations, and 3,133,930 tokens. Graphium
alone used 82 requests, about one hour of generation, and a 1.2 GiB construction cache.
The mechanism is therefore operational and target-state-faithful on these selected
cases, but neither success-rate nor efficiency gain has been established.

### 12.3 Outcome-Independent Qualification

Four pairs were fixed from positions 9--12 of the pre-existing randomized Dev16 schedule
before source acquisition or model execution. Same-model goal-aware free search passed Official
2/4 and target-state replay passed 3/4. The paired table is two both-pass, one B-only,
zero A-only, and one both-fail; exact McNemar is `p=1.0`. A disclosed researcher
interruption affected the original cellrank B episode. Using the replacement specified
before replacement execution gives the primary table; excluding the entire cellrank pair
gives 2/3 versus 3/3.

The causal evidence is narrower than the score difference. Probatus was B-only but passed
its first replay, so stochastic search variation remains a plausible cause. In
importlib_metadata, two failed replays exposed successive complete-program defects and a
third changed program passed replay and Official. Cellrank B exhausted 120 requests before
candidate formation, so replay never activated. Aggregate B time and tokens were higher.

The preregistered promotion condition is met only as a development decision: keep the
minimal mechanism unchanged and scale it to the next fixed Dev batch. No effect,
efficiency, held-out, or SOTA claim is licensed.

### 12.4 Development Expansion and Next Evidence

The unchanged A/B comparison on Dev16 positions 13--16 completed as a 4/4 versus 4/4
ceiling tie. All final replays agreed with Official. Three B programs passed their first
replay; pygeo repaired a network-acquisition timeout and then passed. Aggregate B resources
were lower, but paired request and generation-time medians did not improve; pygeo dominated
the totals. Combined with qualification, A is 6/8 and B is 7/8 with only one discordance
and exact McNemar `p=1.0`.

This result closes random Dev scaling rather than licensing an algorithm patch. Keep the
minimal method fixed and construct the next batch from pre-existing strong-baseline
Official failures in the census. Freeze the sampling rule and baseline evidence before
opening treatment outcomes. Do not add a pygeo network rule, package rules, checkpoints,
or other orthogonal treatments. External baselines and strong/weak backbone comparisons
follow only after this bad-case effectiveness test determines whether replay improves
success where the matched control has headroom.

### 12.5 Failure-Enriched Bad-6 Stress Test

The preregistered strong-baseline Official-failure Bad-6 completed with 12 scientifically
eligible episodes. End-to-end success was `2/6` for the goal-aware free Agent and `4/6` for target-state
replay: two both-pass, two B-only, zero A-only, and two both-fail pairs, with exact McNemar
`p=0.5`. Four B candidates executed seven replays, including three Fail-to-Pass repairs;
final replay and Official agreed on 4/4. HARK is the cleanest causal rescue: internal fresh
replay exposed the same Git ownership failure as A's Official run, and the same session
added the safe-directory operation before passing replay and Official.

This batch establishes neither significance, generalization, efficiency, nor SOTA. B used
5.8% more tokens and 10.4% more endpoint time. More importantly, quacc B expanded search
before candidate formation; both ajenti arms had already reached zero missing imports but
continued pursuing broader runtime completeness without submission. Micropy-cli A likewise
reached the public objective repeatedly but did not deliver. The next bottleneck is therefore
**successful-candidate retention and stopping**, not an insufficient package rule set.

The next version considers one simple success-first hypothesis: preserve the first executable
Official-equivalent candidate and send it to target replay before optional completeness or cost
exploration can erase it. Official success, deployment completeness, and path cost remain
separate outcomes. No package rule may be tuned on consumed Bad-6 cases; the hypothesis requires
a new fixed development batch.

### 12.5.1 Mechanism-label correction

Code review after the causal census found that the historical `deepseek-free-agent`
prompt included the complete executable public goal. Its `A-F` label was therefore
incorrect: the arm implemented `F+O`, while target-state replay implemented `F+O+R` with
advisory replay constraints. All existing paired results remain valid for the replay
contrast, but none estimates the effect of public-goal visibility. The runner now exposes
three distinct future arms: repository-feedback `F`, goal-aware `F+O`, and replay
`F+O+R`. This is an experimental-interface correction, not an algorithmic success claim.
The consumed six-case diagnostic design and balanced three-arm schedule are recorded in
`experiments/validations/envsolve_pro_for_v1_consumed6_design.json` and
`experiments/schedules/envsolve_pro_for_v1_consumed6.json`.
Before any episode started, the first-party credential failed an authenticated canary.
The study therefore moved all three arms together to OpenRouter's pinned
`deepseek/deepseek-v4-flash-0731` endpoint with DeepInfra fixed and fallbacks disabled.
The case set, methods, prompts, tools, evaluator, and analysis remained unchanged; the
pre-execution record is
`experiments/validations/envsolve_pro_for_v1_provider_amendment.json`.

### 12.6 Certified-Incumbent Falsification and Verifier-Triggered Handoff

That hypothesis was tested without changing the scheduled episodes. After correcting the
selection claim with the historical registry, the primary prospective set contains six
pairs. B-FSR passed `6/6`; C-GCI passed `5/6`, with qibolab B-only. No C episode activated
fallback. C also consumed more resources both unconditionally and on the five common
successes. Certified-incumbent retention is therefore removed from the core method and
retained only as a later orthogonal safety ablation.

The decisive qibolab trajectory reached a trusted full-goal Pass but never formed a
candidate. This separates two states that prior analysis had conflated: **the environment
is sufficient** and **a replayable cumulative program has been delivered**. Prompting the
Agent to stop did not reliably cause the transition, while post-replay retention began too
late to help.

The next minimal method gives the controller exactly one new responsibility: after a
trusted full-goal Pass, transition the same active session into programization and clean
replay. Search and replay repair stay open-ended; package choice, interpreter choice, and
completeness remain Agent decisions. The method adds no package rules, cross-case memory,
physical checkpoint, candidate graph, or self-modification.

The preregistered consumed qibolab qualification completed the entire transition. Both
arms passed Official. The scheduled control first passed at request 72, then spent 11 more
requests and 10 shell operations before producing a candidate. The treatment passed at
request 64, triggered handoff once, submitted on request 65, received a clean-replay
dependency conflict, repaired it in the same session, and passed replay on request 66 and
Official evaluation. This qualifies the mechanism, not its effectiveness. Its lower
requests, tokens, and time are descriptive results from one consumed pair.

Runner 0.6.0 also exposed a causal-design confound: the treatment prompt announced the
future handoff before it activated. Runner 0.6.1 removes that disclosure and makes tools
and initial prompts exactly equal across arms; the controller instruction appears only
after a trusted Pass. The next evidence is a fixed prospective bad-case comparison against
B-FSR. No qibolab-specific rule or other treatment is licensed by this qualification.

### 12.7 Atomic-Submit Outcome-Independent Pilot

Runner 0.8.0 made complete-program clean replay atomic with final delivery while preserving
the strong Agent's continuous session and free search. The only two previously unexecuted
Dev-pool cases were fixed before execution. Both atomic and plain `F+O` programs passed
Official; one plain result required an unchanged-script evaluator retry and remains censored
under strict adjudication because its retry method label was not identical to the source.

Atomic replay activated once on fontbakery and three times on verticapy. Verticapy produced
a genuine Fail--Fail--Pass repair chain across distinct fresh containers, but its plain
control also passed. Aggregate atomic generation used 126 versus 88 requests, 2.70M versus
1.99M tokens, and 7,419 versus 3,762 seconds. This qualifies feedback continuity and
replay--Official agreement; it does not qualify success or efficiency gain.

Do not promote universal atomic replay and do not patch the observed package hashes. Keep
the treatment fixed for a mechanically selected batch of pre-existing goal-aware `F+O`
Official failures. That batch tests the narrow remaining hypothesis: atomic replay feedback
improves Pass@1 when the matched control has demonstrated headroom.

### 12.8 Verified Atomic Handoff on the Consumed Goal-to-Delivery Cases

The fixed consumed diagnostic selected all three cases with an already observed
goal-to-delivery gap: Quacc, Ajenti, and Hark. Search remained unrestricted. The harness
ran the trusted complete goal initially and every 16 shell operations; when the result
first became Pass, the next model request had to deliver the cumulative program through
the existing atomic replay action. Replay Fail restored unrestricted tool choice in the
same active session. The study therefore qualifies the coupled scheduled-observation plus
handoff mechanism; it cannot identify a pure handoff effect.

All three cases submitted one model request after their first trusted Pass. Quacc invoked
three replays (`Unknown`, `Fail`, `Pass`) and passed Official after the same session repaired
an over-minimized dependency program. Hark invoked two replays (`Fail`, `Pass`), adding the
fresh-checkout Git ownership operation on the request immediately after failure, and passed
Official. The original Ajenti episode submitted once and exhausted 120 requests after the
old import-provider boundary rejected its goal-passing environment.

Ajenti was adjudicated separately under a procedure written after the episode outcome but
before adjudication execution. No model was called and the request-97 program was not
changed. After correcting the existing provenance check to recognize exact installed-
distribution files and fixed-path system-package ownership, that program passed both clean
replay and the unchanged Official evaluator. The original episode remains Fail but is
censored from algorithm-effect attribution as harness-boundary-induced. The correction
retains rejection of manually introduced unowned providers and does not add a deployment
rule.

The original batch endpoint is `2/3` Official Pass; mechanism activation and one-request
delivery are `3/3`. This is consumed, outcome-conditioned evidence and licenses only the
fixed algorithm described at the top of this document. The next effect experiment uses an
outcome-blind, repository-disjoint bad-case batch with matched `F+O` controls. No additional
algorithm or boundary change is allowed in response to these three treatment outcomes.

### 12.9 Prospective Ten-Pair Stress Test and Core-Method Reduction

The preregistered treatment-unopened batch selected every eligible deterministic failure
from the independent Codex census after applying the recorded exclusions. It executed 20
episodes on Spark: matched goal-aware free search `A-F+O` versus the larger
scheduled-observation, forced-handoff, and atomic-replay treatment `B-F+O+H+R`. Older
trajectories from these repository identities had informed development, so this is a
prospective development stress test, not held-out evaluation.

One pair was censored by evaluator infrastructure. Among nine eligible pairs, A passed
`6/9` and B passed `7/9`: five both-pass, one A-only, two B-only, and one neither-pass pair.
The two-sided exact McNemar result is `p=1.0`. Of the two B-only outcomes, basxconnect never
activated forced handoff, so only BigBang is a mechanism-consistent rescue. Micropy-cli was
A-only because B did not complete generation. The five common-success pairs used 47.6
versus 47.4 mean model requests, while B used more mean generation time (3,143 versus 2,204
seconds) and tokens (1.42M versus 1.13M). These small descriptive resource samples do not
support an efficiency claim.

The scientific decision is subtraction. Fixed cadence and forced handoff are not promoted
to EnvSolve-Pro. The core returns to Minimal B: one continuous Agent session, an
Agent-invoked clean-replay action that can be used repeatedly, replay feedback returned to
the same session, and mandatory exact-program replay certification before delivery. The
existing integrity boundary remains shared experimental infrastructure. No package rule,
candidate-retention policy, checkpoint, compatibility ledger, or new gate is added.

Two measurement fixes accompany the adjudication without changing any episode outcome:
later deterministic Python environment failures now prevent an earlier network message
from censoring the episode, and termination metadata distinguishes an actual forced
handoff from an ordinary atomic submission. Future paired adjudication reports exact
discordance statistics and common-success resources.

The next evidence sequence is fixed as follows:

1. finish the independent Codex and Repo2Run Dev failure matrix and freeze every eligible
   baseline-failure case before opening new Minimal-B outcomes;
2. run matched `F+O` versus Minimal-B `F+O+R` with the same pinned DeepSeek V4 Flash model,
   provider policy, broad safety limits, and Official evaluator;
3. complete independent stratified annotation of the failure taxonomy in parallel;
4. make no algorithm change until the full batch is adjudicated;
5. only if Minimal B preserves or improves Official success proceed to untouched
   evaluation, external-system comparison, and the strong/weak backbone study.
