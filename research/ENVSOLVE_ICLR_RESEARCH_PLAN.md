# EnvSolve-Pro: Stateful Constraint Solving for Repository Deployment under Partial Observability

> Living ICLR paper draft. Engineering history and per-run ledgers remain in the detailed research plan, outside the paper.

## Abstract

Deploying an unfamiliar repository is not dependency-file transcription. It requires recovering hidden runtime,
dependency, build, and platform conditions from incomplete evidence. An Agent observes only local execution symptoms, and
a solution that works in its construction environment may fail in a fresh checkout of the target image. Repository
deployment is therefore better viewed as **stateful constraint solving under partial observability** than as one-shot script
generation or unbounded command trial and error.

We first build a trajectory observation system and classify the earliest decisive causal failure at three layers:
**Observation, Constraint, and Operation**. This taxonomy is orthogonal to deployment method families. Free feedback
search, hard constraints, soft constraints, and clean replay can be combined, but induce different failure distributions.

We then propose **EnvSolve-Pro**. A continuous Agent session freely constructs a complete bootstrap. The Observation layer
replays that program from the target initial state; the Constraint layer returns executable counterexamples as case-local
soft constraints to the same session; and the Operation layer revises the complete program before another replay. The core
algorithm has no package rule library, cross-case memory, physical checkpoints, candidate graph, or harness self-modification.

Development evidence shows that this mechanism repairs complete-program defects hidden during ordinary construction. On
six preregistered strong-baseline failure cases, a free Agent passed `2/6` and EnvSolve-Pro passed `4/6`; exact McNemar is
`p=0.5`, which does not support significance, generalization, or SOTA claims. The traces reveal a second bottleneck: Agents
often satisfy the Official objective but fail to deliver while pursuing broader deployment completeness. Confirmatory
evaluation remains pending after algorithm fixation.

## 1. Introduction

Project reproduction, testing, program analysis, migration, and security auditing all require an executable environment,
yet real repositories rarely provide a complete and reliable environment specification. A missing import may indicate a
missing distribution, an incompatible language version, an unsatisfied platform branch, an incorrect project installation,
or a static analyzer observing the wrong environment. Similar logs can have different causes, while one cause can produce
different logs.

The problem has three structural difficulties:

1. **Hidden conditions.** Validity is jointly determined by source, metadata, build systems, platforms, and external package
   indexes; it cannot be read once from the repository.
2. **Partial observations.** One execution supports or refutes only part of a candidate explanation, and network failures
   may make an outcome unidentifiable.
3. **State transition.** Incremental success in a contaminated construction environment does not imply that the same state
   can be rebuilt from the target initial environment.

Frontier coding Agents are already capable repository readers and experimenters, but model strength does not remove these
structures. An Agent can validate in the wrong state, forget an early prerequisite, continue optimizing an already viable
candidate, or discover a fresh-state defect only in the terminal evaluator. Our aim is not to replace a strong Agent with
rules. It is to give the Agent a loop that exposes target-state counterexamples, preserves reasoning continuity, and returns
a replayable deployment program.

We make three contributions:

1. **Trajectory system and failure taxonomy.** We capture deployment commands, environment identity, complete candidates,
   clean replays, and terminal outcomes, and introduce an Observation--Constraint--Operation causal taxonomy that is
   orthogonal to method families.
2. **The EnvSolve-Pro algorithm.** We introduce a minimal three-layer method: target-state observation, session-local soft
   counterexamples, and complete-program repair with replay. It preserves the Agent's action space and uses no cross-case
   hand-written compatibility rules.
3. **A controlled empirical study.** On EnvBench, we compare a same-backbone free Agent, the earlier hard-constraint
   EnvSolve system, Repo2Run, the EnvBench Agent, and native Codex, reporting Official Pass@1, failure-distribution shifts,
   candidate reach, replay repair, and success-first resource outcomes.

EnvBench is a testbed rather than the definition of EnvSolve-Pro. Evaluator isolation, repository auditing, and common
result collection are shared experimental infrastructure, not algorithmic contributions.

## 2. Problem Formulation

Given repository revision `R` and target initial environment `E0`, let hidden compatibility state `Z_R` contain language
runtimes, package versions, ABI constraints, system libraries, build tools, platform predicates, and environment variables.
A deployment program `P` must construct from `E0` an environment satisfying public goal `G`.

An internal verifier produces:

`O_t = V(R, P_t, E0; Z_R, xi_t)`,

where `xi_t` denotes interference such as network and package-index state. In general, `O_t` does not uniquely identify
`Z_R`: a successful bootstrap supports only one path, while a failure may be consistent with several causes.

EnvSolve-Pro state consists of the current complete program, counterexamples accumulated in one active Agent session, and
their replay records. Stateful does not require a large typed rule system. It requires that resetting the target environment
does not erase established failures or program revisions.

An unseen Official evaluator `Q` scores the final program only after the episode. In EnvBench Python, Official Pass requires
bootstrap exit code zero and zero `reportMissingImports` findings. Online solving cannot consume feedback from `Q`.

Resource limits are experimental settings, not the task definition. Deployment success is primary. Tokens, time, commands,
and storage are measured outcomes, and efficiency is claimed only when success is preserved.

## 3. Failure Taxonomy

### 3.1 Two Orthogonal Axes

We separate **deployment method family** from **failure layer**.

Method families describe how a deployer acts:

- **F, free feedback search:** an Agent freely chooses operations from ordinary execution feedback;
- **C_h, hard constraints:** encoded rules force, reject, or rewrite candidate behavior;
- **C_s, soft constraints:** executable evidence conditions current reasoning without forbidding actions;
- **R, clean replay:** a complete candidate runs from the target initial state and returns a counterexample to the solver.

Failure layers locate the earliest decisive cause:

- **Observation failure:** a necessary fact was absent or observed in the wrong state, noise was hardened, or construction
  and target states exposed different facts;
- **Constraint failure:** the solver missed a required condition or conflict, misdiagnosed cause, or conflated the Official
  target with broader deployment completeness;
- **Operation failure:** actions failed to discharge constraints, ordering or shell state was wrong, the program could not
  rebuild success, or the Agent failed to form and deliver a candidate;
- **Loop failure:** evidence did not change a constraint, the constraint did not change an operation, or a repair was not
  revalidated where it had to hold.

Infrastructure incidents remain Unknown instead of being forced into algorithmic categories. Each failed episode receives
one primary causal label and optional secondary tags, based on the full trajectory rather than the last error string.

### 3.2 Positioning Existing Systems

The EnvBench FreeAgent and same-backbone Raw ReAct primarily implement F. Native Codex is strong F in a continuous session
and persistent construction environment. Repo2Run combines F with local checkpoint/rollback after modifying failures. The
earlier EnvSolve combines F, broad C_h, and historical replay. EnvSolve-Pro studies the minimal F+C_s+R combination.

These mappings explain failure distributions; they do not turn whole-system comparisons into pure component effects. The
first paper does not enumerate all mechanism combinations. Automated harness search belongs to future Auto-EnvSolve work.

## 4. EnvSolve-Pro

### 4.1 Three-Layer Loop

**Observation: what happened?**

The Agent freely reads and executes inside a continuous construction session. Once it forms a complete bootstrap, the
Observation layer executes it from scratch in a fresh checkout of the target image and runs an internal verifier equivalent
to the public goal. The record includes target identity, the program, earliest failure stage, exit state, and bounded raw logs.

**Constraint: what is missing or conflicting?**

Replay failure returns to the same active session. The Agent interprets it as a case-local soft constraint, such as “Git
must accept this checkout before editable installation” or “isolated build resolution cannot see Cython.” Counterexamples
are not promoted automatically into cross-repository rules, and guards do not narrow a strong Agent's action space. Network
or infrastructure evidence remains Unknown.

**Operation: how should the environment change?**

The Agent revises the complete bootstrap rather than patching only the current container. The new program is replayed again
from the target initial state. A passed replay delivers exactly the tested program; a failure continues observation,
constraint revision, and operation repair within the same session.

### 4.2 Algorithm

```text
Freely explore the repository in one continuous session and form P0
for t = 0, 1, ...:
    Ot <- execute and verify Pt from the target initial state
    if Ot == Pass:
        return Pt
    if Ot == Unknown:
        retain the candidate without creating a compatibility rule
    else:
        return the executable counterexample to the active session
    Pt+1 <- Agent revises the complete program using repository, history, and Ot
```

The core is intentionally minimal. It excludes package rule libraries, cross-case memory, typed persistent ledgers,
candidate graphs, physical checkpoints, hypothesis search, program minimization, and harness self-modification. Such
mechanisms require separate treatments rather than accumulation without evidence.

### 4.3 Why a Strong Agent Still Benefits

A strong Agent can remember conversation and summarize facts, but reasoning alone cannot reveal what an unexecuted program
will do in the target initial state. EnvSolve-Pro contributes an intervention rather than more natural-language experience:
it executes the complete program where it must work and returns the counterexample to the same session that still understands
the repository and repair history. Stronger models should exploit this evidence better; the method does not assume that the
model cannot reason autonomously.

## 5. Experimental Design

### 5.1 Research Questions

- **RQ1, failure structure:** how do method families distribute failures across Observation, Constraint, Operation, and loop
  categories?
- **RQ2, success:** under matched backbone, information, and Official access, does F+C_s+R outperform F?
- **RQ3, model dependence:** does EnvSolve-Pro help both weaker API models and a native frontier Agent?
- **RQ4, cost and quality:** at equal or greater success, how does replay affect time, tokens, commands, storage, and
  deployment completeness?

### 5.2 Comparisons

The same-model causal comparison uses fixed DeepSeek V4 Flash: free Agent F, F+R, EnvSolve-Pro F+C_s+R, and the frozen
earlier hard-constraint EnvSolve system. External comparisons include the EnvBench Agent and Repo2Run. Native Codex retains
its native CLI and available frontier model as an independent capability reference, not a same-model control.

All methods share repository revision, target image, public goal, and terminal Official access. Only feedback native to an
algorithm may enter its loop; Official evaluation is terminal for every method.

### 5.3 Data and Overfitting Control

Consumed retrospective trajectories are used only to discover the taxonomy and propose mechanisms. Algorithm development
uses declared development batches; once a case is inspected, it cannot support an unseen-generalization claim. After the
algorithm, prompt, model, provider, taxonomy, and analysis are fixed, evaluation proceeds to Canary, protected test, and the
full official protocol.

EnvSolve-Pro does not learn across cases in this paper. Development/test separation constrains researcher and harness
adaptation; it does not pretend that the algorithm is training parameters. EnConda-Bench is outside scope.

### 5.4 Outcomes and Statistics

The primary outcome is end-to-end EnvBench Official Pass@1. A scientifically valid episode that forms no candidate is a
deployment failure; only explicit infrastructure or experimenter incidents are censored.

Secondary outcomes include candidate formation, first-replay failure, same-session Fail-to-Pass repair, final-replay and
Official agreement, failure-category shifts, tokens, requests, commands, wall clock, and storage. Official success,
environment purity, deployment completeness, and path cost are separate axes rather than post-hoc gates.

Primary comparisons use case-paired outcomes, confidence intervals, and exact McNemar tests. Resources are success-first
outcomes rather than the deployer's central stopping objective.

## 6. Current Development Evidence

The trajectory census spans multiple systems and repeatedly exposes fresh-state drift, hard-boundary false positives,
package-index ambiguity, candidate non-delivery, and metric-passing but incomplete paths. This corpus supports taxonomy
discovery, not system success-rate estimation.

Outcome-independent target-replay development evidence covers eight pairs: free Agent passed `6/8`, while EnvSolve-Pro
passed `7/8`, with one discordant pair (`p=1.0`). These cases established executability but were mostly too easy to identify
an effect.

We therefore preregistered Bad-6 from an existing census of strong-baseline Official failures. A passed `2/6` and B passed
`4/6`: two both-pass, two B-only, zero A-only, and two both-fail pairs, with exact McNemar `p=0.5`. Four B candidates
executed seven replays, producing three Fail-to-Pass repairs; final replay and Official agreed on `4/4`.

HARK is the cleanest causal case. A encountered Git `dubious ownership` only in the Official fresh checkout. B reproduced
the same failure during internal replay, added the safe-directory operation in the same session, and passed both the second
replay and Official. This supports the narrow claim that target-state counterexamples can repair hidden complete-program
defects.

However, quacc B exhausted search before candidate formation. Both ajenti arms already reached zero missing imports but
continued pursuing runtime completeness and never delivered. B consumed 5.8% more tokens and 10.4% more endpoint time on
Bad-6. Current evidence therefore supports neither significance, population effect, efficiency, nor SOTA, and locates the
next bottleneck at successful-candidate retention and stopping.

## 7. Limitations

Current results come from small, failure-enriched development batches. Model, provider, ARM64 platform, and network state
may all influence trajectories. EnvBench's missing-import objective is not equivalent to complete executable deployment.
Soft counterexamples remain model-interpreted and can be misdiagnosed, while target replay adds execution and network cost.
Final conclusions require unseen cases, multiple model strengths, external baselines, and path-quality audits.

## 8. Conclusion

Repository deployment is difficult not because Agents need more commands, but because hidden compatibility conditions must
be inferred under partial observability and compiled into a program that rebuilds from the target initial state. EnvSolve-Pro
connects free Agent reasoning to target-state execution through a minimal three-layer loop. Development evidence demonstrates
real repairs and clearly exposes the unresolved candidate-formation problem. The next step is to test a success-first
candidate-retention mechanism without adding case-specific rules, then proceed to confirmatory evaluation after fixation.
