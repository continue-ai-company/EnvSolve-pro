# P6 Q10 Terminal Calibration Results

Status: closed development calibration. All ten preregistered scripts were attempted
exactly once; there were no model calls, replacements, overwrites, or retries.

## Integrity

All ten run artifacts pass the harness audit. Every evaluated script matches its
precommitted SHA256, every repository revision matches the selected case, and every
run records the frozen clean EnvBench revision and immutable Docker image ID and
RepoDigest.

| Outcome | Count |
| --- | ---: |
| Audit-valid scripts attempted | 10 |
| Official evaluation completed | 9 |
| Infrastructure `Unknown` | 1 |
| Official Pass | 0 |
| Internal false / Official false | 9 |
| Internal false / Official true | 0 |
| Bootstrap succeeded | 3 |
| Pyright result observed | 3 |

The single `Unknown` was a preregistered no-retry `read-timeout`. It is not treated
as a Boolean failure or used to estimate verifier agreement.

## Calibration Result

No completed script was an internal-verifier false negative. Six of nine completed
evaluations failed during bootstrap. The remaining three completed bootstrap but
failed terminal static analysis: one had 824 Pyright errors and 58 warnings, while
the two matched reddit2telegram scripts each had 61 errors and 3 warnings.

The full condition reached Pyright on two of five scripts; the ablation reached it
on one of five, with one ablation `Unknown`. These tiny development counts are
descriptive and do not support an effectiveness claim.

The bootstrap failures expose generic operation-feasibility families rather than a
single verifier-scope defect: unavailable native build prerequisites, isolated
build environments missing a required build dependency, unavailable package or
source mappings, missing language toolchains, and legacy build incompatibility.
Concrete repository logs remain examples, not algorithm rules.

## Research Decision

The Boolean internal gate remains frozen. This calibration provides no evidence
that relaxing it would recover a passing deployment. It does reveal a feedback
quality issue: a fixed check can stop internal verification before other independent
constraints are observed, even when the Official bootstrap later succeeds. The
remedy is not to accept that script, but to avoid first-error masking while retaining
the conjunction of mandatory checks.

The dominant solver defect is earlier: deterministic candidate-command failures are
recorded as bounded feedback and exact failed prefixes, but they are not yet a
first-class, provenance-bearing operation outcome in constraint state. The next
minimal mechanism revision should represent the failed operation, its observed
environment, and its unresolved precondition without encoding repository or package
names. Synthetic counterexamples must show that a subsequent complete program
changes a relevant precondition before repeating the failed operation. Only after
this mechanism is frozen should a new outcome-blind development batch be selected.

## Claim Boundary

This calibration uses consumed Q10 development identities. It does not reopen Q10,
estimate leaderboard performance, or unlock held-out evaluation. Its contribution
is a falsified hypothesis: terminal non-reach was not hiding successful scripts in
the nine completed calibrations. The next target is operation feasibility and search
efficiency under partial observability.
