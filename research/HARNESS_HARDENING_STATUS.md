# Harness Hardening Status

## Purpose

This checklist tracks infrastructure correctness work required before the
harness is frozen. Fixes are justified by method-independent invariants and
synthetic tests, not by improving outcomes on Dev-5.

## Resolved

### Cancellation and cleanup

- Every `run_case.py` process starts in an independent process group.
- `SIGINT` and `SIGTERM` stop active process groups and cancel queued futures.
- Containers are attributed by host mounts under the case artifact root; only
  matching containers are force-removed.
- Cleanup repeats briefly to cover Docker daemon creation races.
- Active artifacts transition atomically to `interrupted`, preserving the
  previous state, signal reason, process exit code, and removed container IDs.
- Queued cases are recorded as `not_started` without creating misleading run
  artifacts.
- Batch summaries are written even after interruption and use the configured
  runs root rather than a hard-coded workspace path.
- Interrupted artifacts are accepted by the audit protocol only when reason,
  timestamp, and cleanup evidence are present.

Validation:

- Synthetic process-group, container-ownership, and audit tests pass.
- A real Ctrl-C smoke exited 130 with one interrupted and four not-started
  cases; its active artifact audited successfully.
- A real SIGTERM smoke exited 143 with the same lifecycle behavior.
- Both smokes left no case-mounted Docker container or child process.

### Typed replay IR prototype

- Replayable shell state is represented as typed package-install,
  system-package, package-index, runtime, export, and activation actions.
- Project working directories are validated and represented as action context.
- Logging-only pipelines are removed from mutations so their true exit status
  is preserved.
- Unknown commands, unsafe pipelines, fallback operators, external absolute
  working directories, and unbalanced shell syntax fail closed.
- Synthetic tests cover path mapping, typed action extraction, dry runs,
  observations, unsafe pipelines, fallback operators, and logging filters.

A read-only compatibility audit was performed only after these rules were
defined. Two of five recorded Dev-5 trajectories are fully accepted; three are
rejected for one unsupported command each. No rule was added after observing
those trajectories. The compatibility decision therefore remains a freeze
blocker rather than being tuned against Dev-5.

### Deadlines and resource-budget provenance

- The run manifest records generation wall clock, model-request timeout,
  provider retry count, per-request output-token ceiling, agent iteration cap,
  shell-command timeout, Git fetch timeout, evaluator-process deadline, Docker
  creation timeout, and Docker execution timeout.
- EnvBench model limits are passed explicitly through Hydra to `ChatOpenAI`.
  A configuration-only dry run verified the resolved values without making a
  provider request.
- GitHub revision fetches use exact shallow-SHA fetches with a hard subprocess
  deadline. Hugging Face fallback remains bounded by the evaluator-process
  deadline.
- The evaluator has an outer hard deadline in addition to EnvBench's internal
  Docker limits. Generation and evaluation deadline exhaustion are recorded as
  `budget_exhausted` with scope, limit, timestamp, and case-owned container
  cleanup evidence.
- Configuration rejects non-positive limits and negative retry counts.
- Synthetic tests cover configuration provenance, generation deadline
  exhaustion, evaluation deadline exhaustion, partial-log preservation, and
  case-owned container cleanup.

Current local defaults are 7,200 seconds generation wall clock, 180 seconds per
model request, two provider retries, 16,384 output tokens per request, 30 agent
iterations, 900 seconds per shell command, 300 seconds per Git fetch, 1,800
seconds for the evaluator process, 180 seconds for container creation, and 900
seconds for container execution. These are protocol parameters, not values
selected from Dev-5 outcomes.

### Online cumulative model budget

- A benchmark-independent atomically persisted ledger enforces logical model-request,
  cumulative input/output-token, and normalized estimated-cost limits.
- Limits are checked before every model call; response usage is atomically
  recorded before another call can begin.
- Input, output, and cache-read prices are frozen by model with source URL and
  snapshot date. Unknown model pricing fails before a provider request.
- EnvBench LangChain and Repo2Run OpenAI clients use thin bridges to the same
  ledger. Provider retries and request deadlines remain explicit parameters.
- Solver metadata, `generation/budget_ledger.json`, manifest limits, and pricing
  must agree for independent audit to pass.
- Synthetic tests cover request, cumulative-token, cache-aware cost, persisted
  termination, and environment bridge semantics. Fake-model smokes verified the
  LangChain and Repo2Run bridges without network requests.

The current per-case defaults are 30 logical model requests, 1,000,000 total
tokens, and USD 5 normalized estimated cost. DeepSeek V4 Pro pricing is frozen
from the OpenRouter model page as of 2026-07-13. These administrative limits
were not selected from Dev-5 outcomes.

### Benchmark decoupling

- Benchmark roots and settings are opaque `BenchmarkConfig` entries rather
  than EnvBench fields in `HarnessConfig`.
- Benchmark and solver factories are selected through independent registries.
- Core evaluation results contain generic evidence and raw metrics; EnvBench
  exit, issue, and Pyright metrics stay inside the EnvBench adapter.
- Official criteria are generic metric predicates and are independently
  recomputed by audit.
- Core audit consumes runner-declared capabilities rather than runner names.
- A synthetic adapter test confirms that a benchmark can be added without
  modifying core or the experiment CLI.

### Repository integrity gate

- EnvBench and Repo2Run generation repositories must remain at the exact frozen
  revision with no tracked-file changes.
- Both ordinary untracked files and files hidden by `.gitignore` are inspected.
  New source/import artifacts, `.pth` files, dependency or verifier
  configuration, symlinks, and other repository outputs fail closed.
- Only standard installation outputs under virtual-environment, build, cache,
  coverage, and egg-info locations are allowlisted. Safety also depends on the
  typed replay gate: arbitrary file-writing commands are never replayable.
- Environment exports reject Python, mypy, pyright, dynamic-loader, current
  directory, and project-root path injection. Activation is restricted to
  standard `.venv`/`venv` scripts or Poetry's resolved environment.
- Repo2Run now passes successful commands through the same typed replay IR;
  arbitrary successful shell mutations are unsupported.
- Successful model-generated runs carry a machine-readable integrity report.
  Independent artifact audit rejects a missing or failed report.

Synthetic Git repositories cover tracked changes, ignored fake modules,
untracked import artifacts and verifier configuration, symlinks, allowlisted
virtual-environment outputs, path injection, arbitrary activation, and audit
tampering. These rules were defined without inspecting additional benchmark
trajectories.

### Typed Replay IR v4 freeze

The replay policy is frozen as `typed-replay-ir-v4`. Its shell semantics,
23-case machine-readable synthetic corpus, implementation, and corpus test are
content-addressed in `experiments/protocols/typed_replay_ir_v4_freeze.json`.
The full 38-test harness suite, compile check, explicit safety matrix, and
recorded-redistillation integration test pass.

V4 proves compound observations safe before dropping them, extracts only typed
mutations from successful `&&` chains, and rejects ambiguous mutation branches
under fallback, semicolon, multiline, pipeline, or nested-shell control flow.
It also rejects output writes, mutating `find`, arbitrary Python snippets,
command/process substitution, dangerous exports, and mutation-capable `xargs`.

The development disclosure is explicit: v3 failures in development trajectories
motivated the semantic revision, so Dev-5 and Dev-Extension-3 are development
only. No repository identifiers or case-specific rules occur in the grammar or
corpus. Canary-20 and Official-Test-100 remain untouched confirmatory splits.

### Official and non-scoring Diagnostic channels

- Every completed artifact contains exactly one `official` evidence record;
  audit independently recomputes its pass value from the frozen generic
  protocol predicates.
- EnvBench bootstrap and full Pyright output are preserved as two `diagnostic`
  evidence records. Their pass values, severity/rule counts, missing modules,
  and non-missing-import errors cannot affect Official Pass.
- Incomplete evaluation is represented as `passed=null`, rather than conflated
  with either verifier success or failure.
- Synthetic integration tests prove that diagnostic outcomes cannot change the
  official score and that audit accepts the generic evidence schema.

The adapter was also exercised on the frozen replayable development case. One
execution failed before evaluation after Git fetch exit 128 and Hugging Face
fallback 401; a second completed with bootstrap exit 1 after a transient Rust
toolchain download timeout, so Pyright remained unknown. The earlier recorded
execution completed bootstrap and Pyright and retained its false official
result. All artifacts are preserved, and no retry-until-success result was
selected.

### Machine-readable Harness Freeze Manifest

`experiments/protocols/harness_freeze_v2.json` freezes the complete P0 contract:

- 60 harness, experiment, test, script, replay-policy, and historical-freeze
  files;
- 11 source, intermediate, development, and confirmatory case files, including
  untouched Canary-20 and Official-Test-100;
- configuration, model pricing, resource budgets, protocol predicates,
  Official/Diagnostic channel semantics, and runner/adapter registries;
- 129 EnvBench and 48 Repo2Run Git-worktree entries, including ordinary file
  hashes, tracked deletions, and symbolic-link targets; both Git revisions and
  dirty-status records; and the exact evaluation image ID and registry digest;
- the nested Typed Replay IR v4 freeze and its content-addressed files.

`experiments/tools/harness_freeze.py --verify` independently returns
`valid=true`. Negative checks reject modified budgets, official-channel
semantics, dataset hashes, and runner registries. The 44-test harness suite and
compile check pass at freeze time.

V2 preserves V1 by exact hash and supersedes it for one disclosed non-scoring
reporting correction. A preregistered post-freeze Dev-3 run showed that
bootstrap failures were labeled `verification` in the derived batch summary,
despite correct raw and diagnostic evidence. The summary now consumes the
bootstrap diagnostic, with an exit-code fallback for historical artifacts.
Official scoring, run artifacts, adapter behavior, and replay policy are
unchanged.

### Post-freeze Dev-3 validation

Three identities were selected outcome-blind from Train-Untouched-201 by a
salted SHA256 rule and written to
`experiments/validations/p0_post_freeze_dev3_preregistration.json` before any
execution. Each received exactly one deterministic attempt.

- Generation, evaluation completion, and independent artifact audit: `3/3`.
- Process failures, interruptions, and not-started cases: `0`.
- Bootstrap completion, Pyright completion, and Official Pass: `0/3`.
- Two bootstraps hit PyPI read timeouts; one isolated ConfigSpace build could
  not resolve `setuptools`. One repository also required the preregistered
  Hugging Face fallback after exact Git fetch exit 128.

No model call or rerun occurred. `issues_count=0` is not interpreted as verifier
success because Pyright did not run. The three identities are development
consumed and excluded from future confirmatory analysis; Canary-20 and
Official-Test-100 remain uninspected.

An explicit user-requested retry was subsequently registered as a separate
reliability run and did not replace the first attempts. All three initial
network/index failures disappeared under unchanged configuration. `phobos`
completed bootstrap and reached Pyright, while `neps` exposed its Python
`<3.12` constraint and `helios-server` exposed the missing `pg_config` system
dependency. Official Pass remained `0/3`. This confirms that online fetch
failures can mask the actual environment constraint and must be modeled
separately from solver and verifier outcomes.

## Freeze status

P0 v2 is frozen. Future changes to a frozen behavioral surface require a new
manifest version and disclosure; ordinary solver work proceeds above this
unchanged evaluation layer.
