# EnvSolve-pro Objective-Alignment Diagnostic v1

## Scope

This post hoc diagnostic uses only the two consumed P4 trajectory censuses. Nine of
16 cases contain both an accepted-candidate verification and a completed Official
evaluation; the remaining seven are excluded from module-set comparisons. The result
cannot support an effectiveness claim.

## Result

The accepted candidates' static unresolved-module proxy covered `40/41` official
`reportMissingImports` modules (`97.6%` recall). The same candidates carried 70
internal module obligations, of which 30 did not match an official missing module.
Twenty-five excess obligations came from Conan Package Tools. Excess obligations
appeared in four repositories, and one Official Pass retained an internal unresolved
constraint.

## Interpretation

The eligible subset does not support a broad observability failure: the internal
static proxy usually sees the scored missing module. It instead raises a precision
hypothesis: runtime import failures and resolver differences may amplify a small
scoring frontier into many non-scoring obligations. The concentration in one case
prevents declaring this the dominant contradiction. The frozen cross-method census
must determine whether objective dilution is a repeated earliest decisive divergence
across repositories before any solver change.
