# P1 Baseline Protocol and Initial Results

## Dataset freeze

The Python study uses the 329 cases in
`JetBrains-Research/EnvBench:splits/python_baseline_failure.jsonl` at dataset
revision `d1e96e6b10335cad40ac7b4f709f46a2c579765a`.

The unchanged official 100-case test file is held out. The official train file
contains two concatenated JSON objects at line 72, so the 229-case train set is
reconstructed as all 329 cases minus the official test identities. Exact source
hashes, selection rules, and counts are recorded in
`experiments/cases/split_manifest.json`.

Dev-5 is selected from official train using environment categories rather than
outcomes:

| Repository | Category |
| --- | --- |
| `jaraco/inflect` | Conventional pure-Python metadata |
| `python-poetry/poetry` | Package manager and version constraints |
| `convexengineering/gpkit` | System or native dependency surface |
| `pytest-dev/pytest-xdist` | Test and development dependencies |
| `markqvist/reticulum` | Platform-specific optional dependencies |

Canary-20 is an outcome-blind SHA256-ranked sample from the remaining official
train cases, using the frozen salt in the split manifest.

Dev-Extension-3 was frozen after the harness-decoupling milestone and before
its first execution. It is an outcome-blind SHA256-ranked sample from
Train-Rest-204 using a separate frozen salt. The selected cases are excluded
from the remaining 201-case untouched pool. Canary-20 and Official-Test-100 are
unchanged and remain unobserved.

## Baseline contract

Every baseline must produce a replayable bootstrap script. The same unchanged
EnvBench official protocol then evaluates that script. A process exit of zero
means the evaluator completed; it does not imply benchmark success.

Failure stages are defined as:

- `generation`: the solver did not produce an admissible replayable script;
- `evaluator`: EnvBench did not produce a matching result record;
- `bootstrap`: the script failed before static verification completed;
- `verification`: the script ran, but official missing-import checks failed;
- `success`: the official protocol passed.

## Deterministic baseline v1

Run: `runs/dev5-deterministic-batch-v1`

| Repository | Bootstrap exit | Missing imports | Official pass | Failure stage |
| --- | ---: | ---: | --- | --- |
| `jaraco/inflect` | 1 | 0 | No | Bootstrap |
| `python-poetry/poetry` | 1 | 0 | No | Bootstrap |
| `convexengineering/gpkit` | 0 | 77 | No | Verification |
| `pytest-dev/pytest-xdist` | 0 | 1 | No | Verification |
| `markqvist/reticulum` | 0 | 18 | No | Verification |

Aggregate Official Pass@1: `0/5`.

The `inflect` failure reveals evaluator interference: EnvBench creates a
`build_output/` directory before editable installation, and setuptools then
detects it as a second top-level package in a flat layout. This behavior remains
unchanged for official-score comparability and will be studied separately under
benchmark fidelity. The Poetry failure was a package download timeout and is
retained as a bootstrap failure rather than silently retried.

## Repo2Run adapter

The adapter invokes Repo2Run at its pinned local revision and records its dirty
state. Infrastructure compatibility changes ensure the exact requested commit
is fetched, checked out, and verified before `pipreqs` or agent execution.

The trajectory distiller:

- keeps only successful state-changing commands;
- removes observations, internal tools, and validation commands;
- resets prior actions when Repo2Run changes the Python base image;
- maps Repo2Run's `/repo` paths to the evaluator project root;
- rejects unsupported base-image changes;
- rejects runs that modify tracked or untracked application source files;
- never records API key values.

The missing-credential path is implemented and auditable. A real Repo2Run run
requires `OPENAI_API_KEY` and `OPENAI_BASE_URL` to be injected into the process
environment; neither belongs in a config, command argument, or artifact.

## EnvBench ReAct / FreeAgent adapter

The EnvBench Python ReAct agent now runs through the same solver interface as
Repo2Run and the deterministic baseline. It receives only the frozen repository
identity and does not receive evaluator output or implementation details.

The adapter records the model, seed, 30-step action budget, command timeout,
global timeout, EnvBench revision and dirty state, exact checkout, complete
JSONL trajectory, model request count, token usage, and the final replayable
script. Provider credentials are inherited from the process environment; only
their presence is recorded. Logs are redacted before being written.

The trajectory policy removes failed commands, pure observations, import smoke
checks, and tests. It retains successful typed environment mutations and fails
closed when a successful command contains an unclassified shell segment. Runs
are rejected if the generation repository is absent, has the wrong revision,
or contains modified application source files.

The existing Reticulum trajectory provides a deterministic parser smoke test:
18 successful commands are reduced to one replayable state change,
`pip install -e .`; 17 observation or validation commands are removed. Its 13
model requests and 126,038 total reported tokens are recovered from trajectory
metadata. This is a parser validation, not a new benchmark score.

## DeepSeek V4 Pro FreeAgent Dev-5

Final run: `runs/dev5-envbench-agent-deepseek-v4-pro-v2`

Model: `deepseek/deepseek-v4-pro` through OpenRouter, seed 0, temperature 0,
30-step action budget. Provider credentials were injected into an ephemeral
shell environment and removed after generation; no credential pattern appears
in the run artifacts.

| Repository | Exit | Missing imports | Pass | Requests | Tokens | Stage |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| `jaraco/inflect` | 1 | 0 | No | 9 | 76,457 | Bootstrap |
| `python-poetry/poetry` | 0 | 15 | No | 23 | 276,276 | Verification |
| `convexengineering/gpkit` | 0 | 12 | No | 11 | 75,816 | Verification |
| `pytest-dev/pytest-xdist` | 0 | 0 | Yes | 12 | 102,679 | Success |
| `markqvist/reticulum` | 0 | 18 | No | 11 | 97,670 | Verification |

Aggregate Official Pass@1 is `1/5`, compared with `0/5` for the deterministic
baseline. Across 66 model requests, trajectories report 613,291 input tokens,
15,607 output tokens, and 628,898 total tokens. Distillation retained 14 action
records, removed 69 failed/observation/validation records, and surfaced one
unclassified successful command.

On cases where both bootstraps completed, missing imports changed from 77 to 12
for GPkit, 1 to 0 for pytest-xdist, and remained 18 for Reticulum. Poetry moved
from a deterministic bootstrap failure to a completed verification with 15
missing imports. Inflect remains a bootstrap failure because EnvBench creates
`build_output/` before editable installation.

The superseded `v1` pilot must not be reported as a model result. It exposed an
adapter error: commands containing the generation path
`/data/project/<repository@revision>` were replayed unchanged even though the
evaluator project root is `/data/project`. Distillation v2 maps that path to the
fresh project root, removes package-manager probes and dry runs, preserves venv
activation, and was regression tested. The first two paid trajectories were
integrity-checked and re-distilled rather than queried again; the remaining
three were generated live under the same model configuration.

EnvBench's downloader also performed unbounded full-history Git clones. It now
fetches the exact requested commit at depth one, checks out detached HEAD, and
verifies the SHA before evaluation. This changes download mechanics, not the
repository contents or scoring protocol, and its dirty state is recorded.

## DeepSeek V4 Pro FreeAgent Dev-Extension-3

Run: `runs/dev-extension3-envbench-agent-deepseek-v4-pro-v1`

The three identities were selected and recorded by the outcome-blind frozen
hash rule before execution. The run uses the same model, seed, action budget,
timeouts, integrity policy, and official protocol as the Dev-5 baseline.

| Repository | Requests | Tokens | Estimated cost | Stage | Cause |
| --- | ---: | ---: | ---: | --- | --- |
| `idaholab/civet` | 27 | 510,752 | $0.02136 | Generation | Tracked source mutation and untracked repository log |
| `scylladb/sphinx-scylladb-theme` | 14 | 145,173 | $0.02252 | Generation | Unsupported compound read-only probes in replay IR |
| `jmetal/jmetalpy` | 19 | 162,789 | $0.01769 | Generation | Unsupported compound and nested shell segments in replay IR |

All 60 model requests completed with zero provider errors. Total usage is
802,570 input tokens, 16,144 output tokens, and 818,714 tokens; 699,136 input
tokens were reported as cache reads. Frozen-price normalized estimated cost is
$0.06157. All three artifact audits pass.

Generation completed for `0/3`, so the official evaluator was not invoked and
this run must not be interpreted as an Official Pass@1 measurement. One case
was correctly rejected by the preregistered repository-integrity policy. The
other two exposed the already registered typed replay IR compatibility blocker.
These cases are development-only: their v3 failures motivated a generalized
shell-semantics revision, so they cannot be used as confirmatory evidence.
Typed Replay IR v4 contains no repository-specific rules and was frozen with a
synthetic safety corpus before recorded re-distillation and evaluation.

This run also exposed a resource-accounting defect: early generation failures
were omitted from batch token totals even though their online ledgers were
complete. The summary now prefers audited online-budget usage and falls back to
legacy trajectory usage only for historical artifacts. This changes reporting,
not generation, evaluation, or pass/fail outcomes.

## Typed Replay IR v4 recorded replay

Policy freeze: `experiments/protocols/typed_replay_ir_v4_freeze.json`

V4 is specified independently of EnvBench metric names and frozen with 23
synthetic commands covering accepted typed actions, proven observations, and
fail-closed safety counterexamples. The freeze records exact hashes for the
specification, corpus, implementation, and corpus test. The full 38-test suite
passes.

After freeze, read-only compatibility analysis produced:

| Repository | V4 disposition | Reason |
| --- | --- | --- |
| `idaholab/civet` | Ineligible | Source integrity failed in the original run |
| `jmetal/jmetalpy` | Rejected | One multiline Python program is not a provably read-only probe |
| `scylladb/sphinx-scylladb-theme` | Replayable | Two typed actions, zero unsupported commands |

The replayable case was evaluated without another model request in
`runs/dev-extension3-recorded-ir-v4-v1`. V4 reduced the trajectory to:

```bash
poetry install
source $(poetry env info --path)/bin/activate
```

Fresh-container bootstrap completed in 191.48 seconds and the independent run
audit passed. Official Pass is false: `exit_code=0`, `issues_count=1`, six
Pyright errors, and two warnings. The single official environment issue is the
unresolved `recommonmark.transform` import. The other errors concern private
imports and source-level type diagnostics, illustrating why raw verifier
diagnostics must be preserved separately from the unchanged official score.
No solver or replay rule was changed after observing this result.

## Official and Diagnostic channel validation

The EnvBench adapter now emits one scoring `official` record plus two
non-scoring `diagnostic` records for bootstrap and full Pyright behavior. Audit
requires exactly one official record and recomputes it from the unchanged
protocol. Diagnostic severity, rule, module, and non-missing-import counts are
preserved for benchmark-fidelity analysis but cannot alter Official Pass.

Two additional executions of the same frozen replayable development case test
failure representation rather than solver quality:

| Run | Evaluator | Bootstrap diagnostic | Pyright diagnostic | Official |
| --- | --- | --- | --- | --- |
| `dev-extension3-official-diagnostic-v1` | Incomplete: Git fetch 128, then HF fallback 401 | Unknown | Unknown | Unknown |
| `dev-extension3-official-diagnostic-v2` | Completed | Failed: Rust toolchain download timeout | Unknown | Fail |

Together with `dev-extension3-recorded-ir-v4-v1`, which completed bootstrap and
Pyright but failed on one official missing-import issue, these executions expose
infrastructure and bootstrap nondeterminism without relabeling either as solver
failure or success. Both adverse reruns are retained. We stopped after the
pre-existing complete run plus these two validation runs rather than retrying
until a favorable outcome.

## P0 harness freeze

The current machine-readable freeze is
`experiments/protocols/harness_freeze_v2.json`. It content-addresses harness
source, all split files, the protocol and resource budget, model pricing,
Official/Diagnostic channel contracts, registries, Typed Replay IR v4,
EnvBench and Repo2Run source surfaces, Git revisions, and the evaluator image.
The verifier rejects source/file-set changes and contract tampering. At freeze
time, all 44 unit tests and compilation pass, and the manifest independently
verifies as valid.

V2 supersedes the exact preserved V1 hash only to correct non-scoring batch
failure-stage classification. Official criteria, adapter results, and replay
policy did not change.

## P0 post-freeze Dev-3 validation

Preregistration:
`experiments/validations/p0_post_freeze_dev3_preregistration.json`.
Results: `experiments/validations/p0_post_freeze_dev3_results.json`.

An outcome-blind salted SHA256 ranking selected three cases from
Train-Untouched-201 before execution. All three deterministic first attempts
completed generation, evaluation, lifecycle recording, Official/Diagnostic
evidence, and independent audit. All three bootstraps failed before Pyright:
two PyPI read timeouts and one isolated ConfigSpace build dependency-resolution
failure. Official Pass is therefore `0/3`, but this is not a solver comparison.
No rerun or model request was made.

The run exposed one derived-report bug: `summary.json` initially called these
failures `verification` despite failed bootstrap diagnostics. The general
classifier and a six-transition synthetic test now enforce the frozen stage
contract. Re-summarization changes only the derived stage label. Raw results,
Official Pass, diagnostic evidence, and first-attempt artifacts are unchanged.

### Explicit retry reliability result

At the user's request, the same three cases were run once more under unchanged
configuration as `p0-post-freeze-dev3-deterministic-v2`. The retry is reported
separately and does not replace the preregistered first attempts or contribute
to Official Pass@1.

| Repository | First attempt | Retry | Retry Official |
| --- | --- | --- | --- |
| `dfki-ric/phobos` | PyPI timeout | Bootstrap passed; Pyright found 100 official issues | Fail |
| `automl/neps` | Build-index failure | Python 3.13.2 violates project `<3.12` constraint | Fail |
| `benadida/helios-server` | PyPI timeout | psycopg2 build lacks `pg_config` | Fail |

Thus all three first-attempt network/index failures disappeared, but Official
Pass remained `0/3`. Network nondeterminism had masked three deeper environment
states rather than changing solver behavior. The retry made no model request,
and Canary-20 and Official-Test-100 remained uninspected.
