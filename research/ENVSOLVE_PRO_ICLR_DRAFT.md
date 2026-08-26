# EnvSolve-Pro: Partially Observable Stateful Constraint Solving for Repository Deployment

Status: working ICLR paper draft, 2026-08-26; prospective atomic-replay and held-out results pending

## Abstract

Deploying an unfamiliar repository is not merely command generation. The Agent sees only
the compatibility facts exposed by its current actions, those actions change the
environment, and a successful interactive workspace may not be reproducible from a
clean checkout. We formulate repository deployment as **partially observable stateful
constraint solving**.

We instrument end-to-end deployment trajectories and classify the earliest decisive
failure into three causal layers: Observation, Constraint, and Operation. The analysis
reveals two recurring gaps: Agents optimize repository-level proxy signals instead of the
scored public goal, and a working construction state does not imply a program that
reconstructs it. EnvSolve-Pro therefore keeps a capable Agent free in one continuous
session, exposes the complete public goal, and makes submission an atomic execution of the
complete deployment program from the target initial state. Failed submissions return an
executable counterexample to the same session as case-local evidence. The method adds no
package-rule library, checkpoint search,
cross-case memory, scheduled repair policy, or hard action rule.

Consumed-development trajectories support the causal taxonomy and show same-session
Fail-to-Pass repairs, but do not establish generalization. The final evaluation separates
free search, public-goal visibility, and target-state replay under the same model, then
compares EnvSolve-Pro with EnvBench baselines, Repo2Run, prior EnvSolve, and native coding
Agents on held-out cases. Official Pass@1 is primary; resource use is evaluated only after
success is preserved.

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
condition, is ordered incorrectly, or is absent from the delivered program. Harness
rejections follow the same causal rule: an incorrect admissibility requirement is a
Constraint failure, while violating a correct requirement is an Operation failure.

The layers form a causal loop: observations induce constraints; constraints guide
operations; operations create the next state and therefore the next observation.

## 3. EnvSolve-Pro

EnvSolve-Pro combines free feedback search, trusted goal observation, and target-state
counterexample replay.

### Observation Layer

The Agent receives ordinary construction feedback and an executable description of the
complete public goal. It may measure that goal while constructing the environment. Replay
evidence is tied to the repository revision, base image, and fresh execution, and observes
the complete program rather than a selected command or accumulated construction state.

### Constraint Layer

A failed replay yields a case-local soft constraint: the observed state contradicts the
current complete program. Raw evidence remains visible, and the same Agent may revise or
reject its interpretation. The harness does not retrieve cross-case rules or choose a
package.

### Operation Layer

The Agent freely inspects the repository and changes the construction environment. When
it submits a complete program, the harness atomically executes that program and the goal
from the target initial state. A failed submission returns evidence to the same session,
without prescribing the next action. There is no unchecked submission action and no
separate optional replay action. A candidate is returned only after that exact program
passes from the target state.

```text
start one continuous Agent session in a construction environment

while no replay-passing program exists and broad safety limits remain:
    Agent freely observes and changes the construction environment
    use repository feedback and the executable public goal
    if the Agent calls submit(P):
        y <- execute P and the public goal from the target initial state
    else:
        continue
    if y passes:
        return P
    return the first executable counterexample in y to the same session

return failure
```

The algorithm stores programs and execution evidence, not container checkpoints. It does
not decide when to submit, how to repair the environment, or which action follows a failed
submission. The repair loop remains inside the active reasoning session and operates on
the complete deliverable from its actual initial state. Stronger models therefore enlarge
the Operation layer instead of being restricted by it. Scheduled verifier-triggered
handoff is rejected and is not part of the method.

## 4. Contributions

1. **Causal failure analysis.** An auditable trajectory representation and
   Observation--Constraint--Operation taxonomy for comparing deployment approaches by
   the earliest cause of failure.
2. **A minimal deployment algorithm.** Same-session target-state replay tests the complete
   deliverable and returns executable counterexamples without prescribing a strong
   Agent's repair policy. Public-goal residuals are case-local soft constraints; the Agent
   remains the operation policy.
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

### 5.2 Same-Model Mechanism Decomposition

The main causal experiment separates three interfaces under the same model and execution
conditions: free search with repository feedback (`F`), free search plus an executable
public goal (`F+O`), and the same goal-aware session plus target-state replay
(`F+O+R`). The first contrast tests the dominant Observation hypothesis; the second tests
whether complete-program counterexamples add value after the goal is already visible.
All replay residuals are advisory, and all environment-changing operations remain model
decisions. The historical `deepseek-free-agent` control already received the public goal,
so earlier `A-F` versus replay results estimate only the second contrast and are relabeled
`F+O` versus `F+O+R` in analysis.

The consumed mechanism study exposed replay as a callable action and revealed that a
strong Agent can ignore it even after reaching a construction-only Pass. The prospective
algorithm therefore merges submission and replay into the atomic interface in Section 3;
it does not schedule submission or select the subsequent repair.

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

### 6.1 Failure Taxonomy

An attempt-level reconstruction contains 48 method--case rows and 38 non-success rows.
A provisional single-reviewer annotation assigns 25 algorithmically attributable failures
to Observation (14), Constraint (7), or Operation (4); nine infrastructure-unknown and four
protocol-censored rows are excluded. These consumed-development counts are not prevalence
or effectiveness estimates. They show why terminal errors are insufficient: the same
Official residual can arise because one system never observes a necessary fact while
another observes it but selects an ineffective operation.

A label-blinded evidence packet covers all 38 non-success rows. Agreement remains
unreported until independent review is complete; provisional counts are not reliability
evidence.

### 6.2 Same-Model Mechanism Evidence

After infrastructure censoring and clean replacement execution, three consumed cases
remain paired for each contrast. Public-goal observation changes one `F` failure to an
`F+O` Pass; two pairs remain failures. Replay preserves one shared Pass, changes one
`F+O` failure to an `F+O+R` Pass, and leaves one hard case failed. The replay-only gain is
Sphinx-Gallery: a clean replay exposed Git's fresh-checkout ownership requirement, the
same session added the missing operation, and the next replay and Official evaluator
passed. On the one common-success pair, replay costs 24 additional model requests,
1.36M tokens, and 1,904 seconds. These results identify a mechanism and tradeoff; they do
not estimate held-out success.

Geoapps is the neither-Pass hard case. Correct interpreter observation removed hundreds
of apparent import residuals, but the full Official goal also counted obsolete repository
imports and imports intentionally missing in tests. Goal-aware Agents then tried to
shrink the measurement scope or create source/type shims, while the optional replay action
was never activated. All three arms exhausted the broad request cap without submission.
This case motivates atomic submit-and-replay and a separate integrity axis; it does not
support a claim that activated replay was ineffective.

### 6.3 Simplicity by Falsification

More controlling treatments were not retained. Prompt-guided early programization plus
incumbent retention regressed from `6/6` to `5/6`; a prospective forced-handoff pilot
regressed from `3/3` to `2/3`, with no treatment-only Official Pass. This evidence argues
against making the harness choose the strong Agent's next operation. The retained method
adds only public-goal observation and atomic complete-program target-state replay. The
next prospective fixed batch tests this interface before held-out evaluation.

## 7. Falsification and Scope

The core claim is weakened if outcome-independent
same-model experiments show no Official gain, if replay failures do not change subsequent
programs, if replay and Official diverge under matched target state, or if gains disappear
for strong models.
A success gain accompanied by prohibitive resource growth is reported as a tradeoff, not
an efficiency improvement.

The first paper studies a fixed deployment algorithm. Harness self-optimization belongs
to Auto-EnvSolve; policy learning belongs to EnvSolve-RL. Their future use of these
trajectories does not enter the present method or claims.
