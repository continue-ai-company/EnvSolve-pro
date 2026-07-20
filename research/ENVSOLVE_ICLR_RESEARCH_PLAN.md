# EnvSolve: Stateful Constraint Solving for Repository Deployment under Partial Observability

> Living ICLR manuscript. Chinese version:
> [`ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md`](ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md).
> Engineering history and experiment ledgers live in the detailed research plans,
> not in this manuscript.

## Abstract

Deploying an unfamiliar repository requires recovering a hidden set of runtime,
dependency, build, and platform requirements. These requirements are not directly
observable: execution reveals only incomplete and sometimes ambiguous symptoms,
while network and infrastructure failures may reveal nothing about the proposed
environment. Repository deployment is therefore better modeled as partially
observable, stateful constraint solving than as unconstrained shell-command
generation.

We introduce **EnvSolve**, a three-layer deployment agent. The **observation layer**
turns repository declarations and fresh executions into provenance-bearing evidence.
The **constraint layer** admits only sufficiently grounded evidence into a persistent
state of facts, conflicts, hypotheses, and unresolved obligations. The **operation
layer** converts that state into a complete deployment program whose execution can
resolve the remaining conflicts. Each candidate is tested in a fresh environment,
and only internal execution feedback may update the state; the official evaluator
is terminal and never provides repair feedback.

We evaluate EnvSolve on EnvBench against Repo2Run, native agents, and same-backbone
raw-history and reflection loops. Comparisons match model access, online information,
official-evaluator access, and primitive resource limits. The study measures final
deployment success, terminal reach, repair efficiency, failure recurrence, and clean
replay. Confirmatory held-out results are pending, so this manuscript currently
makes no effectiveness or leaderboard claim.

## 1. Introduction

Running a repository from source is a prerequisite for testing, program analysis,
migration, security auditing, and large-scale software reproduction. Yet deployment
often fails before any of those tasks begin. A missing import can indicate an absent
distribution, an incompatible language version, a platform-specific branch, or an
incorrect project installation. A failed package command can instead reflect an ABI
conflict, a missing build tool, or a transient package-index failure. Similar logs
can have different causes, and the same cause can produce different logs.

This makes repository deployment a reasoning problem over hidden environment state.
The repository does not provide a complete executable specification of its valid
environment. An agent can inspect metadata and source, but it learns whether a
deployment program is viable only by executing it. Even then, the observation is
partial: successful installation does not imply that all source-visible imports are
resolvable, and a timeout with a network signature does not establish that the
candidate itself is wrong.

Most language-model deployment agents use a conversational loop: generate commands,
execute them, append the resulting log, and ask the model to try again. This loop is
useful, but its state is implicit. Raw history does not say which observations are
facts, which assumptions have been contradicted, which failures are ambiguous, or
which earlier operations must be retained when the next attempt starts from a clean
environment. Natural-language reflection compresses the history, but still delegates
evidence admission and state consistency to free-form generation.

EnvSolve instead separates deployment reasoning into three explicit layers:

1. **Observation:** what happened, and what evidence did the execution expose?
2. **Constraint:** what is known, what conflicts, and what remains unresolved?
3. **Operation:** which environment changes can resolve those constraints?

The layers form a closed loop. A complete deployment program is generated from the
current constraint state, executed in a fresh environment, and converted into new
evidence. Only evidence that passes deterministic admission rules changes the hard
state. This preserves the flexibility of a strong coding agent while preventing
ambiguous or infrastructure-censored feedback from silently becoming a deployment
rule.

The paper makes three contributions:

1. **Problem formulation.** We formulate repository deployment as partially
   observable, stateful constraint solving, distinguishing latent environment state,
   executable observations, and terminal task evaluation.
2. **Three-layer method.** We introduce EnvSolve, whose observation, constraint, and
   operation layers implement provenance-aware evidence admission and
   counterexample-guided generation of complete, replayable deployment programs.
3. **Controlled empirical study.** We design a leakage-resistant EnvBench evaluation
   that compares EnvSolve with native and same-backbone loop baselines under matched
   information and primitive resources, with separate analyses of success, terminal
   reach, efficiency, and clean replay.

EnvBench is a testbed rather than the definition of the method. Fresh containers,
artifact audits, and immutable schedules are experimental controls. They support
valid measurement but are not presented as independent algorithmic contributions.

## 2. Problem Formulation

Let `R` be a repository at a fixed revision and let `Z_R` denote its latent valid
deployment conditions: language runtime, ABI, packages, build tools, system
libraries, platform predicates, and environment variables. A deployment program
`P` is a replayable sequence of environment actions. It may configure the runtime
and install dependencies, but it may not edit application source, fabricate missing
modules, or weaken the evaluator.

At round `t`, the solver executes candidate `P_t` in a fresh environment `E_t` and
receives an observation

`O_t = V(R, P_t, E_t; Z_R, xi_t)`,

where `V` is an internal executable verifier and `xi_t` represents nuisance state
such as network availability and package-index behavior. `O_t` is generally
non-identifying: several latent causes may explain one failure, and an infrastructure
failure may censor the candidate outcome entirely.

The solver therefore maintains a state

`S_t = (F_t, C_t, H_t, U_t, X_t)`,

where `F_t` contains grounded facts, `C_t` hard constraints and contradictions,
`H_t` unresolved hypotheses, `U_t` operation obligations, and `X_t` immutable raw
evidence with provenance. The transition

`S_{t+1} = Update(S_t, Admit(O_t))`

is deliberately not equivalent to appending `O_t` to a prompt. `Admit` decides
whether an observation can modify hard state, remain provisional, or be classified
as Unknown.

An unchanged official evaluator `Q` scores only the final deployment program. Its
output is not observable during the online episode and cannot enter `S_t`. The
objective is to maximize terminal deployment success. Resource limits are part of
the experimental setting, not the task definition: compared methods receive matched
limits on model requests and tokens, candidate environments, executable commands,
and wall-clock time.

### 2.1 Why Partial Observability Matters

Partial observability has three sources. First, repository declarations are
incomplete, conditional, and sometimes stale. Second, execution exposes symptoms
rather than latent causes. Third, infrastructure can censor observations. A solver
that treats every log line as a hard fact can overfit to incidental failures; a
solver that treats no feedback as persistent state repeatedly pays to rediscover the
same conflict. EnvSolve is designed around this tension.

## 3. EnvSolve

### 3.1 Overview

EnvSolve implements the following loop:

```text
S0 <- ObserveRepositoryAndBaseRuntime(R)
while no internal Pass and resources remain:
    U_t <- PlanOperations(S_t)
    P_t <- ProposeCompleteProgram(R, S_t, U_t)
    if not Validate(P_t, U_t):
        S_t <- UpdateWithPolicyCounterexample(S_t, P_t)
        continue
    O_t <- ExecuteAndVerifyFresh(R, P_t)
    S_t <- Update(S_t, Admit(O_t))
return the internally passing program, if one exists
```

The model proposes concrete programs, but deterministic layers control what enters
state, which obligations a proposal must cover, and whether an execution can justify
repair.

### 3.2 Observation Layer: What Happened?

The observation layer converts heterogeneous repository and execution artifacts into
a common evidence schema. Before the first proposal, bounded read-only observers
extract standard project declarations and inspect the exact base runtime. During the
episode, each accepted candidate is run in a new checkout and container. The layer
records the candidate, environment identity, image digest, commands, exit status,
duration, verifier checks, and bounded terminal evidence.

Observations are typed as:

- **Pass:** the declared internal obligations are satisfied;
- **Fail:** reproducible evidence contradicts a candidate assumption;
- **Unknown:** the outcome is censored or cannot be attributed to the candidate.

For example, a deterministic runtime-version mismatch is a grounded Fail. A generic
build error may support only a hypothesis. A timeout with an explicit network or
provider signature is Unknown. An unsigned command timeout establishes candidate
cost under the fixed limit, but not a package-level cause.

The layer never consumes online feedback from the official evaluator. This prevents
test leakage and makes the final evaluation genuinely terminal.

### 3.3 Constraint Layer: What Is Missing or Conflicting?

The constraint layer is the persistent reasoning state. It admits observations by
evidence strength and provenance rather than by textual plausibility.

Grounded positive observations become facts. Deterministic incompatibilities become
hard contradictions. Ambiguous explanations remain hypotheses. Unknown observations
do not become candidate constraints. Every state item points to the candidate,
environment, verifier, and raw evidence that supports it.

State updates obey three invariants:

1. **No unsupported hardening.** A hypothesis cannot become a hard constraint without
   new grounded evidence.
2. **No accidental forgetting.** Failure to re-observe a variable does not imply that
   an unresolved obligation has been satisfied.
3. **Scoped replacement.** A fact is superseded only by later evidence about the same
   domain, subject, and predicate.

These invariants turn execution history into a compact state transition system. The
model sees unresolved conflicts, relevant facts, recent candidate outcomes, and
bounded evidence, rather than an ever-growing transcript.

Python dependency checking illustrates the need for structured state. Runtime
semantics ask whether an import executes on the candidate platform; static source
resolution asks whether a source-visible module is discoverable. These obligations
overlap but are not identical. EnvSolve records them separately instead of collapsing
both into a single import-success bit.

### 3.4 Operation Layer: How Can the Environment Change?

The operation layer maps unresolved constraints to environment actions. A
deterministic planner projects supported state into a typed `OperationPlan`, such as
configuring a compatible runtime, installing a declared dependency, selecting a
project installation mode, or preserving an operation that supported a fact in a
previous fresh environment.

The language model instantiates this plan as a complete deployment program. A typed
validator then checks three properties before execution:

- the program changes only the environment;
- it covers all supported operation obligations;
- it does not replay a prefix already known to fail before any repair can take effect.

Rejected programs return a policy counterexample without consuming a container.
Accepted programs always run from a clean state. Consequently, the operation layer
does not merely recommend the next shell command; it constructs a self-contained
candidate that explains how the current constraints will be resolved.

### 3.5 The Closed-Loop Solver

The three layers separate responsibilities but are coupled by executable feedback:

`Observation -> Constraint update -> Operation plan -> Fresh execution -> Observation`.

This is the algorithmic distinction from ordinary ReAct-style deployment. Raw-history
and reflection baselines may use the same number of rounds and see the same raw
feedback. EnvSolve differs in what feedback is allowed to persist, how contradictions
survive across fresh environments, and how persistent state constrains the next
complete program.

## 4. Experimental Design

### 4.1 Research Questions

- **RQ1: Effectiveness.** Does EnvSolve improve Official Pass@1 over deployment
  baselines under matched information and primitive resource limits?
- **RQ2: Mechanism.** Are gains attributable to explicit constraint state, evidence
  admission, and constraint-to-operation planning?
- **RQ3: Efficiency and robustness.** Does EnvSolve reduce repeated failures and
  improve clean replay without relying on extra attempts or evaluator feedback?

### 4.2 Benchmark and Splits

The main testbed is the 329-repository Python portion of EnvBench. Development uses
only declared cases from the official training partition. Mechanism choices are
qualified on separately frozen, outcome-blind development batches. Canary-20 is used
once after algorithm freeze; Official-Test-100 remains untouched until the method,
budgets, baselines, and analysis are frozen. EnConda-Bench is outside this paper.

EnvSolve performs no cross-case learning or experience retrieval in this study. This
keeps the first paper focused on within-case stateful solving and preserves trajectories
for future work without adding an untested memory claim.

### 4.3 Baselines and Fairness

We compare:

- fixed native EnvBench baselines;
- Repo2Run;
- a same-backbone raw-history loop;
- a same-backbone natural-language reflection loop;
- EnvSolve without persistent typed state;
- full EnvSolve.

The causal comparison matches model and seed, repository revision, base image, raw
online observations, official-evaluator access, and global primitive limits. Each
candidate starts fresh for all loop baselines. The official evaluator is called only
after an internal terminal candidate and never returns feedback to any method.

Budgets are reported as model requests and tokens, candidate environments, commands,
and wall-clock time. Dollar cost is an optional dated conversion, not a scientific
matching variable.

### 4.4 Outcomes

The primary outcome is EnvBench Official Pass@1. Secondary outcomes are:

- fraction of runs that naturally reach terminal official evaluation;
- repair success after the first failed candidate;
- repeated-failure rate and constraint-resolution rate;
- clean-replay success in a new environment;
- model, environment, command, token, and wall-clock consumption;
- censored Unknown outcomes, reported separately from candidate Fail.

Confirmatory comparisons use paired outcomes and confidence intervals. A pair is
eligible only when both methods produce auditable Boolean official outcomes. If
terminal reach is insufficient, the batch supports failure decomposition but not an
effectiveness estimate.

### 4.5 Ablations

The main ablations remove one mechanism at a time:

- typed persistent constraint state;
- evidence admission and Unknown censoring;
- provenance-aware state replacement;
- constraint-to-operation planning and guarding;
- fresh replay of complete candidates.

We additionally compare typed state with natural-language reflection and report
success-resource curves under several preregistered limits.

## 5. Current Evidence and Remaining Experiments

The implementation, audit path, and three-layer loop are complete enough for frozen
development qualification. Aggregate development evidence has established three
facts. First, raw candidate generation is not the only bottleneck: failures can arise
from observation calibration, state transitions, and the mapping from constraints to
operations. Second, infrastructure and provider failures must be censored rather than
converted into repair constraints. Third, reaching the terminal evaluator is itself
a necessary diagnostic outcome; without sufficient terminal reach, paired deployment
effectiveness is not identifiable.

The current development batch does not provide enough complete Boolean official
pairs for a method-effect estimate, and one run was interrupted by the operator.
These trajectories are retained for error decomposition only. Their dominant
transition is candidate-command failure: deterministic operation failures are
observed, but many never become persistent negative operation state. A minimal
revision now admits infeasibility only from a verified failed command prefix, binds
it to the relevant provider context, and keeps network or infrastructure censoring
Unknown. Repository-free counterexamples establish evidence admission, persistence,
context-sensitive rejection, and alternative-operation preservation. Its effect on
deployment remains unknown and must be measured on a new outcome-blind development
qualification before the method is frozen for Canary-20 and Official-Test-100.

That qualification begins with a preregistered eight-pair broad system pilot on the
local development host, before larger ARM64 Linux execution. Cases are selected by
metadata-only hashing after host admission; all pairs are completed before an
algorithm decision. The pilot reports negative-operation utilization separately and
does not treat the broad contrast as a single-component causal ablation.

The final paper will contain three result tables:

1. Official Pass@1 and paired effect estimates for all baselines;
2. component ablations and terminal-reach decomposition;
3. success-resource and clean-replay analyses.

Until those confirmatory runs are complete, all effectiveness cells remain blank and
the paper makes no leaderboard claim.

## 6. Related Work

EnvSolve connects language-model agents for software engineering, automated
environment construction, execution-guided synthesis, and agent reflection or
memory. Its intended distinction is not the existence of an execution loop. It is
the explicit separation of observation, constraint admission, and environment
operation under a terminal-only evaluator.

Compared with free-form reflection, EnvSolve restricts which evidence may change
persistent state. Compared with classical counterexample-guided synthesis, its
observations are noisy, partial, and sometimes censored rather than complete symbolic
counterexamples. Compared with existing deployment agents, its experiments isolate
state representation and transition rules while holding backbone, information, and
resources fixed. Citations will be added after the related-work audit.

## 7. Limitations

EnvSolve cannot repair application defects without violating the environment-only
task boundary. Its internal verifier is an approximation to terminal deployability
and may be incomplete. Fresh environments improve causal clarity but increase time
and compute. Network and package-index failures create censored outcomes. The current
study covers Python repositories in EnvBench; claims about other languages, operating
systems, or cross-case adaptation require separate evidence.

## 8. Conclusion

Repository deployment is difficult because the valid environment is hidden and each
execution reveals only partial, noisy evidence. EnvSolve addresses this problem with
a three-layer architecture: observe executions, maintain an explicit constraint
state, and generate complete environment operations that resolve the remaining
conflicts. This design turns trial-and-error deployment into an auditable stateful
solver while preserving a strong model's ability to construct concrete programs.
The decisive empirical question remains whether this structure improves terminal
deployment success under fair, matched conditions; the frozen held-out study is
designed to answer exactly that question.
