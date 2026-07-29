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
layer gives a strong language-model agent an open terminal for diagnosis and asks it to
submit a complete deployment program. Candidate rejection, execution failure, and goal
findings become verified state for a subsequent repair round instead of ending the
search. The action space remains open, while executable validation prevents source
editing, synthetic capability injection, and other invalid shortcuts. The exact final
program is certified only after passing in a fresh environment.

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

The Operation layer is a general-purpose agent, not a closed planner. It receives the
public goal, the current constraint ledger, the best integrity-valid program, and the
small amount of raw evidence needed to interpret unresolved findings. It may inspect the
repository, install packages, change runtimes, invoke build systems, and test hypotheses
through an open terminal. Structured state guides attention but does not prescribe a
command vocabulary.

After diagnosis, the agent submits a cumulative, self-contained deployment program.
The harness validates the program, executes it in isolation, and runs the public goal in
the same shell and environment. A policy rejection, command failure, complete finding
delta, or effect violation is returned to the next agent round as an Observation. This
matters because a capable agent may find useful environment facts yet submit an invalid
shortcut; discarding the entire trajectory wastes information, while accepting the
shortcut confounds deployment with verifier manipulation.

The resulting loop is

```text
observe -> update constraints -> agent diagnosis -> submit program
        -> validate and execute goal -> observe.
```

Safety and integrity checks define admissibility, not the solution. A construction-state
Pass triggers mandatory replay of the exact program in a distinct fresh environment.
Only a fresh Pass with valid repository effects is certified.

## 3. Contributions

1. **Problem formulation.** We formulate repository deployment as partially observable
   stateful constraint solving with a public executable goal, separating online evidence
   from hidden terminal evaluation.
2. **Method.** We introduce a strong-model-compatible three-layer solver that preserves
   authoritative goal observations, maintains minimal revisable constraint state, and
   turns candidate validation and clean replay into feedback for an open strong-agent
   operation loop.
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
2. a single-session goal-aware agent;
3. a multi-session goal-aware agent with raw prior feedback;
4. EnvSolve-Pro with structured current state and the same raw evidence.

Repo2Run and native coding agents provide external system baselines. Frozen EnvSolve v1
is retained as a historical structured baseline. Core ablations remove goal-state
persistence, policy-rejection feedback, the retained valid program, and the Fail/Unknown
distinction. A model-strength sweep tests whether the structure complements rather than
constrains stronger agents.

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
Reaching a frozen method limit without a passing answer is a non-pass; independently
attributable infrastructure and measurement failures are censored. Compared conditions
receive the same initial image and method-independent cache state.

For EnvBench Python, the public goal is successful bootstrap followed by zero
`reportMissingImports`; the official implementation remains terminal-only. The same goal
contract is supplied to all goal-aware controlled methods. Final tables will be produced
only after code, prompts, goal contracts, split identities, and analysis rules are frozen.

### Current Development Evidence

A five-repository qualification found identical `4/5` Official Pass for explicit
state, fresh search, and raw history. A later eight-case paired screen found that a more
complex causal-feedback variant achieved `3/7`, while its simpler goal-frontier control
achieved `4/7`. These negative results reject the hypothesis that adding more constraint
types is sufficient.

External trajectories sharpen the alternative. Repo2Run stopped on Lark after native
tests passed while the public goal still had 13 issues. A goal-aware strong agent instead
found a valid Conda solution by diagnosing package shadowing. On micropy-cli, the same
agent reduced the public metric to zero using synthetic stubs and was correctly rejected.
The active hypothesis is therefore that verified state should support a strong
interactive operation loop and make rejection recoverable, while executable validation
and clean replay remain hard boundaries. This hypothesis has not yet established an
effectiveness gain.

A first consumed mechanism study further exposed two requirements for testing this
hypothesis correctly. All raw-history and structured-state episodes ended after the
first model submission, so explicit repair state never affected an operation. Moreover,
both micropy-cli conditions passed the benchmark by mixing the target checkout with an
older same-name distribution. We therefore require an executable goal observation
before the first operation and source-consistent namespace provenance in addition to
fresh replay. These are method-contract corrections, not performance results.

The corrected mechanism then produced the intended transition. A complete pre-operation
goal failure became a compact obligation state; an inadmissible first program was
returned with an exact violation; and a second independent session produced an Official
Pass. The same trace separated source provenance from module identity: package metadata
can relabel checkout source without changing its bytes. We therefore treat executable
success and identity-qualified success as distinct measurements. This consumed result
validates the loop, not its cross-repository effectiveness.
