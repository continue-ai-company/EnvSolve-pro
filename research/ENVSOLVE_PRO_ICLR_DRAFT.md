# EnvSolve-Pro: Stateful Constraint Solving for Repository Deployment

Status: working ICLR paper draft, 2026-08-24; the prospective development pilot rejects
verifier-triggered handoff as the primary success-rate mechanism

## Abstract

Deploying an unfamiliar repository is not merely command generation. The Agent sees only
the compatibility facts exposed by its current actions, those actions change the
environment, and a successful interactive workspace may not be reproducible from a
clean checkout. We formulate repository deployment as **partially observable stateful
constraint solving**.

We first instrument end-to-end deployment trajectories and classify the earliest
decisive failure into three causal layers: Observation, Constraint, and Operation. The
analysis reveals a recurring gap between constructing a working state and delivering a
program that reconstructs that state. EnvSolve-Pro keeps a capable Agent free in one
continuous session, measures the complete public goal, and replays the complete deployment
program from the target initial state. Replay counterexamples return to the same session
as case-local evidence. The method adds no package-rule library, checkpoint search,
cross-case memory, or hard repair policy.

A preregistered three-case development pilot tested whether forcing programization after
a trusted construction Pass improves success. It did not: control achieved `3/3` Official
Passes versus `2/3`, and `2/3` versus `1/3` under a separate protocol-compliance audit.
There was no treatment-only Pass. We therefore reject forced handoff as the primary
success mechanism and retain it only as an efficiency treatment to be tested after
success is preserved. Official Pass@1 remains primary; time, tokens, traffic, storage,
deployment completeness, and protocol compliance remain separate outcomes.

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

The Agent freely inspects the repository and changes the construction environment. It may
express the current solution as a complete program and invoke clean replay repeatedly. A
replay failure returns evidence to the same session, without prescribing the next action.
A candidate is returned only after that exact program passes from the target state.

```text
start one continuous Agent session in a construction environment

while no replay-passing program exists and broad safety limits remain:
    Agent freely observes and changes the construction environment
    periodically measure the complete public goal
    if the Agent proposes a complete deployment program:
        obtain the complete deployment program P
    else:
        continue
    y <- execute P and the public goal from the target initial state
    if y passes:
        return P
    return the first executable counterexample in y to the same session

return failure
```

The algorithm stores programs and execution evidence, not container checkpoints. It does
not decide how to repair the environment or force a model action after a construction
Pass. The repair loop remains inside the active reasoning session and operates on the
complete deliverable from its actual initial state. Stronger models therefore enlarge the
Operation layer instead of being restricted by it. Verifier-triggered handoff is retained
only as a rejected success-rate treatment and a possible success-conditional efficiency
ablation.

## 4. Contributions

1. **Causal failure analysis.** An auditable trajectory representation and
   Observation--Constraint--Operation taxonomy for comparing deployment approaches by
   the earliest cause of failure.
2. **A minimal deployment algorithm.** Same-session target-state replay tests the complete
   deliverable and returns executable counterexamples without prescribing a strong
   Agent's repair policy; the evidence-to-program constraint update is the remaining
   algorithmic object under development.
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

### 5.2 Same-Model Handoff Test

Both arms use one continuous free Agent session, the same scheduled full-goal observation,
and repeatedly callable clean replay. The tested treatment added one executable transition:
after the first trusted complete Pass, the next model action had to programize and replay.
Before that trigger, tools and initial prompts were exactly equal. Model, base image,
repository access, construction environment, Official evaluator, and broad safety limits
were matched. Cases were selected without treatment outcomes and fixed before repositories
were opened. Section 6 reports the negative result; this treatment is not the proposed core
algorithm.

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
the prospective comparison therefore began with identical tools and prompts across arms.

That fixed comparison covered all three mechanically selected failures from a 20-case
development screen. Control passed `3/3` and handoff `2/3` on Official Pass@1; the one
discordant pair favored control. Both Marimo arms obtained Official Pass by creating
manual placeholder modules, so a preregistered allowed-action audit counts both as
algorithm failures; protocol-compliant success is `2/3` versus `1/3`. There was no
treatment-only Pass on either axis. PlatformIO provides one success-conditional efficiency
signal: handoff reduced 35 requests and 1.03M tokens to 16 requests and 0.23M tokens.
This does not rescue the success-rate hypothesis.

The pilot exposes two earlier, repeated causes. Trusted goal observations changed when
the Agent's persistent working directory changed, even with the same interpreter and
installed distributions. Clean replay also exposed required provider operations whose
postconditions were not preserved in the delivered program. The next minimal method
revision therefore targets project-root-invariant observation and evidence-to-program
postconditions. Forced handoff is no longer part of the core claim.

## 7. Falsification and Scope

The forced-handoff success claim is rejected by the prospective development pilot and is
not carried forward. The remaining core claim is weakened if outcome-independent
same-model experiments show no Official gain, if replay failures do not change subsequent
programs, if replay and Official diverge under matched target state, or if gains disappear
for strong models.
A success gain accompanied by prohibitive resource growth is reported as a tradeoff, not
an efficiency improvement.

The first paper studies a fixed deployment algorithm. Harness self-optimization belongs
to Auto-EnvSolve; policy learning belongs to EnvSolve-RL. Their future use of these
trajectories does not enter the present method or claims.
