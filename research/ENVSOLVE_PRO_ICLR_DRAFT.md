# EnvSolve-Pro: Partially Observable Stateful Constraint Solving for Repository Deployment

## Abstract

Reproducing a source repository requires discovering runtime, dependency, build, and
platform conditions that are rarely specified completely. An agent observes these hidden
conditions only through repository evidence and the outcomes of programs executed in
fresh environments. Current deployment agents leave this state implicit in a growing
language-model context. They can therefore optimize convenient proxy tests, forget an
unresolved failure, or mistake an infrastructure incident for evidence about the
deployment.

We formulate repository deployment as **partially observable stateful constraint
solving** and introduce EnvSolve-Pro. A public executable goal defines success without
revealing terminal benchmark outcomes. An Observation layer executes each candidate and
the goal in the same fresh environment, preserving provenance and distinguishing Pass,
Fail, and Unknown. A Constraint layer turns goal-grounded failures into revisable
obligations while retaining uncertain repository inferences as hypotheses. An Operation
layer exposes this state to a strong language model, which remains free to generate a
complete deployment program rather than choosing from a closed action vocabulary.
Execution updates the state, and only a goal-passing, integrity-valid candidate is
certified.

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

The agent cannot inspect `z` directly. At round `t`, it runs candidate `P_t` in a fresh
environment and receives observation `o_t`: command outcomes, goal diagnostics, and
infrastructure signals. Each observation reveals only part of the relevant state.
Different causes can produce similar symptoms, some failures expose only the first
violated condition, and network or provider incidents may yield no valid task evidence.
The agent must therefore revise beliefs and obligations across attempts.

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

Unknown is never converted into task failure or success. Fresh environments prevent an
unrecorded mutation from one attempt from silently changing a later attempt. Goal reports
also declare whether their findings are a complete snapshot or partial evidence. Only a
complete snapshot of the same scope may use absence to demonstrate that an earlier
condition has been resolved.

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
belong to the candidate. They do not prescribe a solution. A candidate is certified only
when its goal state is Pass and its execution effects satisfy these checks.

## 3. Contributions

1. **Problem formulation.** We formulate repository deployment as partially observable
   stateful constraint solving with a public executable goal, separating online evidence
   from hidden terminal evaluation.
2. **Method.** We introduce a strong-model-compatible three-layer solver that preserves
   authoritative goal observations, maintains revisable constraint state, and leaves the
   operation space open.
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
distinction one at a time.

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

A frozen five-case development qualification does not yet establish a success-rate
advantage. The two integrity-valid pairs completed by both methods passed under both
explicit state and raw history; explicit state showed lower search burden, but the sample
is too small and provider timing is too variable for an efficiency claim. More
importantly, the batch exposed two general bottlenecks: small verified repairs repeatedly
replay expensive installation prefixes, and a symlink can create a synthetic import
alias that satisfies the surface goal. We therefore harden the integrity boundary before
testing postcondition-verified state preservation and minimal state transformation as
an Operation-layer mechanism. A post-hoc external-agent trajectory independently
exposed the distinction between command failure and resulting state, as well as verifier
scope changes caused by environment location. All final programs remain subject to
clean full replay.
