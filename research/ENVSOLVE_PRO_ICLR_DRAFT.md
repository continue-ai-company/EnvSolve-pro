# EnvSolve-Pro: Partially Observable Stateful Constraint Solving for Repository Deployment

Status: working ICLR paper draft, 2026-08-27; held-out and external-baseline results pending

## Abstract

Automatically deploying an unfamiliar repository is not merely command generation. An
Agent observes compatibility facts only through execution, each action changes what can
be observed next, and a working interactive environment may not be reproducible from a
clean checkout. We formulate repository deployment as **partially observable stateful
constraint solving**.

We first introduce an auditable trajectory representation and classify the earliest
decisive failure into three causal layers: Observation, Constraint, and Operation. Across
development trajectories, two recurring failures are optimizing an incomplete proxy for
the scored goal and failing to convert a working construction state into a program that
recreates it. We then propose EnvSolve-Pro, a minimal three-layer algorithm. A capable
Agent remains free in one continuous session; the harness periodically executes the
complete public goal; a goal-passing state triggers immediate delivery of the cumulative
program; and the exact program is replayed from the target initial state. Replay failures
return executable, case-local constraints to the same session without prescribing a
repair.

Consumed development cases qualify this mechanism, including multi-step Fail-to-Pass
repairs and removal of a previously observed goal-to-delivery delay. They do not establish
generalization. Our final evaluation freezes the algorithm before an outcome-blind batch,
compares it with matched same-model controls, EnvBench baselines, Repo2Run, prior
hard-constraint EnvSolve, and native coding Agents, and tests both strong and weaker
backbones. Official Pass@1 is primary; time, tokens, network, and storage are optimized
only after success is preserved.

## 1. Problem

Given repository revision \(x\), target initial environment \(E_0\), and public executable
goal \(G\), an Agent interacts with a construction environment and returns a deployment
program \(P\). The delivered environment is

\[
E_P = R(P, E_0),
\]

where \(R\) executes the complete program from the target initial state. Deployment
succeeds when \(G(E_P)=1\) under a shared integrity-preserving evaluator.

The problem is partially observable because dependency resolution, build isolation,
interpreter identity, native libraries, ABI, hardware, network behavior, and process-local
state become visible only after particular actions. It is stateful because each action
changes the environment and therefore future evidence. Interactive success is
insufficient: failed commands leave side effects, shell state may be ambient, and the
delivered program may omit an operation performed during exploration.

Time and request limits are experimental conditions rather than part of the task
definition. Success is primary. Resource use is measured under matched broad safety
limits and compared unconditionally and among successful episodes.

## 2. A Causal Failure Framework

We label the earliest failure that changes the terminal outcome, rather than the last
error message. Infrastructure failures and invalid measurement episodes are censored.

### 2.1 Observation: What happened?

An Observation failure occurs when necessary evidence is absent, measured in the wrong
environment, discovered too late, or mistaken for complete evidence. Examples include
testing a different interpreter from the delivered program and validating accumulated
construction state while claiming a clean deployment.

### 2.2 Constraint: What must now hold?

A Constraint failure occurs when evidence is not converted into the compatibility
condition required for success. Examples include confusing import and distribution names,
missing a build-time prerequisite, or failing to preserve an already satisfied runtime
condition during a later installation. An incorrect harness admissibility rule is also a
Constraint-layer measurement failure.

### 2.3 Operation: How should the state change?

An Operation failure occurs when the chosen transformation cannot satisfy the active
condition, is ordered incorrectly, or is omitted from the delivered program. The Agent,
not the harness, is responsible for selecting packages, interpreters, commands, and repair
strategies.

The layers form a causal loop: observations expose constraints, constraints guide
operations, and operations create the next state and observation. The framework describes
failure causes; it is distinct from deployment paradigms. Free trial-and-error,
hard-constraint, goal-aware soft-constraint, and replay-grounded systems can all be
compared by their distributions over the same three layers.

## 3. EnvSolve-Pro

EnvSolve-Pro keeps the three layers explicit while minimizing controller policy.

### Observation Layer

The Agent receives ordinary command feedback in a persistent construction environment.
At a fixed cadence, the harness executes the complete trusted public goal in that same
state and returns the result to the active session. Submitted programs are additionally
observed by executing the complete program and goal from the target initial state, not
from accumulated construction state.

### Constraint Layer

Goal residuals and replay failures are executable, case-local facts. A replay failure
means that the current complete program does not reconstruct a goal-satisfying state.
Raw evidence remains visible, and the Agent may revise or reject its interpretation. The
harness adds no package-rule library, cross-case experience, checkpoint graph, or
model-selected repair policy.

### Operation Layer

The Agent freely inspects the repository and changes the construction environment. When
a trusted observation first reports that the complete goal passes, the controller asks
for the cumulative deployment program on the next model turn and atomically replays it.
A failed replay restores unrestricted tool choice and returns its counterexample to the
same session. A candidate is delivered only when that exact program passes from the target
state.

```text
start one Agent session and one construction environment

while no replay-passing program exists and broad safety limits remain:
    let the Agent freely observe and modify the construction state
    periodically execute the complete trusted goal
    if the goal has not passed:
        continue
    request the cumulative deployment program on the next turn
    y <- execute the program and goal from the target initial state
    if y passes:
        return the program
    return y to the same session and restore free repair

return failure
```

The controller decides only when evidence is measured and when an already goal-passing
state must be expressed as a deliverable. It does not choose the next environment-changing
operation. Stronger models therefore expand the Operation layer rather than being replaced
by a closed planner. The algorithm stores programs and trajectories, not container
checkpoints.

## 4. Contributions

1. **Causal failure analysis.** We provide an auditable trajectory representation and an
   Observation--Constraint--Operation taxonomy that identifies the earliest decisive
   cause across different deployment paradigms.
2. **A minimal deployment algorithm.** EnvSolve-Pro couples trusted goal observation,
   immediate program delivery, and target-state replay inside one unrestricted Agent
   session, turning replay failures into executable case-local constraints.
3. **Controlled empirical evidence.** We compare matched mechanisms, external systems,
   and strong and weaker backbones using Official success, causal failure transitions,
   deployment completeness, and success-preserving resource outcomes.

## 5. Experimental Design

### 5.1 Failure Study

We collect complete trajectories from EnvBench agents, Repo2Run, native coding Agents,
prior hard-constraint EnvSolve, goal-aware free search, and EnvSolve-Pro. Each scientifically
valid failure receives one evidence-linked primary layer and secondary mechanism tags. A
stratified sample is independently re-annotated and inter-annotator agreement is reported.
Terminal error counts alone are not labels, and infrastructure or faulty-harness episodes
do not enter algorithmic prevalence estimates.

The paper compares four deployment paradigms: free trial-and-error, hard constraints,
goal-aware soft constraints, and target-state replay. The evaluator-integrity boundary is
shared infrastructure, not a fifth algorithm. The analysis asks how each paradigm shifts
failure mass across Observation, Constraint, and Operation.

### 5.2 Same-Model Mechanism Test

Under the same model and execution conditions, we separate repository-feedback free
search (`F`), free search with the complete executable goal (`F+O`), and EnvSolve-Pro's
scheduled observation plus atomic target-state replay (`F+O+R`). The first contrast tests
goal observability. The second tests whether early complete-program counterexamples improve
delivery after the goal is visible. All environment-changing choices remain model actions.

Development trajectories are used to discover failure types and choose one fixed method.
Although EnvSolve-Pro has no learned parameters, a separate outcome-blind batch is still
necessary: code, prompts, cadence, boundaries, and stopping logic can otherwise overfit
consumed repositories. Held-out cases estimate performance only after those choices are
frozen.

### 5.3 System and Model Comparisons

System comparisons include EnvBench baselines, Repo2Run, frozen prior EnvSolve, and native
Codex as an independent capability frontier. Repo2Run is treated as a stateful loop, not a
one-shot baseline: it preserves dialogue and construction state and rolls back selected
failed commands. The narrower distinction tested by EnvSolve-Pro is whether the complete
deliverable is executed from the target initial state and its counterexample is returned
before the active reasoning session ends.

Strong and weaker backbones test whether replay-grounded constraints complement model
capability or are absorbed by model progress. Official Pass@1 is primary. Secondary
outcomes are failure-layer transitions, replay-to-Official agreement, deployment
completeness, requests, tokens, wall time, network traffic, and storage. Official success
and broader runtime completeness are reported as separate axes.

## 6. Current Evidence and Claim Boundary

The current trajectory reconstruction contains 48 method--case rows and 38 non-success
rows. A provisional single-reviewer pass identifies 25 algorithmically attributable
failures: 14 Observation, seven Constraint, and four Operation. Nine infrastructure-unknown
and four protocol-censored rows are excluded. Independent annotation is pending, so these
counts support taxonomy development but not population prevalence.

Earlier consumed studies show that optional replay can be ignored and that replay after
late delivery may arrive too late for repair. A failure-enriched six-case study produced
three same-session Fail-to-Pass replay repairs, but also exposed goal-passing states that
were never delivered. More controlling candidate-retention policies regressed, motivating
the smaller state transition used here.

The latest outcome-conditioned three-case qualification couples periodic trusted
observation to immediate atomic handoff. Quacc, Ajenti, and Hark all submitted on the model
request immediately following the first trusted goal Pass. Quacc and Hark passed Official
after same-session replay repair. Ajenti's original episode failed because the old harness
misclassified ordinary installed modules as unowned; a separately specified no-model
adjudication replayed the exact submitted program, which passed both the corrected clean
replay and unchanged Official evaluator. The original Ajenti episode remains Fail and is
censored from algorithm-effect attribution.

These results qualify the mechanism on consumed cases. They do not estimate held-out
success, significance, generalization, leaderboard performance, or SOTA. The next valid
effect claim requires the frozen algorithm on an outcome-blind repository-disjoint batch
with matched controls, followed by external baselines and strong/weak backbone tests.

## 7. Falsification and Scope

The central claim is weakened if matched outcome-blind experiments show no Official gain,
if replay counterexamples do not change subsequent programs, if clean replay and Official
diverge under the same target state, or if gains disappear for stronger models. A success
gain with higher resource use is a success--cost tradeoff, not an efficiency improvement.

This paper studies a fixed deployment algorithm. Harness self-optimization belongs to
Auto-EnvSolve, and learned deployment policy belongs to EnvSolve-RL. We retain compatible
trajectory artifacts for those projects but do not place their mechanisms in EnvSolve-Pro.
