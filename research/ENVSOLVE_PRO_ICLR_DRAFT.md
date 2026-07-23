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
its Constraint layer organizes surface symptoms into a revisable causal constraint
frontier; and its Operation layer lets a strong language model generate complete
deployment programs whose executions update state. The frontier advances scope per
observation channel, links surface failures to executable root conditions, and preserves
both Unknown and raw evidence. It is an external cognitive tool rather than a closed
action language: the model may act outside the current schema, while hard guards are
limited to task safety and behavior directly contradicted by execution.
Because internal checks are themselves partial observations, EnvSolve distinguishes a
candidate certified by its internal goal from an admissible candidate that completed safe
execution but retains unresolved constraints. It preserves the best admissible candidate
rather than treating the internal verifier as a terminal oracle.

We will compare EnvSolve-pro with Repo2Run, a native strong agent, same-backbone ReAct,
and frozen EnvSolve v1 on EnvBench. Official Pass@1 is primary; tokens, calls,
environments, and time are efficiency measures. Two independent development censuses
place `11/16` failures at the interface between constraint closure and viable operations.
An offline mechanism analysis on consumed trajectories groups `93/94` surface module
obligations into `37` executable roots, with maximum `25:1` symptom amplification. These
results motivate and qualify the representation; success claims are reserved for new
untouched cases after method freeze.

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

The **Constraint layer** represents what is currently missing or conflicting as a
revisable causal frontier. Fresh-execution `missing_name` observations, explicit runtime
compatibility statements, and environment identity connect many surface failures to a
shared root while preserving scope, source role, path, and trust. Observation channels
advance independently, so absence of a new observation is not evidence of resolution;
a newer observation of the same channel may confirm or retire an old root. Deterministic
evidence may form hard facts, ambiguous explanations remain hypotheses, and Unknown is
not hardened. The model also retains bounded raw evidence and may challenge soft beliefs.
The complete internal frontier and the model-visible projection are versioned separately:
the bounded projection packs executable roots before descriptive facts and reports all
omissions, so compression cannot replace the constraint object with an unparseable text
fragment.

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
2. We introduce a strong-model-compatible three-layer algorithm whose channel-scoped
   causal frontier compresses repeated symptoms while preserving provenance, Unknown,
   and actions outside the current schema.
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

Diagnostic studies establish measurement and mechanism assumptions without making an
effectiveness claim. Open programs, state-parity preconditions, and candidate retention
first remove representation and terminal censoring. P5 then pairs flat state with the
causal frontier on three consumed mechanism cases and measures root appearance,
recurrence, and closure while auditing the exact persisted model-visible state for digest,
schema, and completeness. A failed measurement gate excludes outcomes from effect
statistics. Only a preregistered mechanism gate permits consumption of a new
outcome-blind Dev batch. Final confirmation freezes code, prompts, analysis, and evaluator
access and separates development and test by repository identity.
