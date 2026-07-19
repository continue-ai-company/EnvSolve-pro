# P4E Repository Replay Protocol

## Objective

P4E closes the gap between isolated typed repairs and repository-level
execution. It treats each bootstrap or verifier outcome as new evidence,
classifies the resulting constraint state, applies at most one verified typed
repair, and replays from a clean checkout. Repository identities may appear in
artifacts, but repair selection must not branch on them.

P4 completion does not mean suppressing every static-analysis diagnostic. A
Dev-5 case is handled when it reaches an auditable terminal class:

- `official_pass`: bootstrap exits zero and the benchmark-owned issue count is
  zero;
- `bootstrap_satisfied_verifier_open`: bootstrap exits zero, while remaining
  verifier findings are retained as typed module obligations for P5;
- `repair_exhausted`: every supported, evidence-grounded repair has failed its
  independent verification gate;
- `intrinsic_or_optional`: a finding is proven to be platform-guarded,
  test/documentation/tooling-only, or outside declared project metadata;
- `infrastructure_blocked`: execution could not produce semantic evidence.

Only the first two classes satisfy P4's environment-bootstrap objective.
Official leaderboard success remains exactly the frozen EnvBench criterion.

## Dev-5 audit

The frozen deterministic and DeepSeek V4 Pro runs are development-consumed
inputs. EnvBench's Python evaluator counts only `reportMissingImports` in
`issues_count`; total Pyright errors are diagnostic evidence and are not a P4
repair target.

The agent run bootstrapped four of five cases. `pytest-xdist` reached official
pass. `gpkit`, `reticulum`, and `poetry` reached bootstrap success with open
module obligations. `inflect` failed before verification because a directory
created by the evaluator was interpreted by setuptools as a second top-level
package. This is the first P4E replay target.

## Round 1: verifier-owned workspace artifacts

A `workspace_artifact_conflict` may be emitted only when all of the following
hold:

1. the failing diagnostic names multiple discovered top-level paths;
2. at least one named path has provenance proving that the verifier created it
   before bootstrap;
3. the path is relative, top-level, non-symlinked, and not tracked by the target
   repository;
4. its content hash is captured before mutation.

The repair may temporarily relocate only proven verifier-owned paths outside
the repository, execute the unchanged package installation command, and restore
the exact path before verification continues. The postcondition requires the
restored content hash to equal the precondition hash. Failed installation or
failed restoration cannot commit a repaired fact.

## Iterative controller

Each clean replay records repository revision, evaluator image identity,
bootstrap script hash, action result, normalized conflicts, repair plan,
independent probes, official metrics, and terminal class. The controller stops
on a terminal class, an unsupported conflict, a repeated state fingerprint, a
failed verification gate, or the preregistered round budget.

Later P4E rounds may add module-to-distribution discovery, but candidate names
must come from package metadata or an independently recorded provider. Import
stubs, source edits, verifier configuration changes, broad ignore rules, and
case-specific package maps are prohibited.

## Integrity

- Dev-5 and previously consumed development extensions may be replayed.
- Canary-20 and Official-Test-100 remain uninspected.
- Every new benchmark execution requires a preregistration written first.
- No model request is required for P4E Round 1.
- Frozen P0-P4D sources and manifests remain immutable.

