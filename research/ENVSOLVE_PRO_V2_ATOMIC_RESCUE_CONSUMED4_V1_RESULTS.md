# EnvSolve-Pro V2 Atomic Rescue: Consumed-4 Results

## Question

Can atomic submit-and-clean-replay rescue four pre-existing `F+O` Official failures without
adding package rules or constraining the Agent's search operations?

This is an outcome-conditioned development diagnostic, not a held-out effect estimate.
All four historical controls failed Official before the atomic outcomes existed.

## Result

Atomic delivery rescued `1/4` cases. Hark passed after a replay counterexample and
same-session repair. Quacc formed and repaired a candidate but exhausted the session
before a certified resubmission. Ajenti and Micropy never formed a candidate.

| Case | First full-goal Pass | First submit | Replay | Official | Dominant stage |
| --- | ---: | ---: | --- | --- | --- |
| Quacc | request 65 | request 106 | Fail, Fail | Fail | late delivery, then target-state/network recovery |
| Ajenti | none; best residual 82 | none | none | Fail | pre-candidate namespace search |
| Hark | request 16 | request 27 | Fail, Pass | Pass | omitted fresh-checkout Git operation |
| Micropy | none; best residual 19 | none | none | Fail | pre-candidate compatibility search |

The four episodes used 397 model requests, 15.54M tokens, 40 provider errors, and
21,199 seconds in aggregate. These are outcomes, not hard success limits.

## Mechanism Evidence

Hark is a clean causal rescue. Its construction state passed the public goal, but fresh
replay failed because Git rejected the checkout as dubious ownership. The same session
added `safe.directory`; the next replay and Official evaluation passed.

Quacc exposes the next bottleneck. The full goal first passed at request 65, but the Agent
did not submit until request 106. Replay then found a real build-isolation defect in
`torch-scatter`. The Agent repaired it with `--no-build-isolation`; a second replay failed
instead on a PyPI read timeout. Network retry work consumed the remaining requests before
a third submission. The network failure is reported separately from the semantic defect.

Ajenti and Micropy show the boundary of atomic replay. Neither rollout reached the full
goal or submitted, so replay feedback could not activate. Their failures cannot be used
to claim that activated replay was ineffective.

## Decision

Retain atomic delivery as a support primitive, but do not promote the current voluntary
atomic method as the paper algorithm from this diagnostic. The next consumed mechanism
test couples scheduled trusted goal observation to immediate use of the same atomic
submission action. It asks whether earlier target-state feedback preserves enough of the
active session for repair. Search remains unrestricted, and no case-specific rule is
added.

Machine-readable result:
`experiments/validations/envsolve_pro_v2_atomic_rescue_consumed4_v1_result.json`.

