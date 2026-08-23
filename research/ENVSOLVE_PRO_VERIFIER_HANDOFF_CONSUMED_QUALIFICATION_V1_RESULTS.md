# Verifier Handoff Consumed Qualification V1

## Question

Can an executable trusted-goal observation move a continuous deployment Agent from a
sufficient construction state to a replayable program, without adding package rules or
restricting search?

This is a mechanism qualification on the already consumed qibolab failure. It is not an
unseen effectiveness experiment.

## Result

Both arms passed the EnvBench Official evaluator. The control first reached a complete
scheduled Pass at request 72 and shell operation 96, but continued for 11 requests and
10 shell operations before submitting a candidate. The treatment reached a complete Pass
at request 64, triggered handoff once, and was required to submit at request 65 without
another shell operation.

The first treatment replay failed on an explicit dependency conflict between
`qibo==0.2.16` and `networkx==3.0`. The counterexample returned to the same session, the
Agent removed the incompatible pin, and the second replay passed. The controller then
returned that certified program directly. This completes the preregistered mechanism
chain:

```text
trusted Pass -> controller handoff -> complete program -> clean replay Fail
             -> same-session repair -> clean replay Pass -> Official Pass
```

## Descriptive Resources

| Metric | Scheduled control | Verifier handoff | Difference |
|---|---:|---:|---:|
| Official Pass | 1 | 1 | tie |
| Model requests | 84 | 66 | -21.4% |
| Total tokens | 5,492,967 | 2,593,497 | -52.8% |
| Recorded container commands | 130 | 98 | -24.6% |
| Generation time | 2,685.8 s | 1,803.2 s | -32.9% |
| Endpoint time | 3,098.3 s | 2,149.2 s | -30.6% |
| Pass-to-certification tokens | 1,139,973 | 151,463 | -86.7% |
| Final program size | 4,252 B | 3,770 B | -11.3% |

These are descriptive values from one consumed pair. They do not establish an efficiency
effect. The treatment needed two replays while the control needed one, yet still finished
earlier because it eliminated the post-Pass search tail.

## Scientific Decision

The executable handoff mechanism is qualified. It solves the specific operation-layer
failure that incumbent retention could not reach: turning a verified sufficient state
into a replay attempt while the reasoning session is still active.

Runner 0.6.0 had one causal-design flaw: its initial treatment prompt disclosed the future
handoff, so pre-trigger search was not perfectly matched. Runner 0.6.1 removes that text
and gives control and treatment identical tools and initial prompts. The handoff instruction
appears only after `candidate_ready`. This correction is regression-tested but carries no
new live effect claim.

The next experiment is a fixed prospective bad-case comparison with runner 0.6.1. No
qibolab-specific dependency, checkpoint, cross-case memory, or new action gate is added.
