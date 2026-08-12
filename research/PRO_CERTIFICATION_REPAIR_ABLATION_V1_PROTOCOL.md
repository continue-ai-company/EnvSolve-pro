# EnvSolve-Pro Certification-Repair Ablation v1

Date: 2026-08-05

## Question

The first repository-disjoint Minimal B development study produced a 5/5 versus 4/5
Official Pass@1 result, but every Minimal B episode passed its first clean replay.
That result does not show that replay feedback enabled repair. This study separates
two mechanisms that the earlier treatment combined:

1. **certification-aware construction**: the Agent knows that its final program must
   pass once in a clean environment;
2. **feedback-conditioned repair**: after a failed clean replay, the same Agent can
   revise the program and replay again.

## Frozen Arms

| Arm | Agent session | Clean replay during generation | Acceptance |
| --- | --- | --- | --- |
| A: strong Agent control | one continuous session | none | final program is evaluated post episode |
| B: one-shot certification | one continuous session | exactly one | final program must match the passing certificate |
| C: retryable Minimal B | one continuous session | repeatedly callable | final program must match a passing certificate |

All arms use the same model, reasoning effort, public goal, open terminal, persistent
construction container, generation cap, post-episode Official evaluator, repository
integrity policy, exact-revision source cache, and process-tree timeout cleanup.

Arm B receives the result of its only replay, but it cannot obtain another certificate.
Therefore B versus C identifies the value of being able to convert replay feedback
into a newly verified program. It does not isolate feedback visibility alone.

## Mechanism Outcomes

The primary outcome remains repository-paired Official Pass@1. The following outcomes
must be reported separately:

- **first-replay pass**: the first executed clean replay passes;
- **repair opportunity**: C's first replay is Fail or Unknown;
- **activated repair**: C later certifies a different program in the same Agent session;
- **repair success**: activated repair is followed by Official Pass;
- **certification-only effect**: B and A differ on Official Pass;
- **retry effect**: C and B differ on Official Pass.

Infrastructure errors are never task failures and require a frozen amendment before
an identical retry. A rejected second call in B is a treatment outcome, not an
infrastructure error.

## Decision Rules

Evidence for feedback-conditioned repair requires at least one C episode with a
Fail/Unknown first replay, a later passing replay, and Official Pass. A C-only Official
Pass without that trace pattern cannot support the repair mechanism.

If C again passes every first replay, this study provides no evidence about iterative
repair. Development should not add a structured state layer on that basis. The next
question would instead be why one-shot certification changes construction, if B and A
differ.

If repair activates but C does not outperform B, analyze whether the feedback was
non-actionable, the Agent failed to revise the relevant operation, or the clean replay
contract rejected valid solutions. Do not add case-specific rules.

## Development Screen

Select eight repositories before execution from the 53 repositories untouched after
the prior Minimal B paired study. Selection uses only a frozen salted hash of repository
identity. Repository contents, historical outcomes, package family, and expected
difficulty are not selection inputs.

The screen contains 24 episodes, with arm order rotated per repository. All episodes
must finish before an algorithm change. This is a development mechanism gate, not a
held-out or leaderboard claim. If a mechanism survives, freeze it before a larger
repository-disjoint replication and preserve the Official test split.

## Resource Reporting

Success is not stopped by token or monetary thresholds. Report model tokens, commands,
wall time, replay count, and infrastructure retries as secondary outcomes. Report
memory, disk, and network only when measured consistently across all three arms; their
absence does not change Official Pass or mechanism activation.

## Excluded Treatments

This study does not add structured state, compatibility ledgers, checkpoints,
hypothesis branching, bootstrap minimization, cross-case memory, evaluator feedback,
package heuristics, or case-specific policies.
