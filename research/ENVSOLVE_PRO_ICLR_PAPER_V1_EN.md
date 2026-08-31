# EnvSolve-Pro: Repository Deployment as Partially Observable Stateful Constraint Solving

## Abstract

Reproducing a software repository requires more than generating a plausible installation script. A deployment agent must infer an unobserved compatibility state from incomplete execution feedback, reconcile interacting requirements over language runtimes, packages, native libraries, source layouts, and generated artifacts, and finally convert a successful construction process into a program that works from a clean initial state. Even strong coding agents often fail at one of these transitions despite long interaction histories.

We formulate repository deployment as **partially observable stateful constraint solving** and organize its reasoning loop into three interfaces: Observation, Constraint, and Operation. Observation turns execution into grounded state evidence. Constraint maintains the still-active requirements and conflicts implied by that evidence. Operation lets an agent freely change the environment, while clean target-state replay converts replay failures into new evidence for the same active session. This separation preserves the flexibility of a strong agent without asking it to repeatedly reconstruct the deployment state from raw transcripts.

We evaluate EnvSolve-Pro on EnvBench using Official Pass@1 as the primary endpoint. Our study combines trajectory-based causal failure analysis, same-backbone controlled comparisons, native Repo2Run and coding-agent baselines, and protected evaluation. The final result statement and the exact constraint-update treatment are intentionally reserved for the post-selection paper version.

## 1. Introduction

Repository deployment is a compact test of whether an AI system can make reliable progress in the physical world of software. The agent receives a repository at a fixed revision and must construct an environment in which the repository's required tooling can execute. It may need to select an interpreter, recover historical package versions, compile native extensions, expose generated code, initialize submodules, or reconcile platform-specific dependencies. The environment changes after every action, but no command reveals the complete state.

This task exposes a limitation of command-level trial and error. A long transcript records what the agent typed and what the shell returned, but it does not by itself answer three questions:

1. Which facts about the current environment have actually been established?
2. Which requirements remain active, conflict, or have been refuted?
3. Which action should change the state, and can the resulting state be reproduced from scratch?

More capable models reduce local reasoning errors, yet they do not remove this structure. A strong agent can recognize an import error and propose a package, but later operations may change the interpreter, invalidate an earlier package choice, or produce a working construction state that is absent from the final script. Conversely, a rigid rule system may preserve consistency while blocking a legal solution that a stronger model could discover. The central problem is therefore not whether to replace reasoning with rules. It is how to expose grounded state and constraint information while leaving the operation policy expressive.

We study this problem through an Observation--Constraint--Operation (OCO) loop. The three layers are reasoning interfaces rather than software modules. Execution produces observations tied to a particular environment state. Those observations update a case-local constraint state. The agent chooses an operation using both the constraint state and relevant raw evidence. When it proposes a deployment program, the program is executed from the target initial state; any replay counterexample returns to the same active session and updates the next round of reasoning.

The paper makes three contributions:

1. **Problem and analysis.** We formalize repository deployment as partially observable stateful constraint solving and introduce an evidence-grounded OCO failure analysis that identifies the earliest decisive reasoning transition.
2. **Method.** We introduce a minimal closed-loop deployment method that combines a continuous agent session, case-local constraint state, unrestricted environment operations, and target-state replay. The final paper will name only the constraint-update mechanism that improves terminal success under controlled evaluation.
3. **Empirical study.** We design same-model causal comparisons and native-system comparisons against EnvBench agents, Repo2Run, Codex, and a prior hard-constraint EnvSolve system. Official Pass@1 is primary; time, tokens, memory, storage, and deployment quality are secondary outcomes.

## 2. Problem Formulation

### 2.1 Deployment Task

A task instance is

\[
x = (r, c, e_0, V),
\]

where \(r\) is a repository, \(c\) is an exact revision, \(e_0\) is the target initial environment, and \(V\) is an executable success criterion. The agent interacts with a mutable construction environment and returns a deployment program \(P\).

The task succeeds only if executing \(P\) from a fresh copy of \((r@c, e_0)\) produces a terminal state \(s^*\) accepted by the evaluator:

\[
s^* = \operatorname{Replay}(P, r@c, e_0), \qquad V(s^*) = 1.
\]

A construction state that passes locally is insufficient if the program cannot recreate it. Likewise, an attractive intermediate error reduction is not success.

### 2.2 Partial Observability

Let \(s_t\) denote the true environment state after step \(t\). It includes the active interpreter and shell, installed distributions, system libraries, filesystem artifacts, source roots, generated files, environment variables, and resolver state. The agent never observes \(s_t\) directly. It receives an observation

\[
o_t \sim \mathcal{O}(s_t, q_t),
\]

where \(q_t\) is a probe such as a shell command, package-manager query, import attempt, build, or public verifier execution. Each probe reveals only part of the state and may itself change that state. Missing output does not imply a missing condition, and old evidence may no longer describe the active environment.

This partial observability is intrinsic to real deployment. Dependency declarations can be incomplete; package names need not match import names; a distribution can install successfully while lacking the required symbol; and a generated provider can exist only after a build step. Platform and network behavior add further hidden variables.

### 2.3 Stateful Constraints

EnvSolve-Pro represents its current belief as a set of evidence-backed constraints

\[
C_t = \{c_t^1, \ldots, c_t^m\}.
\]

A constraint states a condition that must hold for the target deployment, together with its status and evidence. Examples include the presence of a module in the active interpreter, compatibility between a runtime and a binary package, availability of a generated source tree, or reproducibility of a shell state in the final program.

The update rule

\[
C_t = U(C_{t-1}, o_t)
\]

may activate, satisfy, refute, or mark a constraint uncertain. It must preserve enough provenance to distinguish a current fact from a historical observation. The constraint state is advice to the agent, not a replacement for raw evidence and not a hard restriction on the action space.

### 2.4 Actions and Terminal Programs

At each step the agent selects an operation

\[
a_t \sim \pi(h_t, C_t, o_t), \qquad s_{t+1} = T(s_t, a_t),
\]

where \(h_t\) is the continuous session history. Operations may inspect or change any deployment-relevant state. EnvSolve-Pro does not assume a fixed package manager or a closed action vocabulary.

The output is not the construction container. It is the replayable program \(P\). A replay failure is therefore a first-class observation about the gap between construction and delivery, rather than a post-hoc formatting error.

### 2.5 Success and Budget

The primary outcome is terminal Official Pass@1. A run that reaches an intermediate goal but fails to return a replayable program is a failure. Resource quantities such as model requests, tokens, wall-clock time, peak memory, network traffic, and storage are experimental conditions and secondary metrics. They are not part of the task definition, and they are optimized only after success is preserved.

## 3. EnvSolve-Pro

### 3.1 Overview

EnvSolve-Pro keeps one agent session and one mutable construction environment active throughout an episode. Its loop is:

\[
\text{execute} \rightarrow \text{observe} \rightarrow \text{update constraints}
\rightarrow \text{select operation} \rightarrow \text{replay candidate}.
\]

The loop separates evidence, belief, and action. This matters because the same shell output can support different constraints, and the same constraint can admit several legal operations.

### 3.2 Observation: What Is Known?

The Observation interface converts execution feedback into state evidence. An observation contains:

- the operation or probe that produced it;
- the relevant environment identity;
- the exit status and bounded raw output;
- structured findings when an executable verifier is available;
- uncertainty when execution is incomplete or infrastructure is unstable.

Observations are append-only evidence. They do not become permanent truths merely because they appeared earlier in the trajectory. A later interpreter switch or source-tree change can supersede their state interpretation while preserving the original record for analysis.

### 3.3 Constraint: What Must Still Hold?

The Constraint interface maps evidence to the current deployment obligations. It answers four compact questions:

1. Which conditions remain unsatisfied?
2. Which earlier conditions are now satisfied or invalid?
3. Which requirements conflict under the active runtime and platform?
4. Which claims remain uncertain and need another probe?

Constraints are case-local and evidence-backed. They may summarize many repeated diagnostics, but the agent can inspect the associated raw evidence and overturn an incorrect interpretation. This design aims to reduce transcript reconstruction without narrowing the legal solution space of a strong model.

### 3.4 Operation: How Is the State Changed?

The Operation interface remains open. The agent may invoke arbitrary non-interactive deployment commands, including package installation, environment creation, source builds, metadata inspection, and generated-code production. The constraint state informs action selection but does not choose a package or block an operation by itself.

This separation distinguishes EnvSolve-Pro from hard-constraint deployment systems. Safety and evaluator isolation are shared experimental infrastructure. They are not presented as the deployment policy.

### 3.5 Continuous Session and Counterexample Replay

The same active session receives construction feedback and replay counterexamples. This preserves local reasoning continuity: the agent knows why it chose an interpreter, what a failed installation changed, and which residual requirement motivated the current branch.

When the agent forms a complete deployment program \(P\), EnvSolve-Pro executes it in a clean target environment. If replay fails, the failure becomes a new observation \(o_{t+1}^{R}\), and the corresponding construction-to-delivery mismatch enters \(C_{t+1}\). The agent then repairs the program within the same session. If replay succeeds, the exact replayed program is submitted for Official evaluation.

### 3.6 Minimal Algorithm

```text
Input: repository r@c, target environment e0, public verifier V
Initialize active agent history h0, construction state s0, constraints C0 = empty

repeat
    obtain grounded execution evidence ot from the active environment
    Ct <- update(Ct-1, ot), retaining evidence provenance
    at <- agent(h_t, Ct, relevant raw evidence)
    execute at in the active construction environment

    if a complete deployment program P is proposed then
        y <- replay P from a fresh (r@c, e0)
        if y passes V then
            return the exact replayed P
        else
            feed y to the same session as a replay counterexample
until the episode terminates
```

The final constraint-update instantiation is selected only by terminal success under the controlled design study. Intermediate frontier improvement, cleaner diagnostics, or more structured trajectories are not sufficient for inclusion.

### 3.7 Relation to Baselines

Free ReAct exposes raw execution history but does not maintain an explicit current constraint state or require target-state replay. Repo2Run combines feedback search with checkpointing and rollback, emphasizing recovery of construction progress. Native coding agents provide a strong general policy and continuous interaction, but do not by themselves define benchmark-controlled state constraints and replay semantics. The prior EnvSolve system encodes hard constraints that can reject or rewrite behavior. EnvSolve-Pro instead keeps constraints soft, preserves a free operation policy, and closes the loop with executable replay evidence.

## 4. Experimental Setup

### 4.1 Benchmark and Splits

We use the Python portion of EnvBench. The reconstructed benchmark contains 329 repository revisions, with 229 in the official training side and 100 in the Official Test side. Development trajectories are used for taxonomy discovery and mechanism selection. A protected 20-case canary and the 100-case Official Test are not used to design the final method. Exposure is tracked by repository identity so that consumed development cases cannot support unseen-repository claims.

### 4.2 Compared Systems

We compare EnvSolve-Pro with the EnvBench FreeAgent baseline, Repo2Run, a native Codex deployment agent, the prior hard-constraint EnvSolve system, and a same-backbone free agent. Same-backbone comparisons isolate the causal effect of the OCO loop. Native-system comparisons measure end-to-end capability without pretending that different model stacks are a controlled ablation.

### 4.3 Metrics

The primary metric is paired Official Pass@1. Generation noncompletion and failure to produce a replayable program count as failures. Secondary metrics are model requests, prompt and completion tokens, wall-clock time, peak memory, network and storage use, clean-replay attempts, and deployment-quality annotations. Cost is reported through stable resource units rather than a hard dollar threshold.

### 4.4 Statistical Design

Mechanism hypotheses are developed only from consumed trajectories. A treatment is first tested against a matched control with the same case, model, seed, image, goal, and evaluator. Promotion requires terminal success evidence; intermediate error reduction is mechanism evidence only. The selected method is then evaluated on protected identities without further case-specific changes.

## 5. Main Results

The final paper version will report protected Official Pass@1 after method selection.

| System | Backbone | Official Pass@1 | Requests | Tokens | Wall time |
|---|---|---:|---:|---:|---:|
| EnvBench FreeAgent | native | [TBD] | [TBD] | [TBD] | [TBD] |
| Repo2Run | native | [TBD] | [TBD] | [TBD] | [TBD] |
| Codex | native | [TBD] | [TBD] | [TBD] | [TBD] |
| Same-backbone free agent | fixed | [TBD] | [TBD] | [TBD] | [TBD] |
| EnvSolve | fixed | [TBD] | [TBD] | [TBD] | [TBD] |
| EnvSolve-Pro | fixed | [TBD] | [TBD] | [TBD] | [TBD] |

## 6. Analysis

### 6.1 OCO Failure Transitions

We assign each non-successful trajectory one earliest decisive layer when evidence supports a counterfactual attribution: Observation when a required fact was unavailable or not obtained; Constraint when the fact was observed but not retained or reconciled; and Operation when the relevant requirement was active but the chosen state transition or delivered program failed. Infrastructure incidents are reported separately.

### 6.2 Design-Study Conclusions

The design study uses terminal outcomes to distinguish algorithmic progress from better diagnostics. Three questions organize the analysis: whether evidence reaches the active session, whether it changes the current constraint judgment, and whether that change produces a replayable Official success. Variants that improve only the first two steps are retained as measurement tools rather than promoted to the core method.

### 6.3 Model Capability

We test whether explicit state constraints remain useful as the underlying model becomes stronger. The relevant hypothesis is not that stronger models cannot infer constraints. It is that executable, state-bound evidence reduces stale-state reasoning and construction-to-delivery loss even when local reasoning is strong. Strong and weaker backbones are therefore evaluated separately under the same method definition.

## 7. Related Work

EnvSolve-Pro connects work on software engineering agents, automated environment construction, dependency solving, and interactive planning under partial observability. Unlike systems that treat deployment as one-shot script generation, it studies the evolving environment as part of the reasoning state. Unlike classical dependency solvers, it must infer constraints from repository evidence and arbitrary execution. Unlike unrestricted coding-agent interaction, it makes target-state reproducibility an explicit part of the feedback loop.

## 8. Limitations and Conclusion

EnvBench emphasizes executable import availability and does not fully measure semantic runtime correctness, test coverage, or production deployment quality. Static-import success can also admit environments with different completeness and resource profiles. We therefore report Official success separately from deployment-quality annotations. Results on the published container platforms do not establish portability to every operating system or accelerator.

Repository deployment is not well described as free-form command generation. It is a partially observable stateful constraint-solving problem whose evidence, beliefs, and actions evolve together. EnvSolve-Pro turns this view into a minimal closed loop: grounded observation, evidence-backed constraints, free environment operations, and clean replay counterexamples returned to the same agent session. The protected evaluation will determine whether this loop improves terminal success across both strong and weaker agents.
