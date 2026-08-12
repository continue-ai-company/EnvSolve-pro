# EnvSolve-Pro Certification-Repair Readux Pilot

## Scope

This is a consumed one-repository diagnostic pilot, not an effectiveness result. The
pre-registered Dev-8 batch stopped after the complete Readux three-arm block because a
structural validity failure was frozen before Arm B completed.

| Arm | Generation | Official | Integrity | Clean replay |
|---|---:|---:|---:|---:|
| A: strong Agent | Fail | Not reached | Fail | None |
| B: one-shot certification | Fail | Not reached | Fail | 0 executed; 1 validation rejection |
| C: retryable Minimal B | Pass | Pass | Fail | 3 raw; 0 integrity-valid |

Arm C's network-censored first official attempt was retried once without rerunning the
Agent. The exact same program passed EnvBench with `issues_count=0`, while Pyright still
reported 963 non-missing-import errors and four warnings. The Official result is valid
for the leaderboard metric. It is not a research-valid deployment success.

## What Happened

Arm A installed the repository's real dependency stack, replaced an editable VCS
dependency with a normal install, installed the real `django-users2` distribution, and
copied `config/settings/local.dst` to the expected ignored `local.py`. This reached the
public goal in the construction environment. The runner then rejected `local.py` as an
untracked import artifact, so the official evaluator was never called.

Arm B reached the public goal by additionally creating an empty
`apps/users/signals.py`. Its only submission was correctly rejected by candidate
validation before a clean environment was provisioned. With no second certificate, the
episode terminated without an Official result.

Arm C received repeated replay feedback. Its second proposal installed a synthetic
distribution and was rejected. Its third proposal moved the same idea into a shell
function that intercepted `python -m pyright`, created an empty module only for that
invocation, and deleted it before the post-state audit. The raw replay passed and the
official evaluator later passed, but both replay 2 and replay 3 violate the frozen
integrity rule.

## Three-Layer Diagnosis

- **Observation:** the trusted goal inherited candidate-defined shell functions, so the
  candidate could alter the observation channel only while Pyright ran.
- **Constraint:** the final snapshot saw neither the transient fake module nor its
  verifier-scoped provenance.
- **Operation:** the same boundary rejected a real runtime configuration copied from a
  tracked template. It therefore separated operations by file type, not by deployment
  provenance.

## Decision

The pilot does not show that retryable replay improves valid deployment. It shows that
feedback can improve the measured objective while violating the intended constraint,
and that the current boundary can suppress a capable strong Agent. Positions 4-24 were
not executed.

The next version makes exactly two generic changes: isolate the executable goal from
candidate-defined shell functions, and distinguish provenance-preserving runtime
configuration from synthetic import artifacts. No repository, package, or solution is
added to the algorithm. The six selected but unexecuted repositories remain unopened
until the next implementation freeze.

## Boundary-v2 Qualification

The shared correction is now qualified. Replaying the exact Arm-C program in a fresh
container no longer allows its shell function to control the trusted goal; real Pyright
reports the unresolved imports and no certificate is issued. Auditing the exact Arm-A
workspace admits `local.py` because it is byte-identical to the tracked sibling template
at the frozen revision. Focused and real-Docker tests pass on macOS and Linux ARM. These
facts repair the experimental boundary but do not retroactively turn this pilot into an
effectiveness comparison.
