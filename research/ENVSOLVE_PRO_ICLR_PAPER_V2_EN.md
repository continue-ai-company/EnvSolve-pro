# EnvSolve-Pro: Turning Terminal Deployment Failures into In-Session Counterexamples

## Abstract

Repository deployment is usually treated as free-form command generation: an agent
inspects a repository, modifies an environment, and eventually emits a setup program.
This view hides the central difficulty. The compatibility state that determines success
is only partially observable, changes after every operation, and may differ between the
agent's accumulated construction environment and the evaluator's fresh target state.
Consequently, a capable agent can make substantial local progress yet deliver a program
that fails only after its session has ended.

We formulate deployment as partially observable stateful constraint solving and introduce
Observation--Constraint--Operation (OCO), a causal framework for locating the earliest
decisive failure in deployment trajectories. OCO describes reasoning; it does not require
the harness to maintain an external symbolic constraint store. We instantiate the view
with EnvSolve-Pro, a minimal intervention that executes each complete candidate program
from the target initial state while the proposing agent session is still active. An
execution failure is returned as a counterexample to that same session, and only the
exact replay-passing program is delivered.

Current development evidence establishes that target-state replay faithfully exposes
otherwise terminal failures and can induce same-session repairs. It also establishes an
important negative result: a more detailed model-external compatibility frontier improved
diagnostic resolution but did not improve Official Pass@1 in a controlled three-pair
study. These findings separate three quantities that deployment research often conflates:
diagnostic quality, the agent's ability to choose a repair, and terminal success.

## 1. Introduction

Reproducing a software repository requires more than predicting an installation command.
The deployer must discover which interpreter, package set, build tools, generated files,
environment variables, and ordering of operations jointly satisfy the target execution
condition. Many of these facts are revealed only by running commands. Each command can
also invalidate an earlier success by changing the active interpreter, replacing a
binary dependency, or moving the shell to a different state.

Strong coding agents are well suited to this open-ended search. They can inspect source,
read errors, and invent repairs that a fixed package solver cannot enumerate. Yet their
interactive success need not survive delivery. Consider an agent that reaches a working
state after installing a build prerequisite manually. Its emitted setup program omits
that earlier step, uses a different working directory, or installs into another
interpreter. The fresh evaluator then fails after the agent can no longer respond. The
problem is not merely that the agent lacked an error message; the decisive error arrived
outside the repair loop.

We argue that repository deployment is better understood as **partially observable
stateful constraint solving**. There is a real compatibility state, but the agent sees
only local observations. Conditions required for success emerge during execution and
must remain satisfied as the environment changes. The agent retains freedom over how to
satisfy them.

This formulation motivates two separate contributions. First, OCO provides a common
causal language for comparing deployment paradigms. An Observation failure means that a
decisive target-state fact never became available to the active method. A Constraint
failure means that available evidence was not correctly retained or reconciled as a
requirement. An Operation failure means that the relevant requirement was active but the
chosen state change or delivered program did not satisfy it. These labels describe why a
trajectory failed; they are distinct from whether a system uses free search, hard rules,
soft feedback, or replay.

Second, EnvSolve-Pro closes one specific feedback gap without replacing the agent's
reasoning. A complete deployment program is executed from the target initial state before
the active session ends. The resulting counterexample returns to the same session, which
may revise and resubmit the program. Passing replay and delivery refer to the same
artifact. The harness neither enumerates compatibility conditions nor chooses the next
package or command.

Our present contributions are:

1. **A problem formulation and causal failure framework.** We formalize deployment under
   hidden, evolving compatibility state and define evidence-linked OCO attribution across
   different deployment paradigms.
2. **A minimal deployment intervention.** EnvSolve-Pro converts fresh-state failure of a
   complete deliverable into an executable counterexample inside the proposing agent's
   active session, while leaving environment operations model-led.
3. **A controlled design study.** Development experiments show both the capability and
   the boundary of executable feedback: replay can trigger valid repairs, whereas finer
   residual diagnostics alone do not reliably convert into terminal success.

## 2. Problem Formulation

### 2.1 Deployment Task

A task is a tuple

\[
x = (r, e_0, V),
\]

where \(r\) is a repository at a fixed revision, \(e_0\) is the target initial
environment, and \(V\) is the executable evaluator. A deployment method produces a
self-contained program \(p\). Official success is

\[
Y(p, x) = \mathbf{1}\{V(\operatorname{Exec}(e_0, p), r) = \text{pass}\}.
\]

The primary endpoint is case-level Official Pass@1. Time, model requests, tokens,
network traffic, and storage are secondary outcomes conditioned on preserving success.
They characterize paths; they do not redefine a failed deployment as successful.

### 2.2 Hidden Stateful Compatibility

Let \(s_t\) denote the real environment state after step \(t\), including filesystem,
process, interpreter, package, build, and shell state. The agent does not observe
\(s_t\) directly. It receives a local observation

\[
o_t \sim \Omega(s_t, a_{t-1}),
\]

such as command output, an import error, package metadata, or replay failure. The agent
forms an internal judgment

\[
b_t = B(o_{1:t}, a_{1:t-1})
\]

and chooses an operation \(a_t \sim \pi(b_t, o_{1:t})\), producing
\(s_{t+1}=T(s_t,a_t)\).

For every state there is an objective set \(C^*(s_t)\) of compatibility conditions that
must hold for eventual success. This set is not assumed to be known, enumerable, or
stored by the harness. It includes conditions such as interpreter consistency, build-time
availability, binary compatibility, generated-source availability, and reproducibility
of shell effects in the delivered program. Partial observability arises because only a
small, action-dependent projection of these conditions is exposed at any step.

The task is stateful because observations have temporal scope. A successful import under
one interpreter is not evidence about another interpreter. A package visible in the
accumulated construction state need not be produced by a fresh execution of \(p\). A
later operation may also destroy an earlier compatible state.

### 2.3 OCO as a Causal Analysis Framework

OCO attributes one earliest decisive failure to a non-successful trajectory:

- **Observation:** a fact required to distinguish a successful action was unavailable,
  unobserved, or returned only after the method could no longer act.
- **Constraint:** the fact was available, but the method formed, retained, or reconciled
  the wrong requirement. A false hard-rule rejection is also a Constraint failure.
- **Operation:** the relevant requirement was active, but the chosen transformation,
  ordering, or delivered program did not satisfy it.

Later contributors may be recorded as secondary causes, but they do not replace the
earliest decisive attribution. Infrastructure failures and adapter failures are censored
rather than relabeled as algorithm failures. Each attribution must cite trajectory
evidence, not merely a terminal error string.

OCO is deliberately orthogonal to method mechanisms. A free-feedback system, a
hard-rule system, a soft-feedback system, and a replay-based system can all exhibit any
of the three failure layers. This separation lets us ask whether a method changes the
distribution of causes instead of defining a taxonomy that favors one architecture.

## 3. EnvSolve-Pro

### 3.1 Design Principle

EnvSolve-Pro addresses a narrow but consequential Observation gap: fresh-state evidence
about the exact deliverable should arrive before the reasoning session terminates. The
method keeps the agent's action space open. It adds no package-specific repair rules,
cross-case memory, external compatibility frontier, or harness policy for choosing an
operation.

### 3.2 In-Session Target-State Counterexample Replay

EnvSolve-Pro maintains one active agent session and a construction environment. The agent
may inspect the repository and change that environment using ordinary tools. When it
proposes a complete program \(p_k\), the harness creates the target initial state,
executes the exact program, and runs the public executable goal. If execution fails, the
raw grounded evidence \(z_k\) is returned to the same session:

\[
z_k = \operatorname{Replay}(e_0, r, p_k).
\]

The agent decides what the evidence means and how to change the program. A later
candidate \(p_{k+1}\) may use an entirely different strategy. If replay passes, the exact
same \(p_k\) becomes the deliverable. Official evaluation remains separate and occurs
after the episode; it is never exposed as an in-session repair signal.

```text
start one agent session and one construction environment

while no replay-passing program has been produced:
    let the agent freely inspect or change the environment
    if the agent proposes a complete deployment program p:
        z = execute p from the target initial state and run the public goal
        if z passes:
            deliver that exact p
        return z to the same active session

return failure if the agent never produces a replay-passing program
```

The intervention acts at the boundary between candidate formation and delivery. It does
not guarantee that the agent can form a candidate, infer a legal provider for every
dependency, or select an effective operation after observing a failure.

### 3.3 Relation to OCO

The Observation interface consists of ordinary execution evidence plus target-state
replay evidence. The Constraint interface is the agent's internal interpretation
\(b_t\), not a harness-maintained \(C_t\). The Operation interface remains the agent's
free choice of commands and program edits. Thus OCO explains the loop without pretending
that the current implementation contains three symbolic modules.

Replay moves a class of failures earlier in time: an omitted build prerequisite, wrong
interpreter, unreproduced shell effect, or invalid working-directory assumption can
become an in-session observation rather than a post-session Official failure. Whether
that observation becomes a successful repair is an empirical question about both the
evidence and the agent policy.

### 3.4 Distinction from Other Feedback Loops

Ordinary interactive agents receive feedback from commands in their accumulated
construction state. EnvSolve-Pro additionally binds feedback to execution of the exact
complete deliverable from the target state. In the Repo2Run profile examined in our
study, replay and rollback preserve or recover construction progress; EnvSolve-Pro's
intervention instead tests the portable program that will be delivered. The comparison
is therefore about the scope and timing of executable feedback, not whether either system
has a loop at all. Exact native-system behavior is verified from executed trajectories
rather than inferred from high-level system descriptions.

## 4. Experimental Methodology

### 4.1 Evidence Units and Splits

The failure study uses complete method--case trajectories: model messages, tool actions,
state-changing commands, submitted programs, replay results, and Official outcomes.
Consumed development cases may define taxonomy labels and screen mechanisms, but they do
not support held-out or leaderboard claims. Fixed development comparisons are selected
before treatment outcomes are observed. Protected cases are reserved for estimating the
chosen method's generalization.

### 4.2 Compared Mechanisms

We distinguish deployment mechanisms from model backbones:

- free feedback search in one active session;
- encoded hard constraints that may reject or rewrite actions;
- soft executable evidence that informs but does not restrict the agent;
- replay or recovery, with its scope reported explicitly;
- EnvSolve-Pro's complete-program target-state replay inside the active session.

Same-backbone paired comparisons isolate a mechanism. Comparisons with Repo2Run, native
coding agents, and EnvBench baselines measure end-to-end systems and therefore report
their model, tool, replay, and evaluator interfaces rather than treating them as causal
ablations.

### 4.3 Outcomes

Official Pass@1 is primary. For non-successes, OCO attribution and terminal stage explain
where the path broke. Deployment completeness is audited separately because a
metric-minimal environment and a functionally complete runtime can receive the same
Official score. Resource outcomes are reported per case and on common-success subsets;
aggregate reductions caused by one outlier are not generalized.

## 5. Development Findings

### 5.1 Failure Causes Are Not Deployment Paradigms

The current consumed-Dev census contains 16 non-success trajectories drawn from a frozen
209-case census. Thirteen have an evidence-supported earliest algorithmic cause:
6 Observation, 5 Constraint, and 2 Operation failures. Three intermittent package-index
episodes remain infrastructure-unknown and are excluded from the denominator. This is a
provisional single-reviewer development annotation, not a population prevalence estimate.

The examples reveal why terminal error categories are insufficient. Several programs
failed because target-state checkout or build-isolation facts appeared only after the
agent stopped, even though the final error looked like an installation failure. In other
cases, hard admissibility rules rejected programs that later passed Official evaluation;
these are Constraint failures of the method, not harmful operations by the agent.

### 5.2 Replay Fidelity and Repair

On three previously consumed cases selected to probe replay semantics, final
replay-certified programs passed Official evaluation. Two cases activated the intended
repair loop. Replay exposed a missing Git ownership operation in one case. In another it
sequentially exposed an unavailable dependency version, missing ownership handling, and
omitted test dependencies; the same session revised the complete program after each
counterexample. Because these cases were selected for their historical replay failures
and had no paired control, they establish mechanism behavior, not expected success.

An outcome-independent eight-pair development aggregation compared a continuous free
agent with the same interface plus target-state replay. Official results were 6/8 and
7/8 respectively, with one treatment-only pass and one common failure. Replay and
Official agreed for all seven treatment episodes that formed a final candidate, and two
episodes contained feedback-conditioned repairs. The exact paired test is not
significant; this evidence supports fidelity and causal activation, not a success-rate
claim.

### 5.3 Candidate Formation Is a Separate Bottleneck

On a fixed four-pair strong-baseline bad-case batch, both free search and EnvSolve-Pro
passed 2/4. In both common failures, the agent exhausted the request allowance without
forming a complete candidate, so replay never activated. Exact deliverable replay can
certify or repair a candidate; it cannot help when exploration never becomes a program.
This boundary motivates measuring candidate formation separately from replay quality.

### 5.4 More Detailed Residual State Did Not Improve Success

A controlled three-pair study augmented the same loop with a live model-external
compatibility frontier. The frontier was valid, used by the agent, and often reduced the
number of reported residual obligations. Nevertheless, both control and treatment passed
1/3, with no discordant Official outcome. On a common failure, the treatment exposed
precise dependency progress but still did not identify a satisfiable provider or produce
a deliverable. We therefore retain the frontier only as a diagnostic probe. Lower
residual counts are not a surrogate for terminal success.

Together, these studies identify an information-to-action gap. A method may observe a
true residual condition yet fail to infer a satisfiable requirement, choose an effective
operation, or consolidate exploration into a portable program. EnvSolve-Pro addresses
one Observation gap but does not claim to solve all three transitions.

## 6. Limitations

The current evidence is development evidence and does not establish held-out improvement,
SOTA performance, or general efficiency. Failure attribution requires independent
annotation before prevalence claims are reliable. The current method activates only
after a complete program is proposed, leaving candidate formation unresolved. Official
EnvBench success also permits deployment paths with different functional completeness,
so completeness must remain a separate axis. Finally, the exact feedback semantics of
external systems must be established through reproducible runs under matched models and
budgets.

## 7. Conclusion

Automated repository deployment is difficult because compatibility is hidden, stateful,
and revealed through interventions. OCO separates failures of observation, constraint
reasoning, and operation without prescribing a harness architecture. EnvSolve-Pro tests
a deliberately small algorithmic claim: execute the complete deliverable from the target
initial state while the proposing agent can still act, and return failure as an
executable counterexample. Development trajectories show that this intervention can make
otherwise terminal errors actionable, while controlled negative evidence shows that
better diagnostics alone are not equivalent to better deployment. Terminal success,
rather than the apparent neatness of intermediate state, remains the criterion for any
additional mechanism.
