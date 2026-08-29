# EnvSolve-Pro Minimal B: Fixed Bad4 Result

## Scope

This is a four-pair **development mechanism diagnosis**, not held-out or leaderboard
evidence. The cases were selected before these episodes from the recorded Dev failure
stratum. Every pair used the same DeepSeek V4 Flash 0731 model, provider policy, public
goal, image, seed, and safety caps. The control was one goal-aware continuous Agent
session (`F+O`); the treatment added Agent-invoked clean target-state replay and required
the delivered program to match a passing replay (`F+O+R`).

The manually interrupted original Meerkat control is excluded and replaced by its
approved same-arm replacement. OpenQASM treatment uses the approved exact-script
evaluation-only retry after the first Official attempt ended in a read timeout.

## Primary Result

| Repository | `F+O` | `F+O+R` | Replay evidence |
| --- | ---: | ---: | --- |
| `hazyresearch/meerkat` | No pass | No pass | treatment never formed a replayable candidate |
| `pysnmp/pysnmp` | Pass | Pass | two Unknown, then Pass |
| `openqasm/openqasm` | Pass | Pass | first replay Pass |
| `stopstalk/stopstalk-deployment` | No pass | No pass | treatment never formed a replayable candidate |

Both arms scored `2/4` Official Pass. There were no discordant pairs, so the treatment
effect on this fixed batch is exactly zero. The same result holds under the protocol-
compliant endpoint.

## Mechanism Finding

The two true noncompletions occurred **before replay activation**. Meerkat and Stopstalk
both exhausted 120 model requests without a submission in either arm; the treatment made
zero replay calls. Repeatable replay can certify or repair a complete candidate, but it
does not help when the Agent cannot yet turn its construction history into one legal
program.

Pysnmp exposed a treatment-only harness defect. Its first two replay programs reached the
public goal with zero missing imports, but the import-provider audit used a Python 3.10
API under the repository's Python 3.9.7 environment and returned Unknown. The Agent then
changed to Python 3.11; the third replay and Official evaluation passed. The compatibility
bug is fixed in `f923d7e`, without weakening the audit. Pysnmp remains an Official Pass,
but its replay-repair and resource path are confounded and its final Python version is
less faithful than the control's Python 3.9 environment.

OpenQASM shows a narrower benefit: treatment reached an Official-passing path with 51
model requests and 1.24M tokens, versus 106 requests and 3.98M tokens for control. However,
the treatment program optimized the public goal without editable-installing the local
projects, while the control built a fuller environment. This is an Official-goal path
gain, not an equal-completeness efficiency result.

Across the two common-success pairs, treatment averaged 56.5 versus 83 model requests,
1.38M versus 2.73M tokens, and 1,896 versus 2,004 generation seconds. These descriptive
means are not an efficiency claim because one pair has the harness defect and the other
has a deployment-completeness mismatch.

## Decision

Minimal B is retained as a useful baseline, not selected as the final EnvSolve-Pro
algorithm. The next method must move executable feedback into **candidate formation**:
the active session should expose and validate incremental deployment state before a
complete bootstrap exists. It must remain model-led and case-local, avoid package-specific
rules, and keep Official success, deployment completeness, and resource use as separate
axes. A new treatment will be opened only after the transition is deterministic on
consumed traces and the comparison is fixed before observing new outcomes.

Machine-readable evidence:

- `experiments/schedules/envsolve_pro_v2_minimal_b_bad4_v1_effective.json`
- `experiments/validations/envsolve_pro_v2_minimal_b_bad4_v1_result.json`

