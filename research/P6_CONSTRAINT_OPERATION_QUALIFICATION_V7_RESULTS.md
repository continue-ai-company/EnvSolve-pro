# P6 Constraint Operation Qualification V7 Results

Status: closed after pair 3 under the preregistered shared-defect rule.

## Validity

Q7 selected five outcome-blind development identities. Six runs from the first
three pairs were executed; all six are artifact-valid and scientifically eligible.
There was no host suspension, primitive-budget violation, schedule mismatch,
automatic retry, or online official-evaluator access. Pairs 4 and 5 were not run
after the shared mechanism defect was confirmed, but all five selected identities
remain permanently development-consumed.

No executed pair produced two Boolean official outcomes. The three executed pairs
are therefore censored from the paired effectiveness table, and Q7 provides no
Pass@1 estimate.

## Observed Results

| Pair | Pre-action trigger | Initial constraints | Full terminal | Ablation terminal | Full time | Ablation time |
|---|---:|---:|---|---|---:|---:|
| `everyelection` | no | 0 | candidate limit | candidate limit | 416 s | 1,737 s |
| `rl4co` | yes | 13 | candidate limit | candidate limit | 2,929 s | 3,139 s |
| `baybe` | yes | 20 | candidate limit | candidate limit | 1,683 s | 2,469 s |

The treatment mechanism was real, not merely present in code. On the two trigger
pairs, declarative evidence entered typed state before proposal 1, the initial
operation plans contained 13 and 20 package requirements, and the guard checked
candidate coverage. The ablation ran the same observer but admitted none of this
evidence.

This mechanism did not produce a successful deployment. All candidates in the two
trigger pairs failed before a complete fresh metadata report, so none of the 33
initial package requirements was closed by a positive observation. Full used the
same total candidates, commands, and environments as the ablation across executed
pairs, with fewer aggregate tokens and wall-clock time; these are descriptive
resource observations under zero official success, not evidence of effectiveness.

## Shared Mechanism Defect

Pair 3 exposed the decisive defect. Repository metadata and candidate feedback
established that the base Python 3.13 interpreter violated `requires-python <3.13`.
Full EnvSolve found a compatible pyenv runtime and then exposed a separate
protobuf/OpenTelemetry conflict. However, runtime incompatibility never became a
typed hard constraint in the operation plan. The final candidate removed pyenv and
regressed to the already-invalid base interpreter.

The same missing state dimension also allowed the ablation to repeat unavailable
apt runtime mutations. This is a general representation and feasibility problem,
not a BayBE-specific rule: package presence constraints cannot preserve runtime
compatibility or prove that a runtime acquisition action is available.

Under the preregistered adaptation policy, Q7 closed after this pair. No Q7 code or
protocol was changed, no case will be rerun, and the two unexecuted selected pairs
will not return to the untouched pool.

## Next Revision

The next mechanism revision should remain small:

1. Observe the fresh base-runtime identity before admission.
2. Admit `requires-python` only when it can be evaluated against that observation.
3. Convert deterministic runtime mismatch feedback into a typed hard constraint.
4. Require cumulative candidates to preserve a compatible runtime and reject
   repeated acquisition actions already shown infeasible.

These changes must be specified with synthetic counterexamples, frozen, and tested
on newly selected untouched Q8 cases. Q7 supports this error diagnosis only; it does
not support the paper's effectiveness claim.
