# EnvSolve-pro: Partially Observable Stateful Constraint Solving for Repository Deployment

## Abstract

Running an unfamiliar source repository requires recovering runtime, dependency, build,
and platform conditions that the repository rarely specifies completely. An agent can
only partially observe these hidden conditions through repository evidence and noisy
execution outcomes. Existing deployment agents commonly append raw logs to a growing
context and generate another command, leaving state tracking implicit and making
candidate errors, incorrect hypotheses, and infrastructure censoring difficult to
distinguish.

We propose EnvSolve-pro, which formulates deployment as partially observable stateful
constraint solving. Its Observation layer preserves provenance-linked execution evidence;
its Constraint layer maintains revisable facts, hypotheses, contradictions, and unresolved
obligations; and its Operation layer lets a strong language model generate complete
deployment programs whose executions update state. Structured state is an external
cognitive tool rather than a closed action language: raw evidence remains available, and
hard guards are limited to task safety and behavior directly contradicted by execution.

We will compare EnvSolve-pro with Repo2Run, a native strong agent, same-backbone ReAct,
and frozen EnvSolve v1 on EnvBench. Official Pass@1 is primary; tokens, calls,
environments, and time are reported as efficiency measures. The study is currently in
the fair-interface qualification stage and makes no effectiveness claim yet. An initial
five-case trajectory audit found that native successes can be erased by closed post-hoc
command parsing or non-equivalent verification workspaces, motivating an execution- and
effect-based candidate boundary before algorithm comparison.

## 1. Problem

For repository `R`, let `Z_R` denote the unobserved set of valid environment conditions.
At round `t`, an agent selects deployment program `P_t` and receives partial observation
`O_t` after fresh execution. Similar symptoms can arise from different hidden causes, and
network or provider failures can make an outcome uninformative. Deployment therefore
requires maintaining a state over hidden environment conditions, not only generating
shell commands.

EnvSolve-pro maintains `S_t=(X_t,F_t,H_t,C_t,U_t)`: raw evidence, facts, hypotheses,
contradictions, and operation obligations. Updates use repository and internal execution
feedback only. The Official evaluator scores the terminal candidate and never enters the
online loop. The objective is final deployment success; resource limits belong to the
experimental protocol rather than the problem definition.

## 2. Method

The **Observation layer** records repository declarations, environment identity, complete
candidates, command outcomes, verifier results, and infrastructure signals while keeping
Pass, Fail, and Unknown distinct.

The **Constraint layer** maintains what is currently known. Deterministic evidence may
form hard facts; ambiguous explanations remain provenance-linked hypotheses; Unknown is
not hardened. The model can inspect both structured state and relevant raw evidence and
may challenge soft beliefs.

The **Operation layer** lets a strong model generate self-contained deployment programs.
The system enforces only environment-modification and safety boundaries plus exact
prohibitions grounded by execution counterexamples; other operation plans are advisory.
Candidates remain open programs rather than members of a closed command vocabulary.
Fresh isolated execution and audited effects determine validity, return evidence to the
Observation layer, and close the loop.

## 3. Contributions

1. We formulate real repository deployment as partially observable stateful constraint
   solving, separating hidden environment conditions, online execution feedback, and
   terminal evaluation.
2. We introduce a strong-model-compatible three-layer algorithm whose provenance-aware
   state remains revisable and whose model can discover solutions outside the current
   schema.
3. We establish an external-baseline-driven evaluation of final success, mechanism value
   under stronger models, failure recovery, and success-resource trade-offs.

## 4. Research Questions

- **RQ1 Effectiveness:** Does EnvSolve-pro improve Official Pass@1 over Repo2Run, a native
  strong agent, and raw ReAct?
- **RQ2 Mechanism:** What do structured Observation, advisory Constraint state, and
  grounded hard guards contribute, and do they complement, become redundant with, or
  harm stronger models?
- **RQ3 Robustness:** Does the method improve post-failure repair and clean replay across
  repositories, models, and execution platforms?

## 5. Evaluation

Development begins by directly observing external baselines on new Dev cases before any
algorithm revision. Core ablations progressively add structured Observation, advisory
Constraint state, and grounded guards to raw ReAct; frozen EnvSolve v1 is an independent
baseline. Mac and DGX Spark may run cases in parallel, while paired comparisons record
and control platform, image, and network censoring.

Official Pass@1 is primary. Secondary outcomes include terminal reach, post-first-failure
repair, clean replay, repeated failures, and Unknown rate. Tokens, requests, candidate
environments, commands, and wall-clock time support efficiency and Pareto analysis only.
All methods share a terminal-only Official evaluator boundary. Canary and Official Test
remain untouched until the method is frozen.

The completed P0 audit is diagnostic only. It establishes that wrapper preservation and
verification-precondition parity are prerequisites for a fair comparison; it does not
support an effectiveness ranking. P1 will qualify these interfaces on synthetic fixtures
and consumed trajectories before drawing a new outcome-blind Dev batch.
