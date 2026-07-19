# EnvSolve experiments

The experiment harness is independent of any solving method. External systems
such as EnvBench, Repo2Run, and Codex are connected through adapters, while all
runs use the same case, artifact, provenance, and result schemas.

Benchmarks and solvers are separate plugin registries. The core result contains
generic official/diagnostic evidence and benchmark-owned `raw_metrics`; EnvBench
metric names are not part of the core schema. The dependency rules and extension
contracts are documented in `research/HARNESS_ARCHITECTURE.md`.

Generate and evaluate one case with the official deterministic baseline:

```bash
python3 experiments/run_case.py \
  --case-file experiments/cases/dev5.jsonl \
  --case-id envbench-python-markqvist__reticulum@6ded42edd7ae203e5a565cb70138c2d7b4b58b5b \
  --run-id dev5-deterministic-v1
```

Run a frozen split as a batch:

```bash
python3 experiments/run_batch.py \
  --case-file experiments/cases/dev5.jsonl \
  --run-id dev5-deterministic-v1 \
  --runner deterministic \
  --max-workers 2
```

`dev_extension3.jsonl` is a separately frozen, outcome-blind development
extension selected before execution. Its identities, salt, source hashes, and
exclusion from `train_untouched201.jsonl` are recorded in
`experiments/cases/split_manifest.json`. It does not consume Canary-20 or the
official test split.

Run the EnvBench Python ReAct/FreeAgent baseline with an OpenAI-compatible
provider. Credentials are inherited by the child process and are never passed
as CLI arguments or written to artifacts:

```bash
export OPENAI_API_KEY='<provider key>'
export OPENAI_BASE_URL='https://<provider>/api/v1'
python3 experiments/run_batch.py \
  --case-file experiments/cases/dev5.jsonl \
  --run-id dev5-envbench-agent-v1 \
  --runner envbench-agent \
  --model '<provider/model-id>' \
  --seed 0 \
  --max-workers 1
```

Run the minimal verifier-gated EnvSolve v0 through the same harness. It uses
the same bash toolkit and budget bridge as FreeAgent, adds only the fixed
`python -m pip check` completion gate, and never includes that diagnostic gate
in the generated bootstrap script:

```bash
python3 experiments/run_case.py \
  --case-file experiments/cases/dev5.jsonl \
  --case-id '<case-id>' \
  --run-id '<run-id>' \
  --runner envsolve-v0 \
  --model '<provider/model-id>' \
  --seed 0
```

The first paired Discovery-5 experiment is machine-preregistered. The
coordinator verifies every frozen hash, requires credentials only through the
environment, alternates FreeAgent/v0 order, preserves all first attempts, and
resumes without overwriting existing artifacts:

```bash
export OPENAI_API_KEY='<provider key>'
export OPENAI_BASE_URL='https://openrouter.ai/api/v1'
python3 experiments/run_v0_discovery.py
```

After all ten attempts exist, generate the frozen observable-stage analysis:

```bash
python3 envsolve/tools/analyze_v0_discovery.py
```

The agent's JSONL trajectory is converted into a replayable bootstrap script.
Failed commands, typed observations, import smoke checks, and tests are removed.
Replayable mutations are represented as typed actions such as package install,
runtime configuration, environment export, and environment activation. A
successful command containing an unknown or unsafe shell segment fails closed
instead of being silently replayed or discarded. The runner also rejects a
wrong checkout, any tracked repository change, ignored or untracked injection
artifacts, verifier configuration, and symlinks. Repo2Run commands pass through
the same typed replay policy. Standard virtual-environment, build, cache,
coverage, and egg-info outputs are allowlisted.

Re-distill and evaluate a previously recorded model trajectory without making
another provider request:

```bash
python3 experiments/run_case.py \
  --case-file experiments/cases/dev5.jsonl \
  --case-id '<case-id>' \
  --run-id '<new-run-id>' \
  --runner envbench-recorded \
  --source-run runs/<source-run-id> \
  --model '<same-provider/model-id>'
```

The recorded runner rejects a mismatched case, model, revision, modified source
tree, missing trajectory, unauditable source run, or path escaping the source
run. It can re-distill a source that failed only at the prior replay-policy gate
when the model process exited successfully and the complete trajectory and
repository-integrity evidence are present. Token usage remains attributed to
the original generation.

Typed Replay IR v4 semantics, its synthetic corpus, and its immutable file
hashes are recorded in `research/TYPED_REPLAY_IR_V4.md`,
`tests/fixtures/replay_ir_v4_cases.json`, and
`experiments/protocols/typed_replay_ir_v4_freeze.json`.

Generate or verify the P0 Harness Freeze Manifest:

```bash
python3 experiments/tools/harness_freeze.py
python3 experiments/tools/harness_freeze.py --verify
```

The current manifest is `experiments/protocols/harness_freeze_v10.json`; it
content-addresses harness and external-component source surfaces,
all frozen split files, budgets, pricing, protocol criteria, evidence-channel
contracts, registries, Git revisions, and the evaluator image. Regeneration is
a protocol-versioning action, not a routine prerequisite for a run.

Summarize and audit the batch:

```bash
python3 experiments/summarize_run.py runs/dev5-deterministic-v1
```

Run the P0 smoke evaluation from the workspace root:

```bash
python3 experiments/evaluate_only.py \
  --case-file experiments/cases/smoke.jsonl \
  --script experiments/scripts/reticulum_editable_install.sh \
  --run-id p0-smoke \
  --method deterministic-editable-install
```

This script is expected to complete evaluation but not pass the official
EnvBench metric: Reticulum has platform-specific optional imports that are not
installed by its default metadata. The distinction is intentional. Empty module
stubs are prohibited by the research protocol.

Each run is written to:

```text
runs/<run-id>/<case-id>/
  manifest.json
  status.json
  inputs/case.json
  inputs/evaluator.jsonl
  scripts/bootstrap.sh
  scripts/generated.sh
  generation/result.json
  generation/budget_ledger.json
  generation/trajectory.jsonl
  evaluation/result.json
  evaluation/json/results.jsonl
  logs/evaluation.log
```

`manifest.json` records the run specification, host, harness and evaluator Git
state, evaluator source hashes, Docker image ID/digest, resource budget, exact
command, bootstrap script hash, and parsed result. The budget includes model
request timeout and retry count, output-token and iteration caps, Git fetch,
shell, generation, evaluator-process, and Docker deadlines. It also records the
model pricing source and snapshot date. API keys are never part of a run
configuration or artifact.

The local budget is configured in `experiments/configs/local_mac.json`. A hard
generation or evaluation deadline records a structured `budget_exhausted`
termination and removes only containers attributed to that case. Before each
logical model request, the online ledger enforces request, cumulative-token, and
normalized estimated-cost limits. The LangChain and Repo2Run bridges write the
same ledger schema, which audit checks against solver metadata and manifest
pricing.

Runs are bound to the machine-readable protocol in
`experiments/protocols/envbench_python_official_v1.json`. Existing run
directories are not overwritten unless `--overwrite` is explicitly passed.
The lifecycle is recorded in `status.json`, including evaluator failures.

Official score evidence and non-scoring diagnostic evidence are separate.
EnvBench bootstrap status and full Pyright diagnostics are retained for
analysis, while audit computes Official Pass only from the frozen protocol
metrics. An incomplete diagnostic is `null`; it is never treated as a pass.

Batch runs handle both interactive cancellation and scheduler termination.
`SIGINT` exits with 130 and `SIGTERM` exits with 143. Active case process groups
are terminated, Docker containers whose host mounts belong to the case artifact
directory are removed, active artifacts transition to `interrupted`, and queued
cases are recorded as `not_started` in `batch_summary.json`. Interrupted case
artifacts remain independently auditable.

For model-generated runs, audit also requires the runner's repository integrity
and online budget reports to be present and valid. Recorded trajectories created
before these reports were introduced remain usable for historical analysis but
are not silently re-scored under the strict harness.

Audit a completed or failed run with:

```bash
python3 experiments/audit_run.py \
  runs/<run-id>/<case-id>
```
