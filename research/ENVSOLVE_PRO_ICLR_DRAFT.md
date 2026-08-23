# EnvSolve-Pro: Verifier-Triggered Replay for Repository Deployment

Status: working ICLR paper draft, 2026-08-23; verifier-triggered handoff is qualified on
consumed evidence, and prospective effectiveness remains untested

## Abstract

Deploying an unfamiliar repository is not merely command generation. The Agent sees only
the compatibility facts exposed by its current actions, those actions change the
environment, and a successful interactive workspace may not be reproducible from a
clean checkout. We formulate repository deployment as **partially observable stateful
constraint solving**.

We first instrument end-to-end deployment trajectories and classify the earliest
decisive failure into three causal layers: Observation, Constraint, and Operation. The
analysis reveals a recurring gap between constructing a working state and delivering a
program that reconstructs that state. We therefore propose EnvSolve-Pro, a minimal
algorithm that keeps a capable Agent free in one continuous session, periodically
measures the complete public goal, and turns the first trusted Pass into an executable
handoff to programization and clean replay. A replay counterexample returns to the same
session as a soft constraint. The method adds no package-rule library, checkpoint search,
cross-case memory, or hard action policy.

A preregistered consumed-case qualification exercised the complete transition: trusted
Pass, controller handoff, clean-replay failure, same-session repair, replay Pass, and
Official Pass. Both arms passed, so this result establishes mechanism operation rather
than effectiveness; its shorter post-Pass tail is descriptive. The next test is a fixed
prospective bad-case comparison with identical tools and prompts before the trigger.
Official Pass@1 is primary; time, tokens, traffic, storage, and deployment completeness
remain separate outcomes.

## 1. Problem

Given repository revision (x), base environment (E_0), and public executable goal
(G), an Agent interacts with a construction environment and returns a deployment
program (P). The delivered state is

[
E_P = R(P, E_0),
]

where (R) executes the complete program from the target initial state. Deployment
succeeds when (G(E_P)=1) under a shared integrity-preserving evaluator.

The challenge is partially observable because dependency resolution, build isolation,
Python identity, native libraries, ABI, hardware, network behavior, and process-local
state become visible only after particular operations. It is stateful because every
operation changes what later operations observe. Interactive success is insufficient:
failed commands leave side effects, shell state may be ambient, and the final program
may omit a repair performed during exploration.

Time and request limits are experimental conditions, not the problem definition.
Success is primary. Resource use is measured under matched broad safety limits and
optimized only after success is preserved.

## 2. Causal Failure Framework

We label the earliest failure that changed the terminal outcome, not the last error
message.

### 2.1 Observation: What happened?

An Observation failure occurs when a necessary fact is absent, observed in the wrong
environment, discovered too late, or treated as complete when it is partial. Examples
include testing a different Python executable from the submitted program and reusing a
construction cache while claiming to test a clean deployment.

### 2.2 Constraint: What must hold?

A Constraint failure occurs when evidence is not converted into the compatibility
condition required for success. Examples include confusing an import name with its
distribution name, missing a build dependency, or failing to preserve an already
satisfied CPU/runtime condition during a later install.

### 2.3 Operation: How should the state change?

An Operation failure occurs when the selected transformation cannot satisfy the active
condition, is ordered incorrectly, or is absent from the delivered program. A hard
harness rule may also cause an Operation failure by rejecting a valid repair.

The layers form a causal loop: observations induce constraints; constraints guide
operations; operations create the next state and therefore the next observation.

## 3. EnvSolve-Pro

EnvSolve-Pro combines free feedback search, trusted goal observation, and target-state
counterexample replay.

### Observation Layer

The Agent receives ordinary construction feedback. At a fixed command schedule, the
harness measures the complete public goal in the same construction environment. Replay
evidence is tied to the repository revision, base image, and fresh execution, and observes
the complete program rather than a selected command or accumulated construction state.

### Constraint Layer

A failed replay yields a case-local soft constraint: the observed state contradicts the
current complete program. Raw evidence remains visible, and the same Agent may revise or
reject its interpretation. The harness does not retrieve cross-case rules or choose a
package.

### Operation Layer

The Agent freely inspects the repository and changes the construction environment. A
complete goal Pass triggers one controller transition: the next model action must express
the current solution as a complete program and replay it. A replay failure restores free
repair in the same session. A candidate is returned only after that exact program passes
from the target state.

```text
start one continuous Agent session in a construction environment

while no replay-passing program exists and broad safety limits remain:
    Agent freely observes and changes the construction environment
    periodically measure the complete public goal
    if the Agent submits voluntarily or the goal first passes:
        obtain the complete deployment program P
    else:
        continue
    y <- execute P and the public goal from the target initial state
    if y passes:
        return P
    return the first executable counterexample in y to the same session

return failure
```

The algorithm stores programs and execution evidence, not container checkpoints. The
controller decides only when verified sufficiency must become a replay attempt; it does
not decide how to repair the environment. The repair loop remains inside the active
reasoning session and operates on the complete deliverable from its actual initial state.
Stronger models therefore enlarge the Operation layer instead of being restricted by it.

## 4. Contributions

1. **Causal failure analysis.** An auditable trajectory representation and
   Observation--Constraint--Operation taxonomy for comparing deployment approaches by
   the earliest cause of failure.
2. **A minimal deployment algorithm.** Verifier-triggered target-state replay turns
   verified interactive sufficiency into a reproducible program and returns executable
   counterexamples without restricting a strong Agent's repair policy.
3. **Controlled empirical evaluation.** Same-model causal comparisons, external
   baselines, strong and weaker backbones, Official success, failure transitions, and
   success-preserving resource outcomes.

## 5. Experimental Design

### 5.1 Failure Study

We annotate scientifically valid trajectories from EnvBench agents, Repo2Run, native
coding Agents, prior hard-constraint EnvSolve, and EnvSolve-Pro. Infrastructure failures
are censored. Each failed episode receives one evidence-linked primary layer and
secondary mechanism tags. A stratified sample is independently re-annotated and
agreement is reported. Consumed trajectories support taxonomy discovery, not comparative
success claims.

### 5.2 Same-Model Causal Test

Both arms use one continuous free Agent session, the same scheduled full-goal observation,
and repeatedly callable clean replay. The treatment adds one executable transition: after
the first trusted complete Pass, the next model action must programize and replay. Before
that trigger, tools and initial prompts are exactly equal. Model, base image, repository
access, construction environment, Official evaluator, and broad safety limits are matched.
Cases are selected without treatment outcomes and fixed before repositories are opened.

The primary metric is Official Pass@1. Mechanism outcomes include first-replay failure,
feedback-conditioned program change, repair success, and replay/Official agreement.
Resource outcomes include requests, tokens, wall time, network traffic, storage, and
time to the first replay-certified program. They are reported unconditionally and
conditional on success.

### 5.3 System and Model Comparisons

System-level comparisons include EnvBench baselines, Repo2Run, frozen prior EnvSolve,
and native Codex as an independent capability frontier. Strong and weaker backbones test
whether executable counterexamples complement model capability or are absorbed by model
progress. Development data selects the fixed mechanism and protocol; held-out data
estimates performance. No model parameter is trained in this paper.

Repo2Run is itself a stateful loop rather than a one-shot baseline: it preserves a model
dialogue and construction container, invokes tests repeatedly, rolls back some failed
state-changing commands, and serializes successful command history. The specific boundary
tested here is narrower. Repo2Run terminates on success in the accumulated construction
state; it does not execute the complete serialized deliverable from an independent target
initial state and return that counterexample to the still-active reasoning session.

Official success and deployment completeness are distinct. EnvBench's import-oriented
goal is reported as defined, while compatibility shims, unavailable hardware runtimes,
and broader behavioral coverage are audited separately.

## 6. Current Evidence

Trajectory instrumentation first exposed an Observation failure in the evaluator loop:
replay inherited the construction cache, allowing two replay-certified programs to fail
Official. Isolating the target state restored replay/Official agreement and produced
same-session repairs, establishing faithful executable feedback rather than a package rule.

Across two outcome-independent development batches, free search passed `6/8` and
target-state replay passed `7/8` (exact McNemar `p=1.0`). A failure-enriched Bad-6 then
produced `2/6` versus `4/6` and three replay Fail-to-Pass repairs, but also revealed a
repeated Operation failure: the Agent could reach the public goal without delivering a
candidate. These studies motivate the handoff but do not establish a general success gain.

A prospective six-pair attempt to solve candidate non-delivery with prompt-guided early
programization and incumbent retention regressed from `6/6` to `5/6` and consumed more
resources on common successes. The failed trajectory reached a trusted complete Pass but
never proposed a program, so retention could not activate. We reject that bundled method
and isolate one missing transition: verified state sufficiency must cause a replay attempt.

On the already consumed qibolab case, the resulting verifier handoff completed the full
mechanism chain. Control and treatment both passed Official. Treatment reached a trusted
Pass, was handed off once, failed clean replay on a dependency conflict, repaired it in
the same session, and passed the next replay and Official. It used 66 versus 84 requests
and 2.59M versus 5.49M tokens, but these are descriptive values from one consumed pair.
Runner 0.6.1 also removes a pre-trigger prompt difference discovered in this qualification;
the prospective comparison will begin with identical tools and prompts across arms.

## 7. Falsification and Scope

The core claim is weakened if outcome-independent same-model experiments show no
Official gain, if replay failures do not change subsequent programs, if replay and
Official diverge under matched target state, or if gains disappear for strong models.
A success gain accompanied by prohibitive resource growth is reported as a tradeoff, not
an efficiency improvement.

The first paper studies a fixed deployment algorithm. Harness self-optimization belongs
to Auto-EnvSolve; policy learning belongs to EnvSolve-RL. Their future use of these
trajectories does not enter the present method or claims.
