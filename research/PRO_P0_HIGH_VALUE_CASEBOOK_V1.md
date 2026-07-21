# EnvSolve-pro P0 High-Value Casebook v1

## Scope

This casebook records development observations that expose general algorithmic
failure modes. It is not an effectiveness table and does not convert selected P0
cases into optimization targets. Any proposed repair must be stated generically,
tested with synthetic or already-consumed fixtures, frozen, and only then evaluated
on untouched cases.

## Case P0-001: `wpi-lnl/lnldb@6384c05`

**Status:** Repo2Run, Codex CLI, and frozen EnvSolve v1 have terminated. The raw ReAct
episode remains pending, so cross-method findings are provisional.

### Why This Case Is Valuable

`lnldb` is an older Django application with a declared Python 3.7.7 runtime, nested
requirements files, bounded package versions, and editable Git dependencies. It
separates four capabilities that are easy to conflate:

1. reading repository evidence;
2. preserving that evidence as constraints with provenance;
3. proposing operations that satisfy the constraints; and
4. recognizing semantic success rather than shell success.

### Repository Evidence

- `runtime.txt`: `python-3.7.7`
- `requirements.txt` includes `requirements_base.txt` and pins production-only
  packages such as `boto3==1.14.47` and `psycopg2==2.7.1`.
- `requirements_base.txt` constrains `Django>=2.2.13,<3.2` and contains several
  editable Git dependencies at explicit revisions or branches.

### Native Method Observations

| Method | Observed terminal or current state | Diagnostic value |
|---|---|---|
| Repo2Run reproduced | Native generation failed after 16 successful model responses; no official evaluator. The built environment retained a modern Django and the upstream agent crashed while indexing an absent agent result. | A long command loop can still miss a decisive version constraint; baseline robustness must be separated from environment correctness. |
| Codex CLI | Built a Python 3.8 environment, installed `requirements_debug.txt`, and ran Django checks/tests. Official evaluation completed but failed with 1,629 errors; the two missing-import findings were `django.conf.settings` and `django.core.urlresolvers`. | A strong free-form agent adapted to a network timeout and chose a plausible legacy runtime, but local checks and the official target were not aligned. |
| Frozen EnvSolve v1 | Native failure after exhausting five candidates; no official evaluator. It used five successful model responses, four executed environments, 68,063 total tokens, and 2,316 seconds. | The trajectory directly tests whether structured state helps or constrains a strong model. |

### Frozen EnvSolve v1 Candidate Trace

| Candidate | Observation and operation | Outcome | General failure mode |
|---|---|---|---|
| 1 | Used the default Python and installed roughly 70 unpinned package names. | Failed building `psycopg2` because `pg_config` was absent. | Repository constraints were not enforced by the first operation. |
| 2 | Replaced `psycopg2` with `psycopg2-binary` but otherwise kept latest packages. | Command exited 0 and installed Django 6.0.7, which violates the repository bound. | Shell success was accepted as useful evidence despite semantic inconsistency. |
| 3 | Reintroduced many exact package versions, including Django 2.2.28. | The aggregate resolver reported no version for `boto3==1.14.47`; candidate 5 later showed that isolated installation succeeds. | The loop treated a resolver symptom as a single-package fact instead of preserving the compound conflict context. |
| 4 | Correctly inferred that the modern Python runtime was causal and proposed installing Python 3.8.13 through `pyenv`. | Rejected before execution with exit 252 because the operation guard did not recognize `git clone` for acquiring `pyenv`. | A closed textual action vocabulary blocked a directionally correct strong-model repair. |
| 5 | Split the failed aggregate install into several commands while retaining the default runtime. | Isolated `boto3==1.14.47` succeeded, later installs restored Django 6.0.7, and the run failed on `natural-duration==0.1.0`; the repository actually declares that dependency through Git. | Splitting can isolate resolver conflicts, but lost VCS provenance and missing whole-environment postconditions still prevent convergence. |

### Three-Layer Diagnosis

**Observation layer: what happened?**

- High-value repository evidence includes runtime declarations, recursive
  requirements, version ranges, editable/VCS sources, and evaluator findings.
- Hundreds of package presence and import facts are lower value than the small set
  of compatibility-defining facts.
- Network events must remain separate observations. A hotspot interruption was
  reported during the broader batch, but this EnvSolve episode has no model request
  error and continued making download progress; it is not eligible for selective
  restart.

**Constraint layer: what is missing or conflicting?**

- Constraints need full requirement semantics and provenance, not only normalized
  package names.
- A failure should preserve a contextual conflict or unsatisfied core over runtime,
  provider, and requirements, not become either a literal error-message fact or a
  blacklist of one command string.
- Constraints require compression and priority. Thousands of package/import facts
  should not obscure runtime and framework compatibility boundaries.

**Operation layer: how can the environment change?**

- The operation space must remain expressive enough for strong agents to acquire a
  runtime or provider that the fixed catalog did not anticipate.
- Safety should be based on typed intent, provenance, preconditions, and verified
  effects rather than an exhaustive shell-text whitelist.
- Fresh candidate environments preserve causal auditability. Deterministic base
  layers may be cached to avoid repeating system downloads without sharing mutable
  candidate state.

### Testable Hypotheses

- **H1: Evidence fidelity.** Preserving runtime, recursive requirement, and VCS
  provenance reduces incompatible first candidates without narrowing valid actions.
- **H2: Semantic no-goods.** Contextual conflict records reduce repeated equivalent
  failures compared with exact-command blacklists.
- **H3: Open but verified operations.** A typed acquisition fallback improves solve
  rate over a closed action vocabulary without increasing unsafe or unauditable
  execution.
- **H4: Constraint prioritization.** A compact compatibility frontier produces
  better candidates than exposing every low-level fact at equal salience.

### Anti-Overfitting Gate

No repair may special-case `lnldb`, Django, `boto3`, `psycopg2`, or `pyenv`. A repair
must operate on general runtime, requirement, provider, conflict, or acquisition
types; pass unit fixtures that do not contain this repository; and be frozen before
the next untouched development cases are opened.

### Evidence Anchors

- Case selection and schedule:
  `experiments/validations/pro_p0_external_baselines_v1_schedule.json`
- Frozen EnvSolve run ID: `pro-p0-v1-c01-envsolve-v1-frozen`
- Codex run ID: `pro-p0-v1-c01-codex-cli-native`
- Repo2Run run ID: `pro-p0-v1-c01-repo2run-reproduced`
