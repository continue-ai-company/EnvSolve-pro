# EnvSolve-pro P0 High-Value Casebook v1

## Scope

This casebook records development observations that expose general algorithmic
failure modes. It is not an effectiveness table and does not convert selected P0
cases into optimization targets. Any proposed repair must be stated generically,
tested with synthetic or already-consumed fixtures, frozen, and only then evaluated
on untouched cases.

## Case P0-001: `wpi-lnl/lnldb@6384c05`

**Status:** all four native methods have terminated. Only Codex reached the official
evaluator, so this case supports failure analysis but not a complete effectiveness
comparison.

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
| EnvBench raw ReAct | Reached its 30-iteration native limit and did not finish. The final ledger records 31 responses, 806,340 tokens, and 1,447 seconds. Replay IR then rejected three successful shell forms, so no official evaluator ran. | Free-form reasoning recovered key evidence and several failures, but context growth, iteration use, and post-hoc trajectory parsing censored the terminal result. |

### Frozen EnvSolve v1 Candidate Trace

| Candidate | Observation and operation | Outcome | General failure mode |
|---|---|---|---|
| 1 | Used the default Python and installed roughly 70 unpinned package names. | Failed building `psycopg2` because `pg_config` was absent. | Repository constraints were not enforced by the first operation. |
| 2 | Replaced `psycopg2` with `psycopg2-binary` but otherwise kept latest packages. | Command exited 0 and installed Django 6.0.7, which violates the repository bound. | Shell success was accepted as useful evidence despite semantic inconsistency. |
| 3 | Reintroduced many exact package versions, including Django 2.2.28. | The aggregate resolver reported no version for `boto3==1.14.47`; candidate 5 later showed that isolated installation succeeds. | The loop treated a resolver symptom as a single-package fact instead of preserving the compound conflict context. |
| 4 | Correctly inferred that the modern Python runtime was causal and proposed installing Python 3.8.13 through `pyenv`. | Rejected before execution with exit 252 because the operation guard did not recognize `git clone` for acquiring `pyenv`. | A closed textual action vocabulary blocked a directionally correct strong-model repair. |
| 5 | Split the failed aggregate install into several commands while retaining the default runtime. | Isolated `boto3==1.14.47` succeeded, later installs restored Django 6.0.7, and the run failed on `natural-duration==0.1.0`; the repository actually declares that dependency through Git. | Splitting can isolate resolver conflicts, but lost VCS provenance and missing whole-environment postconditions still prevent convergence. |

### Raw ReAct Trace

The raw agent read `runtime.txt`, all recursive requirements, the README, and Travis
configuration before installing. It then:

1. recovered from a Conda HTTP failure by switching providers;
2. installed and activated the declared Python 3.7.7 through `pyenv`;
3. recovered from a pip read timeout by increasing the timeout;
4. constrained `python-bidi`, added `libpq-dev`, isolated a `docutils`/`botocore`
   conflict, and replaced the incompatible `psycopg2` build; and
5. reached Django application initialization, where an outbound Microsoft OpenID
   request failed with an SSL connection error.

At the iteration boundary the model reported that it needed more steps. The frozen
Replay IR then rejected a read-only `pyenv` pipeline, creation of a temporary
constraints file, and `pip uninstall`. This episode is therefore recorded as a native
incomplete trajectory with a wrapper-induced Unknown official outcome. It is not
selectively rerun.

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
- Replayable operations should be recorded as typed events when tools execute. A
  post-hoc shell parser should not be able to erase an otherwise valid trajectory.
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
- **H5: Effect-preserving traces.** Execution-time typed action capture reduces
  wrapper-induced Unknown outcomes compared with post-hoc shell distillation.

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
- Raw ReAct run ID: `pro-p0-v1-c01-envbench-raw-react`

## Case P0-002: `columnflow/columnflow@ad04770`

**Status:** Repo2Run reproduced, frozen EnvSolve v1, and raw ReAct have terminated
with native generation failures. Codex CLI was not launched because its frozen
executable was replaced by an automatic App update, so that position is Unknown.
No cross-method effectiveness conclusion is allowed.

### Why This Partial Trace Is Valuable

The repository separates core installation from optional execution environments.
`setup.py` installs only `sandboxes/cf.txt`, while the tests exercised by the case
also require packages declared in `sandboxes/columnar.txt`. Missing optional modules
are deliberately represented by callable mock objects, so an import can appear to
succeed before tests reveal that the environment is semantically incomplete.

### Repo2Run Observation

Repo2Run completed 20 model responses with no provider or network errors. It used
286,631 total tokens and 552 seconds, entered a Python 3.10 container, installed the
project editable, then added `law` and `order` and repeatedly set project environment
variables. Test collection still failed because `awkward` remained a mock module.
The exact repository declaration was `awkward==2.4.6` in
`sandboxes/columnar.txt`, which the agent had read but did not install.

The upstream process then indexed an absent final agent response and raised a
`TypeError`. Generation therefore ended without a replayable candidate or official
evaluation. This is a valid native baseline failure, not an infrastructure retry:
model responses and 118 inner command records were both present.

### Frozen EnvSolve v1 Observation

Frozen EnvSolve exhausted five fresh candidates without reaching the official
evaluator. It completed five model responses with no request errors, used 44,916
total tokens and 543 seconds, and ended at the candidate, command, and environment
limits simultaneously.

The repository profiler passed `setup.py` and a truncated README to the model, but
the structured declaration observer admitted no repository evidence: zero files,
zero runtime requirements, and zero source bytes. The initial constraint state
therefore contained only the base Python 3.13.2 runtime fact. The candidate sequence
then exposed one compatibility frontier per fresh environment:

| Candidate | New operation or inference | Terminal observation |
|---|---|---|
| 1 | Created a venv with base Python 3.13.2 and installed the project editable. | Rejected by `python_requires >=3.7, <=3.11`. |
| 2 | Acquired Python 3.11.11 through `pyenv`. | Rejected because the PEP 440 bound `<=3.11` does not include `3.11.11`. |
| 3 | Correctly moved to Python 3.10.11. | Project installation and `pip check` passed; the internal verifier lacked `pytest`. |
| 4 | Added `pytest`. | Test collection exposed the undeclared-at-install-time `law` module. |
| 5 | Added `law` and `pytest`. | Collection advanced to unresolved setup variables; `law.cfg` parsed `$CF_WLCG_USE_CACHE` as a literal non-boolean. |

The trajectory shows real progress, but each fresh candidate repeats runtime
acquisition and can discharge only the next newly visible obligation. This is not
evidence that fresh isolation is wrong; it is evidence that observations learned in
one environment must be summarized into a sufficiently complete compatibility
frontier before spending the next environment.

### Codex CLI Infrastructure Deviation

The preregistered executable was `codex-cli 0.145.0-alpha.18` with SHA-256
`f0b214b476e04175bee104fe441caea874baeef3efc3828bfb79e972266156a9`. Before this
position began, the desktop App automatically replaced it with
`0.145.0-alpha.27`. The official OpenAI release and the nearest official historical
desktop package both supplied `0.145.0-alpha.18`, but with different executable
hashes. Version equality is not byte-level boundary equality, so no substitute was
silently introduced and no Codex model or container command was run. The scheduled
position is recorded as Unknown rather than selectively rerun under a changed
external boundary.

### Raw ReAct Observation

Raw ReAct reached its native 30-iteration limit after 31 budget-ledger responses,
719,190 total tokens, 270 seconds, and no provider errors. It inspected `setup.py`,
`setup.sh`, all named sandbox requirement files, and the submodule declarations;
selected Python 3.10.13; installed the project and development requirements; and
initialized and installed the repository-pinned `law` and `order` submodules. Its
last semantic check reached the same unresolved `$CF_WLCG_USE_CACHE` configuration
frontier as frozen EnvSolve, then reported `Sorry, need more steps to process this
request.`

Replay IR v9 preserved 11 typed actions but rejected the successful
`git submodule update --init --recursive` command as unknown. The official evaluator
therefore did not run. This episode has two distinct terminal facts: the native agent
did not finish within its iteration setting, and the wrapper could not represent a
repository-declared source acquisition that the agent had already executed
successfully.

### Three-Layer Diagnosis

**Observation layer:** package declarations are conditional and distributed across
named environment files. Import success is weak evidence when a project intentionally
substitutes missing modules with mocks; the first semantic call is more informative.
The structured observer also failed to admit declarations that were already visible
in the repository profile, forcing runtime and setup obligations to be rediscovered
through failed executions.

**Constraint layer:** the solver needs to connect the selected test surface to the
environment-specific declaration that satisfies it. A flat union of every optional
environment would over-install, while using only `install_requires` is incomplete.
New execution feedback must update a compact frontier that distinguishes runtime
compatibility, verifier prerequisites, project extras, and configuration obligations;
otherwise a fixed candidate count becomes a fixed number of serial discoveries.

**Operation layer:** after a mock-module failure, the useful operation is not an
unbounded package guess. It is a provenance-backed activation or installation of the
smallest declared optional environment whose dependency provides that module. Fresh
containers should replay a revised complete plan, while deterministic runtime
acquisition can be cached without sharing mutable candidate state. Repository-pinned
submodule initialization is a typed source-acquisition operation, not an arbitrary
shell escape.

### Candidate General Hypothesis

- **H6: test-conditioned declaration reachability.** Relating observed test/import
  obligations to repository-declared optional environments should reduce both
  missing optional dependencies and indiscriminate installation. This hypothesis
  must be tested on repository-neutral fixtures before any EnvSolve change and then
  evaluated on untouched cases.
- **H7: observation-state completeness.** Admitting compatible declarations already
  present in profiled files should reduce serial rediscovery without adding
  repository-specific rules.
- **H8: frontier-preserving replanning.** Updating one typed compatibility frontier
  from each verifier failure should solve more obligations per fresh candidate than
  appending the latest error alone.
- **H9: provenance-backed source expansion.** Representing repository-declared
  submodule acquisition as a typed operation should reduce wrapper-induced Unknown
  outcomes without opening unrestricted source mutation.

### Anti-Overfitting Gate

No repair may special-case `columnflow`, `law`, `order`, `awkward`, WLCG, or any
`CF_*` variable. Observation and operation changes must target general declaration,
optional-environment, submodule, or configuration types; pass repository-neutral
fixtures; and be frozen before the next untouched case is opened.

### Evidence Anchors

- Repo2Run run ID: `pro-p0-v1-c02-repo2run-reproduced-r2`
- Native usage: 20 responses, 286,631 total tokens, 552 seconds
- Preserved raw trace: `generation/repo2run_raw/inner_commands.json`
- Raw trace SHA-256: `fc4325962623cac1e3a567394ffba462857f710d9e6a1a96e7956a6807c26ae8`
- Frozen EnvSolve run ID: `pro-p0-v1-c02-envsolve-v1-frozen`
- Frozen EnvSolve usage: 5 responses, 44,916 total tokens, 543 seconds
- Codex scheduled run ID: `pro-p0-v1-c02-codex-cli-native` (not launched; Unknown)
- Raw ReAct run ID: `pro-p0-v1-c02-envbench-raw-react`
- Raw ReAct usage: 31 ledger responses, 719,190 total tokens, 270 seconds
- Raw ReAct distillation: 11 kept actions, 1 unsupported successful command
- Raw ReAct native trajectory SHA-256:
  `cbf6771459347acd61c09bce056c56c8940cb679ef2c956c8b7435ea029dedd8`
- Runtime deviation record:
  `experiments/validations/pro_p0_external_baselines_v1_runtime_deviations.json`
