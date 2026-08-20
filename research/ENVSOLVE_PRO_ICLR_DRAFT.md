# EnvSolve-Pro: Target-State Counterexample Replay for Repository Deployment

Status: working ICLR paper draft, 2026-08-20; method selected, independent
qualification pending

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
algorithm that keeps a capable Agent free in one continuous session but executes each
complete candidate program from the target initial state. The first executable
counterexample is returned to the same session as a soft constraint; the Agent revises
the whole program and repeats. The method adds no package-rule library, checkpoint
search, cross-case memory, or hard action policy.

A preregistered mechanism check on three previously consumed failures produced
replay/Official agreement in all three cases and feedback-conditioned repair in two.
In the hardest case, cold replay successively exposed an invalid wheel version, missing
repository ownership setup, and omitted test dependencies that construction-cache-backed
replay had hidden. These results establish mechanism operation, not effectiveness.
The confirmatory study will compare same-model free search and EnvSolve-Pro on an
outcome-independent batch, then evaluate external baselines and strong and weaker model
backbones. Official Pass@1 is primary; time, tokens, traffic, storage, and deployment
completeness are separate outcomes.

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

EnvSolve-Pro combines free feedback search with target-state counterexample replay.

### Observation Layer

The Agent receives ordinary construction feedback and raw replay evidence tied to the
repository revision, base image, and fresh execution. Replay observes the complete
program rather than a selected command or the accumulated construction state.

### Constraint Layer

A failed replay yields a case-local soft constraint: the observed state contradicts the
current complete program. Raw evidence remains visible, and the same Agent may revise or
reject its interpretation. The harness does not retrieve cross-case rules or choose a
package.

### Operation Layer

The Agent freely inspects the repository, changes the construction environment, and
rewrites the complete program. A candidate is returned only after that exact program
passes replay from the target state.

```text
start one continuous Agent session in a construction environment

while no replay-passing program exists and broad safety limits remain:
    Agent freely observes and changes the construction environment
    Agent proposes a complete deployment program P
    y <- execute P and the public goal from the target initial state
    if y passes:
        return P
    return the first executable counterexample in y to the same session

return failure
```

The algorithm stores programs and execution evidence, not container checkpoints. Its
central choice is where the repair loop runs: inside the active reasoning session,
against the complete deliverable, from the state that the deliverable will actually
face. The harness supplies a target-state counterexample oracle, not a repair policy;
stronger models enlarge the Operation layer instead of being constrained by it.

## 4. Contributions

1. **Causal failure analysis.** An auditable trajectory representation and
   Observation--Constraint--Operation taxonomy for comparing deployment approaches by
   the earliest cause of failure.
2. **A minimal deployment algorithm.** Target-state counterexample replay turns
   non-reproducible interactive success into an iterative, same-session constraint
   solving loop without restricting a strong Agent's action space.
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

The control is one continuous free Agent session with ordinary execution feedback. The
treatment adds only repeatedly callable target-state replay whose failure returns to the
same session. Model, prompt content, base image, repository access, construction
environment, Official evaluator, and broad safety limits are matched. Cases are selected
without treatment outcomes and fixed before repositories are opened.

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

The initial six-case consumed profile found that free search passed 5/6 while the old
replay arm passed 4/6. Two replay-certified programs failed Official because replay had
inherited the construction package cache. This rejected the old implementation and
localized the failure to Observation fidelity rather than missing package rules.

After replay cache isolation, a preregistered three-case mechanism check achieved 3/3
replay/Official agreement. Basxconnect repaired a missing Git ownership operation after
one failed replay. Graphium repaired three successive program defects across cold
replays and then passed Official; cvxportfolio passed its first replay and Official.
Two of three cases therefore exercised feedback-conditioned repair.

This is selected consumed evidence. It establishes that the mechanism can activate and
that replay now matches the target cache state. It does not establish an expected
success-rate or efficiency gain. Graphium required 82 requests, 2.32M tokens, about one
hour of generation, and a 1.2 GiB construction cache, showing that successful repair can
still follow an expensive path.

## 7. Falsification and Scope

The core claim is weakened if outcome-independent same-model experiments show no
Official gain, if replay failures do not change subsequent programs, if replay and
Official diverge under matched target state, or if gains disappear for strong models.
A success gain accompanied by prohibitive resource growth is reported as a tradeoff, not
an efficiency improvement.

The first paper studies a fixed deployment algorithm. Harness self-optimization belongs
to Auto-EnvSolve; policy learning belongs to EnvSolve-RL. Their future use of these
trajectories does not enter the present method or claims.
