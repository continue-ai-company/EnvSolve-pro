# Postcondition-Persistent Qualification v1 Results

## Scope

This repository-disjoint development qualification tested one mechanism: whether
postcondition-gated construction-state persistence is executable, integrity-valid, and
promising enough to retain. It is not a leaderboard or final-test result.

- Cases: 5 EnvBench Python development repositories
- Conditions: persistent explicit state, fresh explicit state, persistent raw history
- Model: `deepseek/deepseek-v4-pro`
- Seed: 1
- Primary outcome: Official Pass
- Online feedback: public executable goal only; Official evaluator terminal-only

## Integrity

All 15 resolved-schedule episodes were scientifically eligible and artifact-integrity
valid. The original position 5 was manually interrupted before Official evaluation,
preserved unchanged, and excluded. Its preregistered replacement changed only the run
ID. The resolved analysis passed all schedule-identity, heartbeat, source-cleanliness,
budget-ledger, and mechanism audits.

## Main Results

| Condition | Official Pass | Candidates | Environments | Tokens | Generation wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Persistent explicit | 4/5 | 19 | 17 | 339,479 | 4,361 s |
| Fresh explicit | 4/5 | 21 | 15 | 358,742 | 3,955 s |
| Persistent raw | 4/5 | 27 | 26 | 483,988 | 9,064 s |

The primary persistent-explicit versus fresh-explicit contrast had four both-pass blocks
and one neither-pass block. The secondary persistent-explicit versus persistent-raw
contrast had the same outcome. No condition produced a treatment-only Official Pass.

## Mechanism Evidence

Persistent explicit state recorded six reused-construction verifications, four clean
replay passes, and two clean passes whose successful construction lineage included
reuse. Persistent raw history recorded four reused verifications and two
reuse-to-clean-pass lineages. The mechanism gate therefore returned
`retain-mechanism`: reuse was real, auditable, and caused no Official Pass loss.

This decision does not claim effectiveness. Persistent explicit used fewer candidates
and tokens than fresh explicit, but more wall time because clean replay adds overhead on
easy cases. It used materially fewer resources than persistent raw, especially on
TRTools, but five repositories and one stochastic seed cannot support an aggregate
efficiency claim.

## Failure Analysis

`openqasm/openqasm` was the only common failure. Every condition exhausted 12 candidates
and retained a program with seven unresolved official issues. Explicit state reduced
trajectory drift and persistent explicit used roughly half the generation time of
persistent raw, but neither crossed the success boundary.

The decisive gap was in the Operation layer:

- operations were proposed without proving tool, file, target, version, or acquisition
  preconditions;
- equivalent ANTLR-generation failures recurred without new evidence;
- some candidates optimized the diagnostic proxy by writing configuration or directly
  materializing import artifacts;
- the effect boundary rejected those integrity-invalid shortcuts.

## Decision

Retain postcondition-gated state reuse as a supporting mechanism, not as the paper's
current effectiveness claim. The next revision should add a minimal executable
operation-relevance contract: target constraint, precondition probes, expected finding
delta, observed complete-snapshot delta, and duplicate failed-family suppression.
Qualify it on synthetic and repository-disjoint evidence; do not tune on OpenQASM.

## Frozen Evidence

- Resolved schedule:
  `experiments/validations/pro_postcondition_persistent_qualification_v1_resolved_r1_schedule.json`
- Results:
  `experiments/validations/pro_postcondition_persistent_qualification_v1_results.json`
- Censored-attempt audit:
  `experiments/validations/pro_postcondition_persistent_qualification_v1_censored_position5_descriptive_audit.json`
- Gate decision: `retain-mechanism`
