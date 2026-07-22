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
Because internal checks are themselves partial observations, EnvSolve distinguishes a
candidate certified by its internal goal from an admissible candidate that completed safe
execution but retains unresolved constraints. It preserves the best admissible candidate
rather than treating the internal verifier as a terminal oracle.

We will compare EnvSolve-pro with Repo2Run, a native strong agent, same-backbone ReAct,
and frozen EnvSolve v1 on EnvBench. Official Pass@1 is primary; tokens, calls,
environments, and time are efficiency measures. A diagnostic qualification on consumed
trajectories found that closed command parsing censored executable baseline behavior and
non-equivalent workspaces hid deployment conflicts. Replacing that interface with open
programs, fresh execution, audited effects, and benchmark-declared preconditions removed
representation rejection while exposing the underlying failures. A subsequent diagnostic
identified over-hardening of internal feedback as a cross-repository failure mode. Two
independently selected eight-case censuses did not replicate one dominant blocking label,
but both located most failures at the interface between constraint closure and viable
operations. These studies motivate the method but do not estimate effectiveness, which
remains to be tested on untouched cases.

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
may challenge soft beliefs. Internal verification narrows uncertainty but does not define
terminal correctness.

The **Operation layer** lets a strong model generate self-contained deployment programs.
The system enforces only environment-modification and safety boundaries plus exact
prohibitions grounded by execution counterexamples; other operation plans are advisory.
Candidates remain open programs rather than members of a closed command vocabulary.
Fresh isolated execution and audited effects determine validity, return evidence to the
Observation layer, and close the loop. A benchmark adapter declares non-outcome state
that must exist before both internal and terminal execution, preventing the solver from
being evaluated under easier hidden preconditions.

Across rounds, EnvSolve retains a small candidate frontier. A **certified** candidate
satisfies the internal goal and terminates early. An **admissible** candidate has completed
safe, integrity-valid execution with no unknown verification state but retains residual
constraints. If search ends without certification, the best admissible candidate remains
eligible for terminal evaluation and is explicitly labeled uncertified. This preserves
the distinction between solver belief and benchmark outcome.

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

Diagnostic studies establish the measurement and mechanism assumptions without making
an effectiveness claim. Open programs and state-parity preconditions removed
representation censoring; a consumed paired test showed that retaining safe uncertified
candidates improved terminal reach but not Official Pass. Two independent trajectory
censuses then disagreed on whether closure or operation was the largest single category,
yet placed `11/16` cases in those two adjacent categories. Their shared causes were
missing runtime/platform frontiers, flat obligations without causal scope, and incorrect
trust boundaries. This evidence motivates a provenance-linked causal constraint frontier;
its effectiveness will be tested only after the method and evaluation boundary are frozen.
