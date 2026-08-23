# EnvSolve-Pro Certified-Incumbent Development Result

Status: complete negative treatment result; development evidence only

## Question

Does prompt-guided early programization plus a clean-replay-certified incumbent improve
the existing continuous-session soft-replay method?

The original eight-pair schedule was executed unchanged. A historical-registry audit made
while the batch was running showed that Futaba had prior trajectory exposure and that
Flask-Security's revision was unavailable. The primary analysis therefore contains six
prospective pairs, Futaba is descriptive, and Flask-Security is source-acquisition
censoring. No case was replaced after outcomes were visible.

## Result

| Case | B-FSR | C-GCI |
| --- | --- | --- |
| mflowgen | Pass | Pass |
| bread | Pass | Pass |
| pajbot | Pass | Pass |
| qibolab | Pass | deployment failure |
| mamonsu | Pass | Pass |
| qiita | Pass | Pass |

B-FSR passed `6/6`; C-GCI passed `5/6`. The paired table is five both-pass, one
B-only, zero C-only, and zero neither-pass pairs. Exact two-sided McNemar is `p=1.0`;
the batch is too small for a population-effect claim, but it does falsify C-GCI as a
non-regressive improvement.

C also used more resources. Across all six pairs it used 271 versus 196 requests,
9.40M versus 3.78M tokens, and 7,547 versus 5,887 generation seconds. The qibolab
failure dominates these totals, so we also compare the five both-pass pairs: C still used
21.4% more tokens, 19.9% more generation time, and 12.1% more endpoint time. No C episode
used incumbent fallback.

## Decisive Failure

Qibolab localizes the failure across the three layers:

- **Observation:** C produced a complete full-root zero-missing-import result at request 93.
- **Constraint:** that verified sufficient state was not converted into a durable obligation
  to deliver the current program before optional exploration.
- **Operation:** the Agent continued broad dependency, hardware, stub, and runtime checks
  until request 120 without proposing a complete program.

The incumbent could not help: it exists only after a clean replay passes, and qibolab C
never called replay. The name "goal-triggered certified incumbent" therefore overstates the
implemented mechanism. Its trigger is prompt-guided belief, while its executable state
begins only after candidate submission.

## Decision

Reject bundled C-GCI as the core algorithm. Keep certified-incumbent fallback only as an
orthogonal safety primitive and keep clean target-state replay because earlier trajectories
contain real Fail-to-Pass repairs.

The next minimal hypothesis is **verifier-triggered programization**. Free search remains
unchanged. When the trusted full goal passes, the controller transitions the same active
session into producing and replaying the cumulative program before optional completeness
work. A replay failure returns the exact counterexample and reopens free repair; a replay
pass terminates successfully. This is a control-flow repair, not a package rule or a new
hard compatibility boundary.

No held-out, external-baseline, strong/weak-backbone, or SOTA claim follows from this batch.

Machine-readable result:
`experiments/validations/envsolve_pro_v2_certified_incumbent_untouched8_v1_result.json`.
