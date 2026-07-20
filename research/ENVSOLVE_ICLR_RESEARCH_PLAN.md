# EnvSolve: Stateful Constraint Solving for Repository Deployment under Partial Observability

> Living ICLR manuscript. Chinese version:
> [`ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md`](ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md).
> Claims in this draft are updated only when supported by frozen experiments.

## Abstract

Repository deployment exposes neither a complete specification nor a cheap oracle.
The compatible runtime, ABI, language and system dependencies, build tools, and
platform conditions form a hidden environment state. An agent observes this state
only indirectly by executing a candidate: the same import or build failure can have
several causes, while network failures and timeouts censor the observation entirely.
Repository deployment is therefore a partially observed, stateful constraint-solving
problem, not merely shell-command generation.

Existing language-model agents usually respond to failure by appending terminal
output to a conversation and trying again. This provides a loop, but no principled
answer to two central questions: what did the execution actually establish, and is
that evidence strong enough to constrain the next attempt? As a result, project
constraints, ambiguous failures, and infrastructure noise are easily conflated.

We introduce **EnvSolve**, which formulates repository deployment as partially
observable, stateful constraint solving. At each round, EnvSolve proposes a
complete deployment program, executes it in a fresh
environment, and converts grounded observations into explicit facts, hypotheses,
and constraints. Deterministic contradictions may guide the next proposal;
ambiguous evidence remains a hypothesis; timeouts carrying explicit infrastructure
signatures remain Unknown, while unsigned fixed-budget timeouts become candidate-cost
evidence. The official benchmark evaluator is used only
once, after the online episode, and never supplies repair feedback.

We evaluate EnvSolve on EnvBench using resource-matched, same-backbone controls that
retain either raw execution history or natural-language reflection. Our evaluation
measures final deployment success, repair efficiency, repeated failures, and clean-
replay reliability. Development analysis revealed a calibration gap between runtime
import checks and static missing-import evaluation, motivating a preregistered
two-layer import-obligation verifier that keeps runtime semantics and static source
resolution as separate evidence. Held-out results are not yet available, so this
draft makes no performance claim.

## 1. Introduction

Running an unfamiliar repository is a deceptively hard reasoning problem. A failed
import may indicate a missing package, a wrong Python version, a platform-specific
branch, an optional feature, or a project-local module that has not been installed
correctly. A failed installation may instead be caused by a package mirror, an
incompatible build tool, or a transient timeout. These observations do not all
justify the same repair.

The difficulty comes from the relationship between the real environment and the
agent's observations. The repository has an unknown set of compatibility and
dependency requirements, but there is no command that reveals this set directly.
Execution supplies only a projection: a missing module identifies a violated
requirement but not necessarily the distribution that satisfies it; a successful
import does not prove static source closure; and a timeout reveals almost nothing
about the candidate. Different hidden causes can therefore produce the same log,
and one hidden cause can produce different logs under changing infrastructure.
This is the sense in which deployment is **partially observed**.

Observations are also expensive. A useful counterexample may require a clean
checkout, a new container, package-index traffic, compilation, test discovery, and
another model proposal. This does not define the task, but it does require a
controlled evaluation: unlimited retries would turn compute into apparent
intelligence and make comparisons meaningless. We therefore compare methods under
matched limits on primitive resources such as model requests and tokens, candidate
environments, commands, and wall-clock time.

This problem matters beyond a benchmark score. At repository scale, reliable
deployment is the gateway to testing, code understanding, migration, and vulnerability
analysis. An engine that cannot
separate environment evidence from infrastructure accidents cannot reproduce
projects reliably enough to support these downstream systems.

Most LLM deployment agents use a conversational loop: run a command, observe its
output, and ask the model what to try next. The loop is useful, but its state is
implicit. The agent can easily repeat a failed command, overreact to a network
error, forget which assumptions were disproved, or produce a script that only works
because an earlier attempt changed the container.

EnvSolve starts from a simple idea: **execution feedback should constrain the next
deployment only after the feedback has been interpreted as evidence**. The method
therefore separates four operations that are commonly mixed together:

1. proposing a complete deployment candidate;
2. executing that candidate in an independent environment;
3. deciding what the execution actually establishes;
4. generating the next candidate from the resulting constraint state.

This separation is intended to make deployment more successful, but also more
scientifically interpretable. We can compare structured state with raw history while
holding the model, feedback, evaluation access, and primitive resource limits fixed.

This paper makes three contributions:

1. **Formulation.** We cast repository deployment as partially observable,
   stateful constraint solving, where execution results become useful only through
   an explicit, provenance-bearing state.
2. **Method.** We introduce EnvSolve, a counterexample-guided deployment algorithm
   that proposes complete programs, verifies them in fresh environments, and admits
   grounded Fail, hypothesis, and infrastructure-Unknown evidence differently.
3. **Empirical evaluation.** We provide a controlled EnvBench study against same-backbone raw-
   history and reflection loops under matched information and resource limits,
   measuring final success, repair behavior, resource use, and clean-replay reliability.

EnvBench is our main testbed, not the definition of the method. Harness isolation,
artifact logging, and fresh containers are necessary for valid experiments, but are
not presented as separate algorithmic contributions.

## 2. Problem Formulation

Let `R` be a repository at a fixed revision. Its latent deployment state `Z_R`
contains the runtime, ABI, package, build, and platform conditions required for a
valid environment. `Z_R` is not directly observable. A deployment program `P` is a
replayable sequence of environment actions such
as choosing a runtime, installing system packages, installing language
dependencies, and setting safe environment variables.

At round `t`, the agent proposes `P_t`. The program is executed in a fresh
environment `E_t`, and an internal verifier `V` returns observations
`O_t = V(P_t, E_t; Z_R, xi_t)`, where `xi_t` denotes nuisance conditions such as
network availability and package-index state. The observation is non-identifying:
multiple latent states may explain the same failure, and censoring may reveal no
candidate property at all. EnvSolve therefore updates an explicit constraint state
rather than treating `O_t` as ground truth:

`S_t = (F_t, C_t, H_t, X_t)`,

where `F_t` contains grounded facts, `C_t` contains admitted constraints, `H_t`
contains unresolved hypotheses, and `X_t` contains immutable execution evidence.
The next proposal is sampled from `G(R, S_t)`. Experimental runs record the primitive
resources consumed by every proposal and execution and stop at preregistered resource
limits shared by the compared methods.

An unchanged official evaluator `Q` scores only the final program. `Q` is called at
most once per method, case, and seed, after the online episode terminates. Its output
cannot enter `S_t`. The research objective is to improve final official success
under matched experimental conditions, not to maximize the number of attempts.

We require a valid solution to modify only the environment. It may not edit
application source to hide failures, create fake modules, weaken the evaluator, or
use case-specific rules derived from held-out outcomes.

## 3. EnvSolve

### 3.1 Complete deployment candidates

Each proposal is a complete program that must work from a clean checkout. It is not
a patch applied on top of the previous attempt. This makes each candidate directly
replayable and prevents success from depending on hidden container history.

A typed replay validator accepts environment mutations and rejects source edits,
observation-only commands, unsafe path injection, and unsupported shell control
flow. Rejected programs are retained as evidence and consume candidate budget, but
they do not consume an environment or command budget.

### 3.2 Fresh execution

Every accepted candidate receives a new checkout and a new container identity.
EnvSolve records the exact command, stdout, stderr, exit code, duration, image
digest, repository revision, and environment identity. No writable state is shared
between candidate environments.

Fresh execution is part of the algorithm because it tests whether the proposed
program is self-contained. It is distinct from the terminal benchmark evaluation.

### 3.3 Executable verification

The internal verifier checks ordinary properties available without official
evaluator feedback. These include installation success, package consistency,
project compilation, runtime facts, and dependency obligations derived from project
source and metadata.

For Python imports, EnvSolve separates two obligations. The **runtime-semantic**
layer asks whether an import must execute under the candidate platform and source
control flow. The **static-source** layer asks whether the source-visible name has a
discoverable module, package, extension, namespace package, or type stub. Guarded
optional and compatibility imports may be inactive at runtime while remaining
static obligations; `TYPE_CHECKING` imports are static-only; provably inactive
target-platform branches waive both layers. A side-effect-free resolver operates
only on the candidate interpreter and physical source paths. It does not call the
official evaluator, run Pyright, query a package index, or use repository-specific
module mappings.

The verifier returns one of three outcomes:

- **Pass:** the preregistered internal obligations are satisfied;
- **Fail:** reproducible evidence contradicts the current deployment assumptions;
- **Unknown:** the observation is censored or cannot be attributed to the candidate.

A timeout with an explicit network or infrastructure signature is Unknown, not
evidence that a different package or command is needed. An unsigned fixed-budget
timeout records that the candidate exceeded the execution limit and may guide a
lower-cost next candidate without asserting a package-level cause.

### 3.4 Evidence admission and state update

Evidence is admitted according to its strength. A deterministic missing capability
can become a hard constraint. A plausible but non-identifying build failure remains
a hypothesis. Malformed output, stale evidence, reused environments, and forbidden
feedback fail closed.

Before the first action, a bounded non-executing observer admits only unconditional
package requirements from standard project metadata. A separate network-disabled,
read-only probe observes Python in the exact base-image digest. Standard runtime
requirements are admitted only when they can be compared with that fresh fact.
Marked, malformed, dynamic, or tool-directive declarations remain unadmitted. The
fresh verifier then observes installed distribution presence, version, and runtime
facts, so an initial requirement remains unresolved only until candidate-scoped
evidence satisfies or contradicts it.

Deterministic runtime incompatibility reported by a package manager becomes a hard
requirement-fact contradiction. Ambiguous action failures remain hypotheses or
provisional state. This gives repository declarations and execution feedback one
shared, provenance-bearing runtime representation.

Each admitted fact records its source candidate, environment, verifier, and raw
evidence. Because each fresh execution is only a partial observation, absence from
a later verifier result is not evidence of satisfaction. An environment-scoped fact
is superseded only by a later fact about the same domain, subject, and predicate;
hypothesis-only and unrelated observations preserve unresolved obligations. The
underlying event remains immutable. A complete verifier report may contain both
positive observations for repaired variables and counterexamples for variables that
remain violated; incomplete or Unknown reports admit neither as hard state.

### 3.5 Counterexample-guided repair

When a candidate fails, the next model call receives the repository context,
unresolved conflicts, recent candidate outcomes, verifier summaries, and bounded
terminal evidence. This projection is an aggregate-bounded sufficient statistic:
raw findings and full constraint records remain auditable but are not duplicated in
the model context. The loop stops when an internal Pass is obtained, the budget is
exhausted, the policy explicitly blocks, or an Unknown outcome prevents justified
repair.

Malformed model output is itself recoverable up to a fixed limit: it is hashed,
recorded, and returned as a protocol error without creating a container. This
protects the deployment search from incidental formatting failures while keeping
their cost visible.

When the state contains a supported hard conflict, a high-confidence unresolved
requirement, or a satisfaction that depended on a previous candidate environment,
a deterministic planner projects it into a provenance-bearing `OperationPlan`.
The last case matters because the next candidate starts fresh: an operation that
made the previous environment valid must remain in the complete program. The model
selects concrete repair parameters, while a guard checks that the current candidate
covers every operation obligation. It also prevents replaying an execution prefix
already observed to fail before any proposed change can take effect. This connects
what is missing or conflicting to how the environment may be changed without a
repository-specific package map. Rejection consumes candidate and model budget only.

### 3.6 Why this is not just another loop

Raw-history, reflection, and EnvSolve can all execute multiple candidates. Their
difference is the representation and admission of feedback. Raw-history retains
logs; reflection asks the model to summarize them; EnvSolve exposes a typed state in
which only grounded evidence can constrain later actions. The main experiments are
designed to isolate this difference under one shared budget.

## 4. Evaluation

Our evaluation tests three hypotheses: EnvSolve improves final deployment success
under a matched total budget; the gain comes from structured constraint state and
evidence admission rather than from additional attempts; and the resulting programs
replay more reliably in clean environments.

### 4.1 Benchmark and splits

The main benchmark is the 329-repository Python portion of EnvBench. Development is
restricted to declared cases from the official training partition. New mechanism
decisions must be qualified on a separately frozen development batch. Canary-20 is
used once after algorithm freeze, and Official-Test-100 remains untouched until all
method and analysis decisions are frozen.

EnConda-Bench is outside this paper. During evaluation, EnvSolve performs no
cross-case update and retrieves no natural-language experience, summary, or
trajectory from another case.

### 4.2 Baselines and controls

We compare with fixed native baselines, Repo2Run, and same-backbone controls. The
causal comparison uses:

- a native deployment agent;
- a raw-history loop with fresh candidates;
- a natural-language reflection loop;
- EnvSolve v0 without persistent constraints;
- full EnvSolve.

Compared feedback-loop methods receive the same model, cases, seeds, image, raw
online information, official evaluator calls, and global resource budget. A method
may stop early, but does not receive a new budget for each candidate.

### 4.3 Metrics

The primary metric is EnvBench Official Pass@1. Secondary outcomes include success
under fixed resource limits, repair probability after a failed candidate,
repeated-failure rate, clean-replay success, token usage, model requests, commands,
environments, and wall-clock time. Dollar cost, when reported, is an auxiliary
conversion under a dated provider-price snapshot and is not a matching variable or
primary outcome. Confirmatory comparisons report paired effect sizes and confidence
intervals.

### 4.4 Ablations

We remove, one at a time, typed constraint state, evidence admission, provenance,
and fresh replay. We also replace explicit state with natural-language summaries
and vary candidate and token limits to measure success-resource curves.

## 5. Results

### 5.1 Protocol validation

The experimental infrastructure now separates artifact integrity from scientific
eligibility. Integrity audit checks identities, hashes, ledgers, trajectories, and
official claims. Eligibility additionally requires a committed clean source revision,
frozen primitive budgets, a complete runtime heartbeat without suspected host
suspension, and schedule-consistent execution. A single resumable coordinator owns
hard process-group deadlines, while a deterministic summarizer derives every table
entry from hash-chained run evidence. These properties establish experiment validity;
they do not establish EnvSolve's effectiveness.

### 5.2 Development diagnosis

Consumed development trajectories identified four general calibration failures.
First, runtime import success is not a sufficient proxy for a static deployment
objective, motivating a two-layer obligation verifier. Second, treating every
fresh-verifier output as a complete snapshot can erase unresolved conflicts; the
state transition now preserves an old fact until the same variable is observed
again. Third, leaf-wise log truncation does not bound a structured prompt; EnvSolve
now projects the event history into compact conflicts, candidate outcomes, verifier
summaries, and grouped operation obligations under one aggregate context budget.
Fourth, creating a virtual environment without binding it to subsequent verification
can make an installed dependency appear missing; complete candidates must now
activate every environment they create before verification.

The first artifact-valid five-pair operation qualification descriptively produced
one full-only pass, one both-pass pair, two both-fail pairs, and one infrastructure-
censored pair. In the both-pass pair, the full method used two candidates while the
free-form control used five. A later provenance review found that these runs predated
the first Git baseline, so all five pairs are scientifically ineligible and support
error analysis only. The next five-pair batch is also excluded: host suspension caused
multiple wall-clock overruns, and a generic DSL gap rejected valid PDM installs. PDM
install/sync and semantic project-venv binding are now covered by synthetic tests,
without rerunning either consumed batch.

A subsequent clean-contract development batch produced ten scientifically eligible
runs but no official pass. Four of five pairs never reached official evaluation; in
the only official pair, full EnvSolve reduced missing-import issues from 28 to one
but still failed. Error analysis showed that the current operation plan is empty
before the first execution, so it does not yet convert repository observations into
initial constraints. It also found one documentation-source coverage gap and an
over-conservative timeout classifier. The two generic mechanism bugs are corrected
for future unseen development cases, while the failed batch remains consumed. This
negative result narrows the method claim: typed reactive repair alone is
insufficient; the next method revision must define conservative pre-action
constraint admission.

That revision now admits only unconditional standard package declarations before
the first proposal and closes them with fresh installed-metadata observations.
The mechanism and a clean committed EnvBench evaluator were frozen before the next
outcome-blind batch. Five new development identities were then selected by a
preregistered metadata-only hash rule. The batch closed after three pairs under its
preregistered shared-defect rule; all six runs were scientifically eligible, but no
run reached official evaluation. Pre-action package admission triggered on two
pairs, yet a deterministic Python-version mismatch never became a hard runtime
constraint. A later candidate could therefore discard a compatible runtime and
regress to the known-invalid base interpreter. This negative result shows that
package-state admission alone is insufficient: runtime compatibility and action
feasibility must inhabit the same persistent constraint state.

The resulting runtime-state revision was implemented and frozen before another
development repository was inspected. It binds a fresh base-runtime fact
to the candidate image, admits standard runtime declarations against that fact,
turns deterministic version mismatch into a hard contradiction, and preserves
candidate-supported satisfaction across fresh attempts. Synthetic transition tests
and a real Docker boundary validate these semantics. This is mechanism validation,
not evidence of improved deployment success. A five-pair development qualification
has now been preregistered, selected without repository inspection, and bound for
execution. Its primary tests are runtime-state invariants, with paired official
outcome secondary. Its first ablation episode was later interrupted by an operator
before verification and is retained as ineligible/Unknown without retry, censoring
that pair. The eligible full counterpart then exercised the mechanism: an explicit
runtime mismatch had later proposal opportunities, while the base-image identity
remained correct. However, the mismatch remained text rather than becoming a hard
constraint and runtime operation obligation. This primary invariant failure closed
the batch after pair 1. It is a negative mechanism result, not an effectiveness
estimate; the remaining scheduled cases were not run.

A minimal revision now closes only that observed state-transition gap. It accepts
the exact subject-first Python mismatch diagnostic, validates the version and range
under PEP 440, and creates a hard contradiction only when the reported version is
actually outside the allowed range. Synthetic positive, compatible-range,
malformed, incomplete, and hedged counterexamples test the admission boundary; an
end-to-end loop test shows that admitted evidence creates a `runtime_configure`
obligation before the next proposal. The change contains no repository, package,
tool, or version-specific rule and does not alter Poetry command coverage. It is
frozen as mechanism v10 with Harness v24. This establishes internal semantics only;
qualification on new untouched development identities remains pending.

That qualification is now preregistered and execution-bound. A metadata-only hash
selected five new identities from 156 untouched development cases, leaving 151;
the exact evaluator image was attested before any selected repository was inspected.
The trigger, stopping rule, budgets, schedule, and restricted infrastructure retries
were frozen. Pair 1 then closed the batch on a shared verifier defect. Both eligible
runs reached internal test collection, where a repository-local service refused a
localhost connection. A phase-agnostic `ConnectionError` signature mislabeled this
candidate failure as dependency-acquisition infrastructure and terminated both
loops before another proposal. The target v10 diagnostic did not occur, so v10
remains unexercised rather than contradicted. The pair is censored, the remaining
cases were not run, and no official result or effectiveness estimate is available.

The minimal correction uses the already-recorded failed-action phase. Network
signatures can now censor an episode only when failure occurs in a candidate command
or an unknown phase; exceptions emitted by fixed internal checks remain candidate
feedback. Opposed synthetic tests and read-only replay of the Q9 raw artifacts
validate this boundary without naming the observed service or repository. The
revision is frozen as v11. This again establishes internal semantics rather than
deployment effectiveness.

The five-pair v11 qualification then executed all ten frozen runs. Every artifact
was valid and scientifically eligible, with no request error, suspension exclusion,
image mismatch, or infrastructure-Unknown verifier result. However, the target
network signature occurred zero times, so v11 is neither prospectively qualified
nor contradicted. All ten runs exhausted the candidate budget before official
evaluation, leaving all five effectiveness pairs censored. This shifts the immediate
research question from a rare classifier trigger to the dominant solver failure:
why typed state and guarded operations still fail to produce an evaluable deployment
within five candidates. The next development step is aggregate transition-level
error analysis over these consumed trajectories, not another replacement batch.

That analysis first found a simpler budget confound: proposals rejected before
environment creation consumed the same cap as expensive fresh executions. We split
the primitive limits and preregistered a consumed-Q10 calibration that changed only
the proposal cap from five to fifteen. All ten audits were valid. Three runs crossed
the old cap and recovered five executions after proposal five, but no run passed
internally or reached the Official evaluator. Thus the split improves search-budget
utilization but is not sufficient for deployment success. The trajectories instead
identify a narrower interface problem: empty final model content can exhaust retries,
and normal budget exhaustion is mislabeled as a policy exception. These boundaries
are now corrected and frozen as v13: output mode and reasoning effort are explicit,
empty responses retain bounded metadata without reasoning content, and budget
exhaustion has a separate terminal type. A repository-free online probe establishes
API compatibility, so no effectiveness claim follows. A replay is now preregistered
on the single consumed Q10 trigger run; it requires
five parsed responses without output failure and a correctly typed budget terminal,
with no replacement or performance claim.

Each correction was specified with synthetic counterexamples before another
outcome-blind development batch. Triggering batches are retained as consumed
diagnostics and are never resumed after a mechanism change. These observations
validate problem structure and protocol behavior, not held-out effectiveness. No
Official-Test or Canary result has been used, and the paper currently makes no
performance-improvement claim.

### 5.3 Main comparison and ablations

Table 1 compares Official Pass@1 for all resource-matched controls; Table 2 reports component
ablations. The accompanying analysis reports success-resource curves, repeated-failure
rates, and internal-verifier calibration. These result blocks remain empty until the
preregistered confirmatory runs are complete. All Fail and Unknown runs remain in
the denominator.

## 6. Related Work

EnvSolve connects four areas: LLM agents for software engineering, automated
software environment construction, execution-guided program synthesis, and
reflection or memory mechanisms for tool-using agents. Its intended distinction is
not the existence of an execution loop, but the use of typed, provenance-bearing
constraint state and explicit evidence admission under a terminal-only evaluator.

Compared with free-form reflection and memory, EnvSolve restricts state updates
through evidence admission. Compared with counterexample-guided synthesis, it must
reason over noisy, censored software executions rather than a complete symbolic
specification. Compared with deployment agents, it isolates the effect of state
representation under matched budgets. Citations are omitted in this working draft
until the related-work audit is complete.

## 7. Limitations

EnvSolve cannot repair application defects without violating the environment-only
task boundary. Internal verification is necessarily an approximation of terminal
deployability and may be incomplete. Fresh environments improve causal clarity but
increase time and compute cost. Network and package-index failures create censored
outcomes, especially on local development machines. EnvBench covers only part of
the repository-deployment landscape, so broader language and platform claims
require separate evidence.

## 8. Conclusion

EnvSolve asks whether repository deployment becomes more reliable when execution
feedback is treated as evidence for an explicit constraint state rather than as
more conversation context. The method proposes complete programs, tests them in
fresh environments, admits only grounded counterexamples, and keeps official
evaluation terminal. The protocol and core loop are implemented; the decisive
held-out comparison remains pending. The corrected execution language, dual audit,
scheduler, and analysis pipeline are implemented without case-specific or evaluator-
derived rules. The first outcome-blind runtime-state qualification exposed a narrow
diagnostic-admission failure and is closed. The next qualification exposed and
repaired a phase-agnostic infrastructure-classification defect. A complete unseen
development qualification of the repaired v11 produced ten scientifically eligible
trajectories and no false infrastructure transition, but the preregistered target
signature never occurred and no run reached official evaluation. Cross-case
decomposition attributes 23 of 50 terminal candidate stages to candidate-command
failure. A preregistered post-episode calibration of ten deterministically selected
terminal scripts produced nine completed Official failures, one infrastructure
Unknown, and zero passes; only three scripts reached Pyright, where all failed.
Thus terminal non-reach was not hiding a passing script in any completed calibration,
and the Boolean internal gate remains fixed. A subsequent implementation audit found
that nine pre-environment rejects consumed the same five-unit cap as fresh executions.
The consumed-Q10 calibration therefore raised only the proposal cap to 15 while
retaining five fresh environments and five verifier commands. Three runs used the
released capacity and recovered five post-cap executions, but no run reached internal
or Official Pass. The simpler harness explanation is real but insufficient; the next
minimal revision targets output completion and budget-terminal semantics. Held-out
evaluation remains blocked until a frozen development method reaches the terminal
evaluator often enough to support an effectiveness comparison.
That boundary revision is now implemented and synthetically qualified as v13; its
next admissible evidence is a preregistered consumed-development replay.
That one-run trigger replay is now frozen and awaiting execution.

The main loop implements a minimal constraint-to-operation boundary: hard conflicts,
unresolved requirements, and candidate-supported satisfaction produce provenance-
bearing operation obligations, and a typed guard requires the next complete program
to cover them in its fresh execution.
