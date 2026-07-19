# P6 Constraint-Operation Qualification V6 Results

Status: completed development qualification; all five identities are consumed.

## Frozen execution

- Selection and schedule revision: `47fa4e56f4d76acbac53ac78f09e5b5bb5a06464`.
- Schedule SHA256: `b5c640e40b0e38af259758565077070e5c28dda34f5fc939d66ee70d4c6bb025`.
- Model: `deepseek/deepseek-v4-pro`; five candidates, commands, and fresh environments
  per episode; 7,200-second generation and 9,600-second coordinator limits.
- All 10 runs are artifact-valid, schedule-consistent, within primitive budgets,
  produced complete heartbeats without host suspension, and are scientifically
  eligible under the frozen Q6 contract. No model request failed.

## Outcomes

| Case | Full EnvSolve | Free-form ablation | Official pair |
|---|---|---|---|
| `django-mysql` | candidate limit; 5 candidates; 28,710 tokens; 182.1 s | candidate limit; 5 candidates; 41,408 tokens; 603.0 s | censored: no official evaluation |
| `plugins` | candidate limit; 5 candidates; 47,351 tokens; 492.6 s | candidate limit; 5 candidates; 39,216 tokens; 382.2 s | censored: no official evaluation |
| `helios-server` | candidate limit; 5 candidates; 31,885 tokens; 583.1 s | candidate limit; 5 candidates; 39,270 tokens; 720.7 s | censored: no official evaluation |
| `rebench` | internal pass in 2 candidates; official fail with `issues_count=1` | internal pass in 2 candidates; official fail with `issues_count=28` | neither passes |
| `datasets` | execution-timeout Unknown after 1 candidate; 5,604 tokens; 935.4 s | execution-timeout Unknown after 2 candidates; 15,603 tokens; 1,926.2 s | censored: no official evaluation |

The deterministic summary contains zero official passes, two official fails, and
eight runs without an official Boolean. Only one of five pairs enters the paired
official estimate, and neither method passes that pair. Q6 does not qualify the
current operation mechanism and supports no effectiveness claim.

## Error analysis

1. **The operation layer is reactive at episode start.** The first full-method
   `OperationPlan` is empty because repository observations are not yet converted
   into initial constraints. In the three candidate-limit cases, both methods
   discover dependencies sequentially and exhaust the same five-candidate budget.
2. **Internal import coverage omitted documentation sources.** Full EnvSolve reduced
   `rebench` from 28 official missing-import issues to one, but the remaining
   `recommonmark.parser` import lives in `docs/conf.py`.
3. **Unsigned execution timeouts were censored as infrastructure failures.** The
   `datasets` logs instead show pip dependency backtracking and expensive build
   dependency installation. A timeout is infrastructure Unknown only when its logs
   contain a recognized DNS, TLS, HTTP, or connection signature.
4. **Internal success is not yet calibrated to official success.** Executable setup
   and official static closure remain distinct outcomes. The full condition's
   `issues_count=1` near miss is informative but still a Fail.
5. **Evaluator provenance is recorded but not cleanly committed.** The EnvBench
   checkout contains three generic local compatibility patches with frozen source
   hashes. A shareable clean evaluator commit is required before confirmation.

## Post-Q6 mechanism corrections

Two corrections were implemented only after Q6 completed. Ordinary execution
timeouts now become candidate failures with a structured cost hypothesis, allowing
a fresh next candidate; only signed infrastructure timeouts remain Unknown.
Documentation imports now enter the same bounded, benchmark-independent two-layer
inventory as runtime, test, and build imports. Synthetic tests, the full regression
(`347 passed, 1 skipped`), and the opt-in real Docker boundary pass. These are
development-set adaptations and require new outcome-blind cases; Q6 is never rerun.

The next algorithmic milestone is a preregistered design for turning initial
repository observations into conservative constraints before the first action,
followed by a fresh paired qualification with a clean evaluator revision.
