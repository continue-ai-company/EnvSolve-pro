# EnvSolve-Pro Operation Frontier V5

Date: 2026-08-30

## Question

Can a strong Agent deploy more reliably when it sees the verified effect of each
environment-changing operation, without restricting its command choices or turning its
construction history into the final deployment program?

## Why V4 Is Not The Core Method

Minimal B gives one Agent a continuous session, a persistent shell, and clean replay of
any complete program it proposes. V4 additionally accumulates construction commands as
an editable program. On the first three Hard6 pairs, both methods passed all cases, but
V4 used more aggregate tokens, about twice the wall time, and 13 clean replays versus
three for B.

The failure was not a lack of edit machinery. V4 treated a shell exit as evidence that
the intended state change occurred and treated construction coordinates as a portable
deployment plan. PyRollbar and LangGraph eventually passed because the Agent repaired
these mistakes, but only after long diagnostic loops.

## V5 In Plain Language

After the Agent says, "this command is meant to change the environment," the harness
immediately runs the complete public goal and reports how many obligations became fixed,
newly broke, or remain. To keep repeated observations within the model context, it
exposes at most 128 obligation identities per section and an explicit truncation flag.
Complete evidence remains in the machine trajectory, and the Agent can inspect the raw
goal when it needs more detail. The Agent stays in the same session and chooses the next
action freely.

The harness never converts that command into the deployment program. When the active
environment works, the Agent writes one self-contained program and replays it in a clean
environment. A replay failure returns to the same session for repair.

## Three Layers

**Observation:** command output and a truthful bounded projection of the complete
public-goal post-state after each declared change.

**Constraint:** a compatibility frontier containing only executable current obligations
and their resolved or introduced delta. It is evidence, not a package rule.

**Operation:** an open Bash action selected by the Agent, followed eventually by an
Agent-synthesized, path-portable full program.

## What V5 Does Not Add

V5 has no package rules, command filters, automatic rollback, checkpoints, cross-case
memory, controller classifier, or hard semantic veto. It does not add another candidate
session or another whole-program search loop.

## First Qualification

The first paired comparison uses three already-consumed cases: Conan, PyRollbar, and
LangGraph. They cover a V4 efficiency win, a severe V4 replay-amplification loss, and a
mixed result. Each pair compares fresh Minimal B and V5 runs under the same case, model,
provider, seed, host lane, goal, evaluator, and broad safety limits.

Official Pass is primary. If success ties, we inspect whether operation-linked deltas
actually change diagnosis or recovery, then report requests, tokens, wall time, shell
effects, observations, projection truncation, and clean replays. These consumed cases
qualify the mechanism; they do not estimate generalization.
