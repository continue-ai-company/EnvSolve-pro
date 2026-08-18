# EnvSolve-Pro: Partially Observable Stateful Constraint Solving for Repository Deployment

Status: working ICLR paper draft, 2026-08-18

## Abstract

Repository deployment is usually treated as command generation: an Agent reads a
repository, executes commands, and returns an installation script. This view misses the
central difficulty. The compatibility state is only partially visible, actions change
that state, and success in an interactive workspace may not survive execution from a
clean checkout. We formulate repository deployment as **partially observable stateful
constraint solving**.

We first instrument deployment trajectories and organize failures into three causal
layers: Observation, Constraint, and Operation. The resulting evidence suggests that a
major bottleneck is not insufficient package knowledge, but delayed or incomplete
observations of the state in which the submitted program must work. We then introduce
EnvSolve-Pro, a minimal algorithm that keeps a free Agent in one continuous session,
performs complete identity-bound observations on a fixed schedule, tracks how
compatibility obligations change, and certifies complete programs by clean replay. The
harness supplies evidence but does not choose packages, block operations, or restore
checkpoints.

We evaluate the method with same-model paired experiments, external deployment
baselines, and an independent strong-Agent frontier. Official Pass@1 is primary;
mechanism activation, failure-layer transitions, and success-conditional resource use
explain where gains come from. A preregistered optional-observation pilot improved from
2/4 to 3/4 passes but failed mechanism qualification because one treatment episode
never used the observation tool. This negative result motivates the deterministic
observation schedule evaluated by the current study.

## 1. Problem

Given repository revision \(x\), base environment \(E_0\), and public goal \(G\), an
Agent interacts with a construction environment and returns a deployment program \(P\).
The delivered environment is

\[
E_P = R(P, E_0),
\]

where \(R\) executes the complete program from a clean state. Deployment succeeds when

\[
G(E_P)=1 \land I(x,P,E_P)=1,
\]

where \(I\) is a shared evaluation-integrity predicate covering repository identity,
goal identity, and artifact provenance.

### 1.1 Why the state is partially observable

The Agent cannot inspect the full compatibility state in advance. Dependency solving,
build isolation, Python identity, native libraries, ABI, hardware, networking, and
process-local state become visible only after particular operations. Moreover, the
interactive construction environment and the clean replay environment are different
states: failed commands may leave partial effects, shell configuration may be ambient,
and the final script may omit an operation that happened interactively. Execution is
therefore both an action and a source of information.

### 1.2 Budgets are evaluation conditions

Time and request caps make experiments comparable and safe, but they are not part of the
problem definition. Success has priority. Tokens, wall time, network traffic, disk, and
memory are measured outcomes under matched limits, not hard optimization targets.

## 2. Three-Layer Failure Framework

We classify the earliest decisive cause rather than the terminal error string.

### 2.1 Observation: What happened?

An Observation failure occurs when a necessary fact is absent, attached to the wrong
environment identity, measured too late, or interpreted as complete when it is partial.
Examples include testing a different Python executable from the submitted program and
discovering a clean-environment conflict only after the interactive session ends.

### 2.2 Constraint: What must hold?

A Constraint failure occurs when evidence is not converted into the right compatibility
obligation, when obligations conflict without being recognized, or when a resolved
obligation is treated as still active. Constraints may concern runtime versions, package
ranges, build dependencies, system libraries, ABI, platform, or state propagation.

### 2.3 Operation: How should the state change?

An Operation failure occurs when the chosen transformation cannot discharge the active
obligation, is ordered incorrectly, or cannot be reconstructed by the submitted program.
Harness rules can also create Operation failures by suppressing a valid action from a
capable Agent.

The framework is causal across layers: an operation cannot repair a constraint that was
never inferred, and a constraint cannot be inferred from a fact that was never observed.

## 3. EnvSolve-Pro

### 3.1 Shared evaluation foundation

Every controlled arm shares foundation \(E\): isolated Official evaluation, immutable
repository and goal identity, exact submitted-program hashing, and auditable artifacts.
This foundation makes evidence trustworthy but does not infer compatibility or select
actions, so it is not an algorithmic treatment.

### 3.2 Scheduled observation

EnvSolve-Pro runs a complete public-goal observation:

1. before the first model request;
2. after every \(K=16\) completed shell operations;
3. immediately before clean replay if the environment changed after the latest
   observation.

Each observation records the executable identity, environment paths, relevant installed
distributions, complete findings, and bounded raw evidence. The cadence was fixed once
from a historical consumed-trajectory interval and is not tuned on new outcomes.

### 3.3 Stateful constraint frontier

For consecutive complete finding sets \(Q_{t-1}\) and \(Q_t\), the harness reports

\[
\text{resolved}_t = Q_{t-1} \setminus Q_t, \qquad
\text{introduced}_t = Q_t \setminus Q_{t-1}.
\]

Observations and deltas are appended to an evidence frontier in the active session.
Evidence provenance is monotonic, but the inferred compatibility state may improve,
regress, or change direction. The frontier is guidance, not a policy: it neither installs
packages nor restricts the Agent's action space.

### 3.4 Free operation and clean replay

The same Agent session freely chooses shell operations and edits a complete deployment
program. A candidate is certified only by executing that exact program in an independent
clean environment. Replay failure, together with its identity-bound observation, returns
to the active session for repair. The Official evaluator is invoked only after the
episode and never enters the repair loop.

```text
Q <- observe(clean construction state)
give Q to one continuous Agent session

while no replay-certified program and safety limit remains:
    let the Agent freely inspect, operate, and edit P
    after every K shell operations:
        Q' <- observe(current construction state)
        return delta(Q, Q') and raw evidence to the same session
        Q <- Q'
    when the Agent requests replay:
        observe first if the construction state is dirty
        result <- execute exact P from a clean state
        return replay evidence to the same session

return only the exact replay-certified program hash
```

The method has no package-rule library, physical checkpoint, cross-case memory, learned
policy, or harness self-modification.

## 4. Contributions

1. **Failure taxonomy and instrumentation.** We provide auditable cross-system
   trajectories and an Observation-Constraint-Operation taxonomy for identifying the
   earliest decisive cause of deployment failure.
2. **A minimal deployment algorithm.** We introduce EnvSolve-Pro, which combines
   deterministic identity-bound observation, a stateful evidence frontier, free
   same-session operation, and clean replay without encoding package choices or blocking
   capable Agents.
3. **Controlled empirical evidence.** We measure same-model causal gains, strong- and
   weaker-model performance, Official success, failure-distribution shifts, and resource
   Pareto behavior against free-search, hard-constraint, replay-based, Repo2Run,
   EnvBench, and native coding-Agent references.

## 5. Experimental Design

### 5.1 Failure study

Scientifically valid consumed trajectories from EnvBench FreeAgent, Repo2Run, native
Codex, prior hard-constraint EnvSolve, and EnvSolve-Pro enter retrospective taxonomy
discovery. Infrastructure failures are censored. Each failed episode receives one
evidence-linked primary label for its earliest decisive layer. A deterministic 20%
sample stratified by system and category is independently re-annotated; raw agreement,
Cohen's kappa, and adjudicated labels are reported. This corpus supports taxonomy and
failure-profile claims, not comparative success rates.

### 5.2 Mechanism qualification

The current qualification compares a same-backbone free-search plus clean-replay control
with EnvSolve-Pro on four previously consumed repositories, two repetitions, and
counterbalanced order, for 16 episodes. Every treatment episode must follow the frozen
observation schedule; at least 75% of scheduled observations must be complete; the
harness must impose zero operation constraints and create zero checkpoints.

Promotion requires no lower Official Pass count, at most one paired treatment-only loss,
and either one treatment-only win or a preregistered success-conditional efficiency
signal. This small experiment qualifies the mechanism; it is not the final effect-size
estimate.

### 5.3 Confirmation and baselines

No frozen Dev identity is opened until mechanism qualification. Algorithm, prompt, tool
schema, taxonomy, model/provider binding, and analysis code are then frozen before
Canary and protected evaluation. Controlled comparisons retain the same model and
foundation. System-level baselines include EnvBench FreeAgent, Repo2Run, frozen prior
EnvSolve, and native Codex as an independent frontier reference. Strong and weaker
backbones test whether the harness complements rather than replaces model capability.

The primary metric is Official Pass@1. Secondary mechanism metrics are schedule
compliance, obligation-set transitions, candidate-ready-to-replay latency, replay repair,
and paired failure-layer transitions. Resource metrics are reported both unconditionally
and conditional on success. Official success and broader deployment completeness remain
separate evaluation axes.

## 6. Current Evidence and Falsification

Across 14 consumed strong-Agent trajectories, 898 shell operations contained 50 natural
global compatibility checks, an average interval of 17.96 operations. The resulting 36
comparable state transitions were stagnant or regressing in 36.1% of cases. This suggests
that strong Agents do inspect global state, but irregularly and sometimes after long
periods of locally plausible work.

A preregistered eight-episode pilot tested an optional compatibility-ledger tool. All
eight effective episodes passed validity checks. The treatment passed Official in 3/4
episodes versus 2/4 for the replay control, with one treatment-only win and no loss. In
that win, complete findings moved from 16 obligations to zero before a replay conflict
was repaired. Its paired control found the correct environment late and exhausted 120
requests without replay.

The pilot nevertheless received the machine decision
`negative-mechanism-not-qualified`: one successful treatment episode never called the
tool. On comparable successful pairs, the treatment used median ratios of 1.30 requests,
1.28 interactive steps, 1.46 tokens, and 1.11 time to certificate relative to control.
The result supports the value of complete identity-bound observation in at least one bad
case, but rejects voluntary tool use as a stable mechanism.

EnvSolve-Pro is falsified or narrowed if deterministic scheduling still fails to produce
stable complete observations, lowers Official success, creates treatment-only losses, or
shows no reproducible repair or efficiency signal. We will report such outcomes rather
than add case-specific rules.

## 7. Scope and Limitations

EnvBench Official emphasizes missing-import compatibility and does not establish full
application behavior. Our integrity foundation can reject invalid measurement artifacts,
but it is not evidence that the deployment algorithm works. The first paper studies a
fixed harness and contains no cross-case learning, automatic harness search, or Agent RL.
