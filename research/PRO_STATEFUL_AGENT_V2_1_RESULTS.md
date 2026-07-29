# EnvSolve-Pro Stateful Agent V2.1: Consumed-Case Mechanism Result

## Scope

This is a consumed-development mechanism result on
`bradenm/micropy-cli@ac85e9f`. It is not held-out effectiveness evidence.

## Result

- EnvBench official result: **Pass**
- Official `reportMissingImports`: **0**
- Non-scoring Pyright errors: **311**
- Model rounds: **2**
- Model candidates: **2**, plus one shared initial observation
- Container commands: **71**
- Schedule wall time: **1,446.8 seconds**
- Tokens: 3,670,827 input, of which 3,459,072 were cached; 41,474 output

The initial observation returned 70 active findings. The constraint layer
retained all findings and projected 24 complete obligation groups with no
unknown or omitted groups.

## State Transition

Candidate 1 installed the project and dependencies, then tried to create a
small `micropy` stub package. The operation layer rejected it before goal
execution because the program directly materialized an importable artifact.

Round 2 received the full rejected script and the exact rejected line and
target. Candidate 2 did not create a Python source or stub file. It installed
the dependencies and used temporary setuptools metadata to map the checkout's
`micropy/app` package to the legacy `micropy.cli` import. It passed the public
goal, repository audit, V2 source-provenance audit, and official EnvBench
evaluation in a fresh exact-revision environment.

## Mechanism Decision

Observation-role separation, observation-before-operation, and
constraint-before-operation passed. A real rejection-to-repair transition was
observed, although the preregistered divergent-source rejection itself was not
exercised.

The run is valid mechanism evidence and a valid official benchmark result.
It is not yet a clean integrity-qualified effectiveness result.

## Construct Gap

V2.1 audits source bytes and direct creation of importable artifacts, but
setuptools `package_dir` metadata can assign existing checkout source to a new
module identity. Here, `micropy.cli` is absent from the revision and was mapped
to `micropy.app`.

This does not invalidate the EnvBench Pass: EnvBench officially scores missing
imports, and the remaining 311 diagnostics are non-scoring. It does show that
source provenance and module-identity provenance are different constraints.

The next step is a small identity canary and rule:

> Source under a project namespace may be installed or copied at its declared
> module identity, but it may not acquire an undeclared import identity through
> package metadata, links, loaders, or path remapping.

The rule must be validated before repository-disjoint Dev evaluation is frozen.
