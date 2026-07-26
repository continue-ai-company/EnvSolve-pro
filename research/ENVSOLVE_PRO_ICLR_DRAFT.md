# EnvSolve-Pro: Partially Observable Stateful Constraint Solving for Repository Deployment

## Abstract

Reproducing a source repository requires discovering runtime, dependency, build, and
platform conditions that are rarely specified completely. An agent observes these hidden
conditions only through repository evidence and the outcomes of programs executed in
isolated environments. Current deployment agents leave this state implicit in a growing
language-model context. They can therefore optimize convenient proxy tests, forget an
unresolved failure, or mistake an infrastructure incident for evidence about the
deployment.

We formulate repository deployment as **partially observable stateful constraint
solving** and introduce EnvSolve-Pro. A public executable goal defines success without
revealing terminal benchmark outcomes. An Observation layer executes each candidate and
the goal in the same isolated environment, preserving lineage and distinguishing Pass,
Fail, and Unknown. A Constraint layer turns goal-grounded failures into revisable
obligations while retaining uncertain repository inferences as hypotheses. An Operation
layer admits a resulting construction state as reusable, damaged, or unknown from
executable postconditions. It exposes this state to a strong language model, which
remains free to generate a complete deployment program rather than choosing from a
closed action vocabulary. Reusable state can carry verified partial progress into later
repair, but the exact final program is certified only after passing in a fresh
environment.

We evaluate EnvSolve-Pro on repository deployment benchmarks against Repo2Run, native
coding agents, and same-model agent loops. Controlled baselines receive the same public
goal, allowing us to separate gains from objective visibility, explicit state, and
iterative constraint repair. Official Pass@1 is the primary outcome; resources are
reported as efficiency measures rather than success thresholds.

## 1. Problem

Given a repository `R`, an initially unknown environment state `z`, and a public
executable goal `G`, the agent must produce a deployment program `P` such that

```text
G(Execute(P, R, z)) = Pass.
```

The agent cannot inspect `z` directly. At round `t`, it runs candidate `P_t` in an
isolated construction state `z_t` and receives observation `o_t`: command outcomes,
goal diagnostics, effect audits, and infrastructure signals. The next round may retain
the resulting state only if executable postconditions establish that it is reusable;
damaged or unknown states are discarded. Each observation reveals only part of the
relevant state.
Different causes can produce similar symptoms, some failures expose only the first
violated condition, and network or provider incidents may yield no valid task evidence.
The agent must therefore revise beliefs and obligations across attempts.

The returned solution is still a complete program, not a state-dependent delta. If a
program passes during construction search, the solver executes the exact same program
from a distinct fresh checkout and environment. Only that replay can certify success.

The executable goal is part of the task specification, not the terminal evaluator. It
contains a versioned program, a report schema, and a content digest. The online solver
may execute it but never receives official benchmark outcomes. This boundary permits
grounded repair while preventing adaptation to hidden labels.

The objective is deployment success. Time, token, and environment limits are experimental
controls used to compare methods under common conditions, not defining properties of the
problem.

## 2. EnvSolve-Pro

### 2.1 Observation: What Happened?

For every candidate, the Observation layer records the repository evidence used, the
complete deployment program, environment identity, execution outcomes, goal report, and
audited effects. It assigns one of three goal states:

- **Pass:** the goal program completed and its report satisfies the declared schema.
- **Fail:** the goal completed and returned concrete unsatisfied conditions.
- **Unknown:** the candidate or goal could not be evaluated reliably, for example because
  a required tool or network operation failed.

Unknown is never converted into task failure or success. Every observation records
environment lineage, freshness, and audited effects. The layer separately classifies the
resulting construction state as reusable, damaged, or unknown; only reusable state may
host a later attempt. Goal reports also declare whether their findings are a complete
snapshot or partial evidence. Only a complete snapshot of the same scope may use absence
to demonstrate that an earlier condition has been resolved.

### 2.2 Constraint: What Is Still Unsatisfied?

The Constraint layer maintains a versioned state `S_t` of active obligations, established
facts, uncertain hypotheses, and their provenance. Goal failures are authoritative
obligations: they remain active until a later execution of the same goal demonstrates
that they are satisfied. Repository declarations and model interpretations may explain
or refine an obligation, but they cannot erase goal evidence.

State transitions are evidence-driven and reversible. A new observation may add an
obligation, refine its scope, connect repeated symptoms to a shared cause, discharge it,
or leave it unresolved. Partial observations may only add or refine state; a complete
same-scope snapshot may discharge absent obligations. This structure prevents two common
failures of raw-history agents: losing a decisive condition in a long trace and treating
the absence of a repeated message as proof that the condition disappeared.

The state is an external cognitive aid, not a complete symbolic model of Python or Linux.
Its minimal form is a provenance-preserving set of current goal obligations. Causal
compression and additional semantic inference are useful only when they improve
resolution without suppressing executable evidence.

Each active obligation also routes a bounded, read-only view of the repository evidence
most likely to explain it: the exact reported source location and related occurrences of
the missing subject. This turns an opaque symptom into grounded local context without
granting the Constraint layer an unrestricted search-and-act loop.

### 2.3 Operation: How Should the Environment Change?

The Operation layer presents the public goal, current constraint state, and selected raw
evidence to a strong language model. It also retains the best fully executed,
integrity-valid candidate as an evidence-backed anchor. The model emits a self-contained
deployment program that may freely revise the anchor but is asked to preserve settings
that remain consistent with current evidence. This prevents a repair for a newly exposed
condition from silently forgetting conditions satisfied by an earlier candidate.

EnvSolve-Pro does not restrict the model to predefined package, runtime, or build actions; such a
closed operator set would bound the capability of future models and fail on novel
repositories.

The program is executed in isolation, followed immediately by the executable goal in the
same shell and environment. The resulting report returns to the Observation layer,
forming the loop

```text
observe -> update constraints -> generate operation -> execute goal -> observe.
```

Safety and integrity checks govern what may be changed and whether the observed effects
belong to the candidate. They do not prescribe a solution. A verified reusable
construction state can carry expensive setup into the next repair, while the model still
emits a cumulative clean-start program. A construction-state Pass triggers a mandatory
fresh replay of that exact program; only a fresh Pass with valid effects is certified.

## 3. Contributions

1. **Problem formulation.** We formulate repository deployment as partially observable
   stateful constraint solving with a public executable goal, separating online evidence
   from hidden terminal evaluation.
2. **Method.** We introduce a strong-model-compatible three-layer solver that preserves
   authoritative goal observations, maintains revisable constraint state, and uses
   postcondition-gated construction-state reuse without closing the operation space.
3. **Evaluation.** We establish a same-goal controlled protocol that separates objective
   visibility from stateful repair, compares against external deployment agents, and
   measures both final success and post-failure recovery.

## 4. Experimental Design

### Research Questions

- **RQ1:** Does EnvSolve-Pro improve Official Pass@1 over Repo2Run, native coding agents,
  and same-model agent loops?
- **RQ2:** How much comes from exposing the public goal, maintaining explicit constraint
  state, and updating that state with executable feedback?
- **RQ3:** Does the method recover more often after an initial failed deployment, and
  does the effect persist across repositories, models, and execution platforms?

### Comparisons

The main controlled comparison uses the same model, tools, public goal, terminal
evaluator boundary, and experimental limits:

1. a free-form agent loop without the executable goal;
2. a goal-aware free-form agent loop without structured state;
3. EnvSolve-Pro with Observation, Constraint, and Operation layers.

Repo2Run and native coding agents provide external system baselines. Frozen EnvSolve v1
is retained as a historical structured baseline. Ablations remove goal-state persistence,
finding-routed repository evidence, the retained candidate anchor, and the Fail/Unknown
distinction one at a time. A direct state-persistence ablation compares fresh-candidate
search with postcondition-gated persistent construction and mandatory clean replay.

### Protocol and Metrics

Development, qualification, and final evaluation are separated by repository identity.
Algorithm changes use only completed development trajectories; qualification and test
repositories remain hidden until the corresponding version is frozen. Every terminal
candidate is evaluated from a clean environment, and official outcomes never enter an
online repair loop.

Official Pass@1 is primary. We additionally report first-attempt success, repair success
conditioned on an initial failure, attempts to success, clean replay, and Unknown rate.
Tokens, model requests, candidate environments, commands, and wall-clock time characterize
efficiency and success-resource trade-offs. Network and provider incidents are reported
as censored infrastructure outcomes rather than algorithm failures.
Logical model calls and provider transport attempts are reported separately.

For EnvBench Python, the public goal is successful bootstrap followed by zero
`reportMissingImports`; the official implementation remains terminal-only. The same goal
contract is supplied to all goal-aware controlled methods. Final tables will be produced
only after code, prompts, goal contracts, split identities, and analysis rules are frozen.

### Current Development Evidence

A preregistered repository-disjoint qualification compared postcondition-persistent
explicit state, fresh explicit search, and postcondition-persistent raw history on five
development repositories. All 15 episodes passed integrity and eligibility audits.
Each condition achieved `4/5` Official Pass, passing the same repositories and failing
the same one. This is a useful negative result: it demonstrates executable,
postcondition-gated reuse, but not a success-rate gain.

Persistent explicit state recorded six reused-construction verifications, and two reused
lineages produced programs that later passed clean replay. Relative to persistent raw
history, it used fewer candidates and tokens and roughly half the aggregate generation
time. Relative to fresh explicit search, it used slightly fewer candidates and tokens
but more wall-clock time because mandatory clean replay adds overhead on easy cases.
With five repositories and one stochastic seed, these resource differences are
diagnostic rather than an efficiency claim.

The shared failure identifies a sharper Operation-layer problem. All methods reduced the
goal to seven unresolved findings, then repeated infeasible build-tool paths or proposed
integrity-invalid ways to materialize import artifacts. Explicit state preserved what
was missing, but did not ensure that a proposed operation was relevant, feasible, or
causally progressive. The next frozen revision therefore adds executable operation
preconditions, constraint-to-operation relevance, progress certificates, and
duplicate-failure-family suppression. This evidence narrows the paper's method rather
than adding new semantic rule types.
