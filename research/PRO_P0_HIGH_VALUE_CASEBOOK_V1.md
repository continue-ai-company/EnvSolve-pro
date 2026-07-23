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
| Codex CLI | Built a Python 3.8 environment, installed `requirements_debug.txt`, and ran Django checks/tests. Official evaluation completed with `issues_count=2`, so the case failed. Pyright also emitted 1,629 total errors, but the other 1,627 were non-scoring diagnostics. | A strong free-form agent adapted to a network timeout and chose a plausible legacy runtime, but local checks missed two official import obligations. |
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

## Case P0-003: `marimo-team/marimo@537b230`

**Status:** all runnable scheduled methods have terminated. Repo2Run's native
verifier passed but its replay wrapper rejected the trajectory. Raw ReAct stopped
incomplete and then failed an artifact-insensitive integrity audit. Frozen EnvSolve
exhausted five candidates after following the wrong optional-dependency branch. The
scheduled Codex result is Unknown because the exact preregistered binary could not be
recovered. No official evaluator ran.

### Why This Partial Trace Is Valuable

This case separates package installation from a simple filesystem postcondition.
The project declares a test extra that supplies the Python dependencies, while test
collection also expects a generated frontend asset directory to exist. A deployment
can therefore have a consistent package graph and still fail before tests because a
required empty directory is absent.

### Repo2Run Observation

Repo2Run used eight model responses, 77,503 total tokens, and 377 seconds with no
request errors. It read `pyproject.toml`, installed the repository-declared
`.[testcore]` extra, observed collection failure caused by the absent
`marimo/_static/assets` path, created that directory, and reran its native `runtest`.
The final native verifier returned 0 and collected 1,085 tests.

The frozen Repo2Run replay layer retained only the package-install action and rejected
the successful `mkdir -p /repo/marimo/_static/assets` operation. Generation was
therefore marked non-replayable and the official EnvBench evaluator did not run. This
is recorded as native-baseline success under Repo2Run's verifier plus a
wrapper-induced Unknown official outcome, not as an EnvBench success.

### Raw ReAct Observation

Raw ReAct completed 20 model responses, used 344,440 total tokens and 561 seconds,
and had no provider errors. It followed the repository's full source-build path:
installed pnpm, attempted `make fe`, repeated the frontend build with the documented
larger Node heap, and then ran `make py`. The Python install encountered a `pyarrow`
build problem under base Python 3.13. The agent selected Python 3.12 and corrected
`PATH`, but then emitted an empty terminal response before reinstalling or running a
test. The native trajectory is therefore incomplete.

The wrapper subsequently reported 7,865 repository-integrity violations despite
zero tracked changes and zero changed source files: 7,854 symlinks, 10 Python files,
and one requirements file, all generated inside package-manager `node_modules`
trees. Dependency installation artifacts were classified as source injection without
considering their generated-root provenance, so integrity enforcement added a
separate wrapper failure. The episode is not retried.

### Frozen EnvSolve Observation

The first frozen EnvSolve episode was stopped after candidate 3 by a classified TLS
dependency-acquisition failure. The same frozen code, model, protocol, and case were
then rerun once under the preregistered infrastructure-retry rule. The valid retry
completed five model responses and fresh-container candidates, used 56,916 total
tokens and 478 seconds, and had no model request errors.

Candidate 1 installed the project and exposed the missing `pytest` verifier
dependency. Candidate 2 added `pytest`; collection then reached 893 tests before
`starlette.testclient` required an additional HTTP test dependency. Candidate 3
selected the broad `testoptional` extra, which pulled an old `pyarrow` into base
Python 3.13 and failed during wheel preparation. Candidates 4 and 5 stayed on that
branch, adding build tools and pinning `pyarrow==15.0.2`, but could not make the
incompatible source build installable. The episode stopped at the five-candidate
limit.

This is an algorithmic failure, not an infrastructure or evaluator result. The
initial repository observation admitted 14 runtime requirements from `pyproject.toml`
but did not expose the semantics of its optional dependency groups. Consequently,
the solver had enough freedom to act but insufficient structured evidence to prefer
the narrow `testcore` group that Repo2Run found by reading the declaration. Repeated
`pyarrow` build failures also remained package-install failures instead of becoming
a runtime compatibility conflict that would redirect search.

### Initial Three-Layer Diagnosis

**Observation layer:** a missing path can be a deployment observation even when no
file content must be generated. Test collection supplied stronger evidence than the
package graph alone. Build artifacts, dependency trees, and source edits must also
be observed as distinct path classes rather than inferred from file extensions.
Optional dependency groups and their verifier relevance are part of repository
evidence; flattening only base requirements loses a decisive choice boundary.

**Constraint layer:** environment state includes typed filesystem postconditions such
as `directory_exists(project-relative-path)`, not only runtimes, packages, imports,
and environment variables. Repeated native-build failures under a declared runtime
must be promotable from local command errors to a runtime-package compatibility
conflict.

**Operation layer:** creating a project-relative empty directory is a bounded,
effect-verifiable operation. Treating every filesystem mutation as an unrepresentable
shell escape unnecessarily censors successful strong-agent trajectories. Conversely,
a broad repository integrity scan must understand operation-produced artifact roots;
otherwise valid package-manager semantics become false tampering evidence.

### Candidate General Hypothesis

- **H10: typed filesystem postconditions.** Representing bounded project-relative
  directory creation with explicit path scope and effect verification should reduce
  wrapper-induced Unknown outcomes without permitting arbitrary source edits.
- **H11: provenance-scoped integrity.** Classifying untracked paths by the typed
  operation and generated root that produced them should preserve tracked-source
  protection while avoiding false positives from standard package-manager layouts.
- **H12: verifier-conditioned optional dependencies.** Preserving named optional
  dependency groups as structured repository evidence, then ranking them against the
  active verifier's missing imports, should avoid broad extras without hard-coding
  package or repository names.
- **H13: compatibility-conflict promotion.** Aggregating repeated build failures by
  package, runtime, and failure phase should let the constraint layer close an
  unproductive install branch and propose a compatible runtime or narrower
  dependency set.

### Anti-Overfitting Gate

No repair may special-case `marimo`, frontend assets, `_static`, or the observed path.
No repair may hard-code `testcore`, `testoptional`, `pyarrow`, or a Python version.
Any operation change must use a general filesystem intent, reject traversal and
protected paths, verify the resulting effect, pass repository-neutral fixtures, and
be frozen before an untouched case is opened. Dependency-group and compatibility
changes must be derived from declarations and execution evidence and validated on
synthetic repositories with different names.

### Evidence Anchors

- Repo2Run run ID: `pro-p0-v1-c03-repo2run-reproduced`
- Native usage: 8 responses, 77,503 total tokens, 377 seconds
- Native verifier: return code 0, 1,085 tests collected
- Preserved raw command trace: `generation/repo2run_raw/inner_commands.json`
- Raw command trace SHA-256:
  `a825ca90f8b4a38b24a6ccc762e50afc71ee3ede47dd64c63960a7a6b9ee6d71`
- Raw ReAct run ID: `pro-p0-v1-c03-envbench-raw-react`
- Raw ReAct usage: 20 responses, 344,440 total tokens, 561 seconds
- Raw ReAct integrity audit: 0 tracked changes, 7,865 generated-path violations
- Raw ReAct native trajectory SHA-256:
  `78af4405d3115f97c99cefba57cb93821e7d93230e75ec8131a7d6e48047f7f7`
- Frozen EnvSolve primary run ID: `pro-p0-v1-c03-envsolve-v1-frozen`
- Frozen EnvSolve infrastructure retry run ID:
  `pro-p0-v1-c03-envsolve-v1-frozen-network-retry3`
- Frozen EnvSolve retry usage: 5 responses/candidates, 56,916 total tokens,
  478 seconds, 0 request errors
- Frozen EnvSolve outcome: candidate budget exhausted; 5 verifier failures
- Scheduled Codex outcome: Unknown, exact preregistered executable unavailable
## Case P0-004: `strinking/futaba@2e4d787`

**Status:** all runnable scheduled methods have terminated. Frozen EnvSolve produced
an internally accepted deployment but failed the official static-analysis criterion.
Repo2Run reproduced succeeded in its native Python 3.10 container but replayed only
an ambient-state-dependent install command, which failed official bootstrap under
Python 3.13. Raw ReAct solved the native deployment but its successful trajectory was
rejected by the replay compiler. The scheduled Codex result is Unknown because the
exact preregistered executable remains unavailable.

### Why This Case Is Valuable

This case couples an old Poetry lock with a native extension that cannot build under
the benchmark image's Python 3.13. A successful deployment must select a compatible
runtime, ensure that the package manager actually owns an environment using that
runtime, install development dependencies needed by static analysis, and preserve
those causal choices in a fresh-container replay. Importability alone is not the
official success condition.

### Frozen EnvSolve Observation

Frozen EnvSolve used three model responses and fresh-container candidates, 28,582
total tokens, and 501 seconds without request errors. Candidate 1 used Poetry under
the default Python and failed while compiling `frozenlist==1.4.0`. Candidate 2
installed Python 3.10 but did not bind Poetry to it, so `poetry install` still created
a Python 3.13 environment and repeated the failure. Candidate 3 created a Python 3.10
venv explicitly and used `pip install .`; all 54 internal import obligations,
`pip check`, compileall, and source import closure passed.

The official bootstrap also completed, but EnvBench reported two scoring
missing-import diagnostics, so the run failed. Pyright emitted 746 total errors over
119 files; the other 744 argument, attribute, optional-member, and related type
errors were non-scoring diagnostics. This is a genuine EnvSolve failure because its
internal verifier missed two obligations in the official import-resolution target.

### Repo2Run Observation

Repo2Run used five responses, 32,055 total tokens, and 111 seconds without request
errors. Its native trajectory ran in a Python 3.10 container, where `poetry install`
succeeded. The replay distiller retained only that install command and reported no
integrity violation. In the official fresh container, the same command inherited
Python 3.13 and failed compiling `frozenlist==1.4.0`; Pyright never ran. The official
result was therefore bootstrap exit 1, not a static-analysis score.

The command was syntactically replayable but semantically incomplete. Its successful
effect depended on an ambient runtime that was visible in the native container and
absent from the compiled plan.

### Raw ReAct Observation

Raw ReAct used 13 responses, 96,776 total tokens, and 95 seconds with no request
errors. It inspected the Poetry declarations, diagnosed the Python 3.13 extension
failure, selected Python 3.10.13 through pyenv, recreated `.venv`, ran
`poetry install --with dev`, and verified the project plus its primary runtime and
development imports. The native trajectory completed successfully.

The replay compiler retained runtime configuration and environment activation but
rejected the compound command containing `rm -rf .venv`; it also rejected a later
observational command whose final probe used `|| true`. Because the package install
shared the first compound command, generation was marked non-replayable and no
official evaluator ran. Repository integrity remained valid with zero tracked changes
and no disallowed untracked paths. This is a wrapper-induced Unknown, not a native
agent failure.

### Initial Three-Layer Diagnosis

**Observation layer:** the same locked extension failing on Python 3.13 and installing
on Python 3.10 is direct runtime-package compatibility evidence. A successful command
also carries causal ambient facts, including the active interpreter and package-
manager environment. Official failure shows that runtime import probes and the
official static missing-import check are distinct observations.

**Constraint layer:** a replayable solution must be causally closed: runtime choice,
environment ownership, dependency groups, and verifier obligations cannot remain
implicit in the source container. Internal acceptance must cover the declared task
contract, not merely a weaker proxy such as importability.

**Operation layer:** runtime installation, package-manager interpreter binding,
project-scoped environment replacement, dependency installation, and static checking
are separate typed operations. A bounded reset of a known generated environment root
is not equivalent to arbitrary destructive shell access. Compound commands should be
decomposed so that one unsupported observation does not erase an independent
successful install effect.

### Candidate General Hypotheses

- **H14: verifier-contract closure.** Deriving internal obligations from the official
  missing-import contract and running an independent local checker of the same
  semantic family should reduce false internal acceptance without exposing
  post-episode evaluator results to the solver.
- **H15: causal replay closure.** Recording the runtime, environment owner, and other
  ambient preconditions that made a successful action work should prevent syntactic
  replay from changing semantics in a fresh base container.
- **H16: typed environment replacement.** A project-scoped operation that replaces a
  recognized generated environment and binds it to a selected runtime should preserve
  strong-agent recovery behavior while rejecting arbitrary deletion.
- **H17: effect-level compound decomposition.** Distilling independently successful
  effects from compound shell expressions should keep a valid deployment action when
  an adjacent cleanup or observation is unsupported.

### Anti-Overfitting Gate

No repair may mention `futaba`, `frozenlist`, Poetry-specific package names, or the
observed version numbers. Runtime constraints must arise from declarations and
execution evidence. Environment replacement must be limited to typed generated roots
with path-scope validation. Verifier changes must be declared before the next
untouched case and evaluated on repository-neutral fixtures that separate runtime
import success from the official static missing-import result.

### Evidence Anchors

- Frozen EnvSolve run ID: `pro-p0-v1-c04-envsolve-v1-frozen`
- Frozen EnvSolve usage: 3 responses/candidates, 28,582 total tokens, 501 seconds
- Frozen EnvSolve internal outcome: candidate 3 accepted; 54 obligations satisfied
- Frozen EnvSolve official outcome: bootstrap 0, `issues_count=2`, failed; 746 total
  Pyright errors were recorded as non-scoring diagnostics
- Repo2Run run ID: `pro-p0-v1-c04-repo2run-reproduced`
- Repo2Run usage: 5 responses, 32,055 total tokens, 111 seconds
- Repo2Run official outcome: bootstrap 1; `frozenlist==1.4.0` failed under Python 3.13
- Repo2Run trajectory SHA-256:
  `071f085f73813c8acbc091700aa0484758d0ca572fd4d4fc6f4889f0d59ea903`
- Raw ReAct run ID: `pro-p0-v1-c04-envbench-raw-react`
- Raw ReAct usage: 13 responses, 96,776 total tokens, 95 seconds
- Raw ReAct native trajectory SHA-256:
  `a0dbe3f26f2d6802670126f3626099c54458782a6a99eceeff6792f03a54968c`
- Raw ReAct integrity: valid; zero tracked changes and zero disallowed untracked paths
- Scheduled Codex outcome: Unknown, exact preregistered executable unavailable


## Case P0-006: `r-anime/holo@7864bc6`

**Status:** all three cross-method census runs reached the official evaluator.
EnvSolve-pro causal v3 and Codex CLI passed; Repo2Run reproduced failed with five
missing-import issues. Total Pyright errors remain non-scoring.

### Why This Case Is Valuable

This is a compact positive control for the observation-to-action path. The repository
has a plain requirements file and additional source imports. A method can read both
without actually making the resulting dependency obligations true in its final
program, so the case separates evidence acquisition from evidence use.

### Cross-Method Observation

| Method | Native behavior | Official outcome |
|---|---|---|
| EnvSolve-pro causal v3 | Used four fresh candidates and four model responses. The accepted strict script installed the declared requirements plus dependencies exposed by executable verification. | Pass, `issues_count=0`; 28,657 total model tokens and 408 seconds end to end. |
| Codex CLI | Read requirements and source imports, installed the declaration plus one missing GUI dependency, then imported every source module before finalizing a two-line program. | Pass, `issues_count=0`; 13 container commands, 236,969 input tokens, and 156 seconds. |
| Repo2Run reproduced | Read the requirements file, source tree, and Python files, but emitted only runtime selection and read-only inspection commands. | Fail, `issues_count=5`; 25,662 total model tokens and 79 seconds. |

### Three-Layer Diagnosis

**Observation layer:** repository declarations and source-import probes are both
useful. Codex actively checked all source modules; EnvSolve accumulated executable
feedback across fresh environments. Repo2Run also read the relevant files, so this
case is not explained by file visibility alone.

**Constraint layer:** observed declarations must become unresolved obligations until
the accepted environment proves them satisfied. Repo2Run's final program demonstrates
the counterexample: relevant evidence was present in the trajectory but had no
binding effect on the emitted deployment.

**Operation layer:** both passing methods emitted small replayable programs whose
effects survived fresh official execution. EnvSolve's strict script also prevented a
failed install from being mistaken for success.

### Candidate General Hypotheses

- **H19: evidence-to-action entailment.** Requiring every admitted high-confidence
  declaration to be satisfied or explicitly discharged before finalization should
  reduce trajectories that inspect the right evidence but emit a no-op deployment.
- **H20: frontier-guided active observation.** Giving a strong model read-only
  repository and import probes selected by the unresolved constraint frontier should
  retain Codex-like discovery while keeping observations typed and auditable.

### Anti-Overfitting Gate

No repair may mention this repository or any package observed in it. H19 must be
tested with synthetic declarations whose package names and file layouts differ from
this case. H20 must compare a fixed profile, unconstrained exploration, and
frontier-guided read-only queries on already consumed repositories before any
untouched evaluation.

### Evidence Anchors

- EnvSolve-pro run ID: `pro-cross-method-v1-c05-envsolve-pro-causal-v3`
- Codex run ID: `pro-cross-method-v1-c05-codex-cli-native`
- Repo2Run run ID: `pro-cross-method-v1-c05-repo2run-reproduced-open`
- Frozen success criterion: bootstrap exit 0 and `issues_count=0`


## Case P0-005: `python/importlib_metadata@f390168`

**Status:** all runnable scheduled methods have terminated. Frozen EnvSolve converged
to an internally accepted deployment in three fresh candidates, but official
bootstrap failed because the evaluator added a top-level artifact directory before
the editable install. Repo2Run installed the test extra but failed its native
verifier. Raw ReAct passed the native tests and Mypy, after which the replay compiler
rejected unrelated observational commands. The scheduled Codex result is Unknown
because the exact preregistered executable remains unavailable.

### Why This Case Is Valuable

This case is a compact test of feedback precision and workspace-state equivalence.
The base declaration exposes only one runtime dependency, while test collection
reveals an additional import obligation. Separately, a verifier-owned output
directory changes setuptools flat-layout package discovery even though the repository
revision and deployment script are unchanged.

### Frozen EnvSolve Observation

Frozen EnvSolve used three model responses and fresh-container candidates, 19,607
total tokens, and 257 seconds with no request errors. Candidate 1 installed only the
observed `zipp` requirement and failed because pytest was absent. Candidate 2 installed
the repository's `.[test]` extra; fixed checks completed, and the structured verifier
reduced the remaining state to one unresolved module, `importlib_resources`.
Candidate 3 preserved the test extra, added that package, and satisfied all 38 active
obligations. This is a clean positive example of executable feedback becoming a
specific constraint and improving the next complete plan in a fresh container.

The official bootstrap nevertheless failed before Pyright. EnvBench created
`build_output/` at repository root before running the generated script. During
`pip install -e ".[test]"`, setuptools automatic flat-layout discovery then saw both
`build_output` and `importlib_metadata` as top-level packages and refused to build.
The internal verifier had run against a clean checkout without this verifier-owned
precondition, so its acceptance environment was not equivalent to official execution.

### Repo2Run Observation

Repo2Run used six responses, 46,068 total tokens, and 350 seconds without request
errors. Its only deployment action was `pip install -q -e ".[test]"`, which succeeded
after 235 seconds. The subsequent native `runtest` returned 2, as it had before the
install, and Repo2Run terminated with process exit 1. It did not convert that second
collection failure into a new dependency constraint, so generation never reached
replay or official evaluation.

### Raw ReAct Observation

Raw ReAct used 16 responses, 129,602 total tokens, and 186 seconds without request
errors. It installed the project and its test extra, then ran the suite: 139 tests
passed, one was skipped, coverage reached 96 percent, and Mypy reported no issues.
The native deployment was successful.

The replay compiler correctly retained the two package-install actions but rejected
three parent-directory exploration commands and two successful `python -c`
observations. Those observations were not causal prerequisites for the retained
install effects, yet their presence made the entire generation non-replayable. No
official evaluator ran. Repository integrity remained valid with zero tracked
changes and no disallowed untracked paths. This independently reproduces P0-004's
effect-level decomposition problem.

### Initial Three-Layer Diagnosis

**Observation layer:** verifier-owned workspace artifacts are part of execution state
when they can affect build-system discovery. A collection failure can also expose a
single missing module after declared dependency installation, providing a much
smaller counterexample than the raw test log.

**Constraint layer:** internal acceptance is meaningful only when its initial
workspace state is equivalent to the eventual verification state, excluding the
verifier result itself. Non-causal unsupported observations must not invalidate an
otherwise closed deployment plan.

**Operation layer:** the benchmark adapter should reproduce declared verifier
preconditions before internal execution, or arrange evaluator artifacts after
bootstrap when the benchmark permits it. The replay compiler should preserve typed
install effects independently from read-only exploration and executable probes.

### Candidate General Hypothesis

- **H18: verifier-precondition parity.** Materializing verifier-owned paths and other
  declared workspace preconditions in internal fresh environments should reduce
  false acceptance caused by clean-checkout versus evaluation-workspace differences,
  without exposing post-episode evaluator outcomes.

P0-005 also provides independent support for H17: successful deployment effects
should survive unsupported, non-causal observations elsewhere in the trajectory.

### Anti-Overfitting Gate

No repair may mention `importlib_metadata`, `build_output`, setuptools flat-layout,
or the observed missing module. Verifier preconditions must come from a benchmark
adapter contract and be tested with synthetic artifact names and multiple build
backends. Replay changes must prove causal independence before dropping unsupported
commands and must still reject unsupported commands whose effects feed deployment.

### Evidence Anchors

- Frozen EnvSolve run ID: `pro-p0-v1-c05-envsolve-v1-frozen`
- Frozen EnvSolve usage: 3 responses/candidates, 19,607 total tokens, 257 seconds
- Frozen EnvSolve internal outcome: candidate 3 accepted; 38 obligations satisfied
- Frozen EnvSolve official outcome: bootstrap 1; Pyright not run
- Repo2Run run ID: `pro-p0-v1-c05-repo2run-reproduced`
- Repo2Run usage: 6 responses, 46,068 total tokens, 350 seconds
- Preserved Repo2Run commands: `generation/repo2run_raw/inner_commands.json`
- Repo2Run command trace SHA-256:
  `540962a7383fbc1208606456e361063611998c9a211491bd21df10c9d59499a8`
- Raw ReAct run ID: `pro-p0-v1-c05-envbench-raw-react`
- Raw ReAct usage: 16 responses, 129,602 total tokens, 186 seconds
- Raw ReAct native result: 139 passed, 1 skipped, 96 percent coverage, Mypy clean
- Raw ReAct trajectory SHA-256:
  `e7daafbe3af9b06348eea6a9ac666ccd506deed05e001402579a7b61fd70bf6a`
- Raw ReAct integrity: valid; zero tracked changes and zero disallowed untracked paths
- Scheduled Codex outcome: Unknown, exact preregistered executable unavailable
