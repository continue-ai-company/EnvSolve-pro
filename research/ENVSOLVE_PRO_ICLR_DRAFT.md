# EnvSolve-Pro: Partially Observable Stateful Constraint Solving for Repository Deployment

Status: working ICLR paper draft, 2026-08-11

## Abstract

Deploying an unfamiliar repository is not merely command generation. An Agent observes
execution in a changing environment, infers unsatisfied compatibility conditions, and
must deliver a program that reconstructs a working state from a clean checkout. Success
in the construction environment does not imply that the program is replayable, while a
post-hoc evaluator reveals this gap only after the Agent can no longer repair it. We
therefore formulate repository deployment as **partially observable stateful constraint
solving**.

We first build auditable deployment trajectories and analyze failures through an
Observation--Constraint--Operation causal framework. Initial evidence indicates that the
dominant problem is not a shortage of package rules: critical facts appear only during
clean replay, execution evidence fails to condition the next repair, and categorical
hard constraints reject valid solutions from strong Agents. We introduce EnvSolve-Pro.
A continuous Agent session freely operates a persistent construction environment, may
submit a complete deployment program to independent clean environments, and receives
soft counterexample constraints that preserve the underlying evidence. Every compared
system runs under the same evaluation-integrity foundation; this foundation validates
the experiment but is not part of the deployment algorithm.

We evaluate Official Pass@1 through same-model paired experiments and external baselines,
then test failure-distribution shifts and success-first resource efficiency. The method
and a Dev-12 paired study are preregistered. Its first three pairs show two auditable
feedback-conditioned repairs but equal 2/3 Official Pass@1, so they establish mechanism
activation rather than an effectiveness claim.

## 1. Problem

Given a repository, exact revision, and base image, an Agent reaches an interactive
construction state \(C\) and returns a deployment program \(P\). The delivered state is
not \(C\), but

\[
E_P = R(P,E_0),
\]

where \(R\) executes \(P\) from a clean initial state \(E_0\). Deployment succeeds when
the public goal \(G\) holds and the program respects an evaluation-integrity boundary
\(I\):

\[
G(E_P)=1 \land I(P,E_P)=1.
\]

### Partial observability

The full compatibility state is not available upfront. Dependency resolution, build
isolation, ABI, hardware, networking, shell state, and checkout ownership become visible
only after particular operations. More importantly, the persistent construction state
and clean deployed state differ: failed commands can have partial effects, interaction
can leave ambient state, and the final program can omit a necessary operation. Execution
is how the Agent obtains further observations about this gap.

Budget is an experimental condition, not part of the problem definition. Under matched
safety deadlines, systems should prioritize successful deployment; time, tokens, network,
disk, and memory are measured outcomes.

## 2. Three-Layer Failure Framework

We label the earliest decisive causal failure, rather than the final error string.

### 2.1 Observation: What happened?

Observations include command results, environment identity, candidate execution, the
public goal, and integrity checks. Failures occur when a necessary fact is never observed,
a clean environment exposes a different fact, or partial and infrastructural evidence is
mistaken for a definitive state.

### 2.2 Constraint: What must hold?

Constraints are compatibility obligations inferred from evidence, including runtime,
version, build dependency, system library, ABI, platform, and state-propagation
requirements. Failures arise from missing or conflicting constraints, or from confusing a
narrow benchmark objective with complete deployment semantics.

### 2.3 Operation: How should the environment change?

Operations are environment transformations chosen to discharge active constraints.
Failures include ineffective actions, wrong ordering, construction success that the final
program cannot reconstruct, and harness rules that reject valid solutions. Cross-layer
closure failures are tracked separately: evidence does not become a constraint, a
constraint does not condition the next action, or a repair is not revalidated where it
must hold.

## 3. Method

We separate deployment mechanisms from experimental validity. Four composable mechanism
families describe how a deployer solves compatibility problems:

- **F, free feedback search:** an Agent freely chooses operations from ordinary execution
  feedback;
- **C_h, hard-constraint deployment:** encoded compatibility rules require, reject, or
  rewrite operations or candidate programs;
- **C_s, soft-constraint deployment:** execution evidence is summarized as an actionable
  obligation while raw evidence remains visible and the action space stays open;
- **R, clean replay and recovery:** a complete program runs in a fresh checkout and base
  environment, and failure returns to the same active session.

All systems share **E**, an evaluation-integrity foundation that isolates the Official
evaluator, protects repository and goal identity, binds exact submitted scripts, and
records content-addressed artifacts. E neither infers compatibility nor selects actions,
so it is not an algorithmic treatment. Continuous-session access is also matched across
controlled arms.

EnvSolve-Pro is the minimal composition **F+C_s+R**:

```text
P0 <- Agent constructs a complete deployment program
for t = 0, 1, ...:
    Et <- execute Pt in an independent clean environment
    Vt <- run the public goal under shared E
    if Vt passes:
        certify hash(Pt), and return the same program
    ct <- derive a soft constraint with bounded raw evidence
    Pt+1 <- the same Agent session freely repairs the complete program
```

The method contains no package-rule library, candidate graph, cross-case memory, learned
policy, physical checkpoint, or harness self-modification. A program derives paths from
the repository root in its starting working directory. Only the exact replay-certified
script hash can be returned. The Official evaluator remains post-episode and never enters
the loop.

## 4. Contributions

1. **Causal failure study.** We introduce cross-system trajectory instrumentation and an
   Observation--Constraint--Operation taxonomy that explains where deployment paradigms
   fail instead of reporting aggregate success alone.
2. **EnvSolve-Pro.** We propose a minimal verifier-guided repair algorithm combining open
   Agent search, soft counterexample constraints, and same-session clean replay without
   categorical rules that suppress model capability.
3. **Controlled evidence.** We test Official Pass@1, causal error transitions,
   same-model gains, and success-first resource Pareto efficiency against matched systems
   and an independent frontier reference, while reporting leaderboard success and
   deployment completeness as separate axes.

## 5. Experiments

### 5.1 Research questions

- **RQ1:** How do deployment paradigms distribute failures across the three layers?
- **RQ2:** With model and evaluator access matched, does F+C_s+R outperform F, and is any
  gain caused by repair after replay failure?
- **RQ3:** How does EnvSolve-Pro compare with Repo2Run, the EnvBench Agent, and
  hard-constraint EnvSolve on DeepSeek V4 Pro, and where does native Codex place the
  independent frontier reference?
- **RQ4:** At equal or higher success, does EnvSolve-Pro improve time, token, network,
  disk, or memory efficiency?

### 5.2 Data protocol

We partition the 329 EnvBench Python cases into repository-disjoint Dev-209, Canary-20,
and protected-test-100 sets. Historical consumed trajectories support taxonomy discovery
only. A deterministic 20% sample stratified by system and primary failure category is
independently re-annotated, with raw agreement, Cohen's kappa, and adjudication reported.
The current Dev-12 is selected by a frozen salted hash from 56 Dev cases remaining
after identity-only exclusion of prior terminal evidence; repository content, outcome,
and failure class are not read. We open Canary only after freezing the algorithm and use
the protected and complete official protocols last.

### 5.3 Comparisons

The current Dev-12 pair shares E, `deepseek/deepseek-v4-pro`, a fixed Cloudflare
endpoint, image, architecture, public goal, safety deadline, continuous-session access,
and Official evaluator:

- **A: F**, a free Agent without in-session clean replay;
- **B: F+C_s+R**, EnvSolve-Pro.

Dev-12 remains unchanged under its original preregistration and serves as a mechanism
pilot. After it completes, a fresh Dev-16 is selected outcome-independently from the
frozen reserve. It compares F, F+R, F+C_s+R, and frozen prior EnvSolve as the
representative F+C_h+R system, for 64 episodes. F+R versus F isolates replay; F+C_s+R
versus F+R isolates soft normalization. EnvSolve-Pro versus prior EnvSolve is only a
system-level soft-versus-hard comparison because the implementations differ beyond the
constraint mechanism. External comparisons also include EnvBench FreeAgent, Repo2Run,
and native Codex; their native semantics are retained.

### 5.4 Metrics

The primary metric is Official Pass@1. Mechanism metrics include first-replay failure,
feedback-conditioned repair, terminal class, and paired error-category transitions.
Resource metrics include wall time, tokens, tool calls, replay count and duration, plus
directly measurable network, disk, and peak memory. Infrastructure incidents are censored
separately and do not overwrite algorithmic failures.

## 6. Current Evidence and Falsification

The current retrospective strong-Agent census contains 50 terminal episodes: 28 Official
Passes, 11 Official Failures, five pre-Official hard-boundary failures, and six
infrastructure-censored outcomes. Repeated mechanisms include clean-checkout ownership
drift and categorical rules rejecting local configuration, third-party layout repair, or
compatibility artifacts; three rejected programs later pass non-scoring Official
counterfactuals. Conversely, advisory replay agrees with Official in only 22 of 38
comparable episodes. Replay therefore needs high fidelity and must remain soft evidence,
not become another hard gate.

This motivates the method but does not establish its effect. Eight Dev-12 pairs have run;
six are pairwise Official-observable, and both arms are 5/6 on those pairs. EnvSolve-Pro
produced three auditable feedback-conditioned repairs and three first-replay
certifications. The clearest stopping trace used nearly identical dependency strategies:
EnvSolve-Pro submitted at request 15 after replay, whereas F repeated an already satisfied
goal until request 43. Yet a preceding repair cost EnvSolve-Pro about 61% more tokens and
generation time, and it twice failed to form a replay candidate. The evidence therefore
supports repair and stopping mechanisms, not a pass-rate or unconditional efficiency
advantage. The remaining Dev-12 and fresh Dev-16 must test reproducibility; otherwise we
will narrow the claim rather than add rules.

## 7. Limitations

EnvBench Official primarily measures missing imports and cannot alone establish a complete
runtime deployment. We report Official success and deployment completeness separately,
without replacing the leaderboard metric. EnvSolve-Pro does not learn cross-case
experience or search its own harness design; those capabilities are outside this paper.
