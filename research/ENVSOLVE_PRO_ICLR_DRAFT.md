# EnvSolve-Pro: Partially Observable Stateful Constraint Solving for Repository Deployment

Status: working ICLR paper draft, 2026-08-31; held-out and external-baseline results pending

## Abstract

Automatically deploying an unfamiliar repository is not merely command generation. An
Agent observes compatibility facts only through execution, each action changes what can
be observed next, and a working interactive environment may not be reproducible from a
clean checkout. We formulate repository deployment as **partially observable stateful
constraint solving**.

We first introduce an auditable trajectory representation and classify the earliest
decisive failure into three causal layers: Observation, Constraint, and Operation. The
current minimal scaffold keeps a capable Agent in one continuous session, executes every
candidate from the target initial state, returns replay counterexamples to the same
session, and delivers exactly the replay-passing program. This separates interactive
progress from reproducible deployment without constraining the Agent's operations.
A preregistered development test found that additionally exposing a live compatibility
frontier improved observability but not Official success, so it is excluded from the core
method. The remaining algorithmic question is narrower: how to help the Agent determine
whether residual constraints have a legal solution and turn that solution into a
deliverable without adding a brittle rule system.

Consumed development cases qualify the mechanism but do not establish generalization.
Our final evaluation fixes the algorithm before outcome-blind evaluation, compares it
with matched same-model controls, EnvBench baselines, Repo2Run, prior hard-constraint
EnvSolve, and native coding Agents, and tests strong and weaker backbones. Official
Pass@1 is primary; time, tokens, network, and storage are optimized only after success
is preserved.

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

EnvSolve-Pro keeps the three layers explicit while minimizing controller policy. The
method described here is the current empirical incumbent; the final constraint-layer
intervention is not yet fixed.

### Observation Layer

The Agent receives ordinary command feedback in a persistent construction environment.
It may execute the public goal and submit a complete program for target-state replay at
any time. Commands, goal observations, environment identity, replay evidence, and Official
outcomes are retained in one auditable trajectory.

### Constraint Layer

The active Agent infers case-local constraints from raw execution and clean-replay
counterexamples. The harness does not currently maintain a second model-external
compatibility frontier: matched Dev evidence showed that exact residual deltas can be
valid and causally used without resolving provider satisfiability or candidate delivery.
A narrow shared integrity boundary prevents evaluator-only configuration or type stubs
from changing the task; it does not choose packages or operations. The method adds no
package-rule library, cross-case experience, checkpoint graph, or repair policy.

### Operation Layer

The Agent freely inspects the repository, chooses every environment transformation, and
decides when the active state is ready. It then synthesizes a self-contained program
rather than inheriting the exploratory command history. A failed clean replay preserves
the active session and returns its counterexample. A passing replay returns the exact
certified program immediately, including on the final allowed model request.

```text
start one Agent session and one construction environment

while no replay-passing program exists and broad safety limits remain:
    action <- Agent freely inspects or changes the construction state
    if the Agent submits a self-contained deployment program:
        replay <- execute the exact program and goal from the target initial state
        if replay passes: return the program
        return replay to the same session

return failure
```

The controller binds delivery to clean replay and returns failures without ending the
reasoning session. It neither chooses packages nor decides the next operation. Stronger
models therefore expand the Operation layer rather than being replaced by a closed
planner. The algorithm stores programs and trajectories, not container checkpoints. The
live-frontier treatment remains an analysis instrument and ablation, not part of this loop.

## 4. Contributions

1. **Causal failure analysis.** We provide an auditable trajectory representation and an
   Observation--Constraint--Operation taxonomy that identifies the earliest decisive
   cause across different deployment paradigms.
2. **A minimal deployment algorithm.** EnvSolve-Pro keeps search in one unrestricted
   Agent session and makes target-state replay an iterative executable counterexample and
   exact-delivery primitive. The final constraint intervention must earn inclusion through
   Official success rather than architectural complexity.
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

Under the same model and execution conditions, Minimal B is the fixed control: one
continuous free Agent plus repeatedly callable target-state replay (`F+R`). Each proposed
algorithmic addition is tested as one matched treatment. Accumulated editable programs,
scheduled observation, forced handoff, checkpoint-like retention, and live compatibility
frontiers have failed to improve success consistently and are not combined into the core.
The next treatment is selected only after the trajectory taxonomy identifies a dominant
cross-repository constraint or delivery failure. All environment-changing choices remain
model actions.

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

Strong and weaker backbones test whether executable state feedback complements model
capability or are absorbed by model progress. Official Pass@1 is primary. Secondary
outcomes are failure-layer transitions, replay-to-Official agreement, deployment
completeness, requests, tokens, wall time, network traffic, and storage. Official success
and broader runtime completeness are reported as separate axes.

## 6. Current Evidence and Claim Boundary

Trajectory reconstruction currently supports the O/C/O taxonomy but not prevalence:
independent annotation is pending, and infrastructure or protocol-censored episodes are
excluded from algorithmic failure counts. Deployment paradigms and failure causes remain
separate variables.

Development ablations reject final replay alone, editable accumulated programs, fixed
observation cadence, forced handoff, and checkpoint-like candidate retention as the core
method. Their common weakness is that useful executable evidence arrives too late or is
coupled to a controller policy that adds cost without reliably improving the next action.

In the completed six-pair accumulated-program ablation, the simpler continuous-Agent
control achieved 5/6 effective Official passes versus 4/6, while using 15% fewer model
requests, 42% fewer tokens, 36% less wall time, and seven rather than 24 clean replays.
We therefore retain final replay as certification but remove accumulated construction
commands from the method.

The first consumed-case qualification of operation-linked feedback produced goal replay
success for both methods on all three pairs. EnvSolve-Pro reduced aggregate requests,
tokens, shell calls, and wall time, driven by one severe false-progress loop; it was more
expensive on another case and provided no useful signal when the Agent left its selected
Python environment inside a temporary subshell. This supports a fixed Dev test of the
mechanism, not a success-rate, SOTA, or generalization claim.

A prospective four-pair development test then exposed two measurement defects. Both arms
could obtain Official Pass by changing Pyright semantics with untracked configuration or
type-only providers, and a replay Pass on the final model request could be discarded by a
second submission step. Among the two validity-adjudicated pairs, both methods succeeded;
the frontier was substantially cheaper on one case and slower on the other. On Meerkat,
repeated frontier snapshots nearly doubled prompt tokens relative to the matched control.
We therefore reject that historical-snapshot V5 and advance only the simpler current-state,
validity-aware variant described above.

A consumed Pysnmp regression exercised the complete live-frontier loop and passed Official,
establishing mechanism operation but not an effect. The subsequent preregistered matched
three-pair study produced one Official Pass in each arm. On their shared success, the
frontier used 33% fewer requests and 37% fewer tokens but took 18% longer. On a shared
request-cap failure it used 5% more tokens and 21% more time. It also reached zero observed
obligations on TensorFlow Model Analysis yet failed Official because the candidate ended
outside the repository. We therefore reject the frontier as the core method, add a shared
final-working-directory replay postcondition, and do not rewrite the recorded outcome.

The negative result narrows the next question. More precise residual reporting is
insufficient when the Agent cannot determine whether a legal provider set exists or does
not convert a diagnosed state into a candidate. An outcome-blind audit of five existing
hard failures motivated an explicit executable-hypothesis treatment. Two preregistered
activation-only runs rejected it before effect testing: despite many applicable provider
operations, the model never selected the optional action channel. We retain this as a
negative design result rather than calling an unused tool an algorithm. The next constraint
intervention remains unselected; Minimal B is the current executable scaffold, not yet the
paper's final method.

All current results are development evidence. Official success and deployment
completeness are reported separately, and repository-unseen claims are reserved for
protected Canary and Official Test data after the method and boundary are fixed.

## 7. Falsification and Scope

The central claim is weakened if the final matched treatment shows no Official gain, if
its structured evidence does not change subsequent actions, if clean replay and Official
diverge under the same target state, or if gains disappear for stronger models. A success
gain with higher resource use is a success--cost tradeoff, not an efficiency improvement.

This paper studies a fixed deployment algorithm. Harness self-optimization belongs to
Auto-EnvSolve, and learned deployment policy belongs to EnvSolve-RL. We retain compatible
trajectory artifacts for those projects but do not place their mechanisms in EnvSolve-Pro.
