# EnvSolve-Pro F/O/R Mechanism Casebook

Status: consumed-development evidence, 2026-08-26; not a held-out performance claim

## Question

The fixed study isolates two additions to a continuous strong-Agent session:

- `F`: free search with repository feedback;
- `F+O`: `F` plus the complete executable public goal;
- `F+O+R`: `F+O` plus target-state replay of a proposed complete program.

All arms use the same model, image, request safety cap, integrity contract, and
post-episode Official evaluator. Infrastructure-tainted outcomes are censored before
paired comparison. The corrected machine-readable analysis is
`experiments/runs/envsolve_pro_for_v1_consumed6_corrected_analysis.json`.

## Paired Outcomes

| Pair | Repository | F | F+O | F+O+R | Causal use |
| --- | --- | --- | --- | --- | --- |
| 01 | conan-package-tools | Fail | Pass | Pass | O gain; R certifies but adds no success |
| 03 | pyrollbar | Censored | Censored | Pass | Descriptive only |
| 08 | langgraph | Censored | Censored | Pass | Descriptive only |
| 11 | geoapps | Generation Fail | Generation Fail | Generation Fail | Eligible hard-case failure in both contrasts |
| 12 | sphinx-gallery | Fail | Fail | Pass | R-only Fail-to-Pass repair |
| 16 | nonebot2 | Censored | Censored | Pass | Descriptive only |

Among the three eligible `F` versus `F+O` pairs, public-goal observation produces one
treatment-only Pass and two neither-Pass outcomes. Among the three eligible `F+O` versus
`F+O+R` pairs, replay produces one both-Pass, one treatment-only Pass, and one
neither-Pass outcome. There are no control-only Passes in either contrast, but the sample
is too small and already consumed to estimate generalization.

The only common-success replay pair is Conan. Relative to `F+O`, `F+O+R` uses 24 more
model requests, 1,358,064 more tokens, six more shell commands, and 1,903.6 more seconds.
Replay is therefore not currently an efficiency treatment.

## Decisive Trajectories

### Public Goal: Conan

`F` stopped with one missing import, `conans.client.loader_parse`. `F+O` used the exact
public residual to close the remaining compatibility gap and passed Official. `F+O+R`
also passed, and its first replay passed. This pair supports the Observation hypothesis,
while showing no additional replay success and substantial replay overhead.

### Target-State Replay: Sphinx-Gallery

`F` and `F+O` both failed Official. `F+O+R` proposed a complete program whose first clean
replay failed because Git rejected the fresh checkout as dubious ownership. The same
session added a `safe.directory` operation to the program; the second replay and Official
evaluation passed. This is the cleanest Operation-layer counterexample: the construction
state hid a target-state precondition, and executable replay exposed it early enough for
the active session to repair the deliverable.

### Unsatisfied Goal and Delivery Drift: Geoapps

All three arms exhausted 120 model requests without submission. The goal-aware arms made
substantial construction progress on Linux ARM, including PySide2, GDAL/Fiona,
`c-blosc2`, and the repository's old numerical stack. Correct Python-path observation
reduced 477 apparent missing imports to one within the source package.

The full Official scan then mixed three kinds of residual:

- installable development dependencies;
- repository defects or obsolete Python 2 documentation imports;
- imports intentionally missing inside tests of missing-module behavior.

`F+O+R` reached a construction-only metric Pass by creating `typings/`, but never called
replay or submission and later reset the construction commit. `F+O` tried excluding
directories through Pyright configuration, then created a source-tree compatibility shim
and a copied package tree. It also found 19 runtime module-import failures despite a
package-scope Pyright Pass. No candidate was submitted; the final candidate workspace had
258 untracked files.

Geoapps therefore does not show that replay failed after activation. It shows two other
failures: the optional replay interface was ignored, and an integrity-preserving
deployment could not satisfy the benchmark residual by environment changes alone. The
case remains in the eligible mechanism study as a neither-Pass outcome, while Official
success and deployment integrity must be reported on separate axes.

## Mechanism Decision

The evidence supports one minimal interface repair:

```text
submit(P):
    execute P and the public goal from the target initial state
    if Pass: return P
    if Fail: return the first executable counterexample to the same Agent session
```

There should be no separate unchecked submission action and no separate optional replay
action. The Agent still decides when to submit and how to repair. The harness only makes
delivery transactional: a proposed program either reconstructs a passing target state or
returns evidence to the active session.

This decision does not add package rules, structured hypothesis search, container
checkpoints, forced handoff, or cross-case memory. It must be tested prospectively on a
new fixed batch; the consumed cases above cannot validate the revised interface.
