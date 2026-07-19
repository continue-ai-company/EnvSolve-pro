# P6 Constraint Operation Qualification V8 Results

Status: closed after pair 1 under the preregistered runtime-invariant rule.

## Validity

Q8 selected five outcome-blind development identities. Position 1 was interrupted
at operator request before verification and is retained as scientifically
ineligible/Unknown without retry. Position 2, the frozen full counterpart, is
artifact-valid and scientifically eligible. It had a complete heartbeat, a clean
committed source, matching schedule identity, and no primitive-budget violation,
host suspension, request error, or online official-evaluator access.

The first pair is censored because its ablation is ineligible. The primary runtime
mechanism nevertheless triggered in the eligible full run and violated a frozen
invariant, so Q8 closed after that pair. Positions 3--10 were not run; all five
selected identities remain permanently development-consumed. Q8 provides no paired
effectiveness estimate or official Pass@1 result.

## Observed Result

| Pair | Ablation | Full | Runtime trigger | Primary verdict | Official result |
|---|---|---|---|---|---|
| `biopsykit` | interrupted / ineligible | candidate limit / eligible | yes | invariant failure | censored / Unknown |

The full run used five model requests, 37,815 tokens, five proposed candidates,
three executed commands, three fresh environments, and 410.5 seconds. It never
called the official evaluator. All three candidate environments used the exact
image digest observed by the read-only base-runtime probe, so the image-identity
invariant passed.

The probe observed Python 3.13.2. Candidate 1 then produced an unambiguous package-
manager diagnostic stating that the current Python version was not allowed by the
project's declared range. Four later proposal opportunities existed, satisfying
the preregistered mechanism-trigger rule. The model itself selected Python 3.10 in
the next candidate, showing that free-form reasoning could react to the text.

Typed state did not. The run admitted zero repository runtime requirements,
recorded no post-initialization constraint update, created no hard runtime conflict,
and produced no `runtime_configure` obligation. The mismatch-to-conflict invariant
therefore failed before candidate 2 executed. The later compatible-runtime attempt
cannot repair that violation retrospectively.

## Shared Mechanism Defect

The decisive defect is a narrow action-result admission grammar. A deterministic
diagnostic of the generic form `Current Python version (...) is not allowed by the
project (...)` remained ordinary execution evidence instead of becoming a typed
runtime requirement/fact contradiction. Consequently, the model may temporarily
choose a compatible interpreter while the solver cannot require or preserve that
repair across fresh candidates.

The repository also used Poetry-specific runtime metadata, which the conservative
pre-action declaration observer did not admit, and two final proposals repeated a
candidate-policy rejection around a lock command. These are recorded secondary
coverage observations. Neither is needed to establish the primary failure, and Q8
will not accumulate post-hoc fixes for them.

Under the frozen adaptation policy, Q8 is closed. No Q8 case will be rerun, the
remaining selected cases will not return to the untouched pool, and no Q8 outcome
supports a paper-level effectiveness claim.

## Next Revision

The next mechanism revision should remain minimal:

1. Define a package-manager-independent runtime-mismatch diagnostic schema.
2. Parse a version and allowed range only when both are explicit; retain near-miss
   diagnostics as provisional evidence.
3. Add synthetic positive and adversarial-negative tests before changing the live
   parser.
4. Reuse the existing hard-conflict, operation-planning, preservation, and guard
   path without adding repository, package, or version rules.

Poetry declaration admission and candidate-policy command coverage remain separate
ablation candidates. They should be added only if broader error counts show they
are independent bottlenecks. The repaired mechanism must be frozen and qualified
on newly selected untouched Q9 cases.
