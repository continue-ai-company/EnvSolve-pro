# P4B Evidence-Producing Context Acquisition Protocol

## Purpose

P4A intentionally produced no executable plan for recorded conflicts whose
runtime or package context had not been observed. P4B acquires that context
through typed, read-only probes and deterministic provider parsers. It does not
allow an LLM assertion or an unreferenced mapping to become repair context.

P4B is additive. It does not modify the frozen P4A repair schema, transition
preflight, operators, or verification-gated commit semantics.

## Structured evidence

P4B defines the following evidence kinds:

| Kind | Required value |
| --- | --- |
| `context-tool-observation` | tool name, boolean presence, optional absolute path |
| `context-runtime-inventory` | runtime manager and normalized available versions |
| `context-system-manager-observation` | package manager, boolean presence, optional path |
| `context-capability-package-candidate` | capability, manager, and candidate system packages |
| `context-module-distribution-candidate` | import module and candidate Python distributions |

Only evidence at or above confidence `0.8` enters `RepairContext`. Every
selected context field contributes its evidence ID. Invalid names, versions,
paths, managers, package candidates, or distribution requirements fail closed.

## Probe policy

The initial case-independent inventory consists of:

- `command -v -- pyenv`;
- `pyenv versions --bare`, only after `pyenv` is observed;
- one `command -v` probe for each allowlisted system package manager:
  `apt-get`, `apk`, `dnf`, `yum`, and `brew`.

Each probe has a deterministic action ID. The policy reconstructs completed
steps from the P2 trajectory, records one structured evidence item per probe,
and can resume without re-executing completed commands. A missing optional tool
is an observation, not a solver failure. Probe commands do not install packages,
write repository files, or inspect evaluator scoring behavior.

When multiple system managers are present, the frozen selection order is
`apt-get`, `apk`, `dnf`, `yum`, then `brew`. Pyenv version inventories are
normalized with PEP 440 and deduplicated.

## Capability provider

P4B supports an apt-file output parser for capability-to-package candidates.
The provider command is rendered only for a validated executable name and uses
an anchored path expression. Parsed package names must pass the frozen package
token grammar. Provider output becomes candidate evidence, not an installed
capability fact; P4A still requires post-install `command -v` verification.

The context builder can also consume structured module-distribution candidate
evidence, but P4B does not yet claim an automatic module-to-distribution
discovery algorithm. Candidate provenance remains mandatory.

## Validation protocol

Safety and lifecycle behavior are defined first with synthetic command results.
After tests pass, a case-free container based on the frozen evaluator image may
run the inventory policy. It must not mount or download any benchmark repository.
The artifact records the image identity, commands, action/evidence trajectory,
derived context, and independent state audit.

No Canary-20 or Official-Test-100 identity, source, trajectory, or outcome is
inspected. A case-free image inventory is infrastructure characterization, not
an EnvBench success measurement.

## P4B exit criterion

P4B is complete when evidence validation, deterministic context construction,
conditional probe scheduling, missing-tool behavior, resume behavior, apt-file
candidate parsing, and secret-safe state recording pass synthetic tests; the
case-free evaluator-image inventory audits successfully; and P0 through P4A
freezes remain valid.

## P4B validation result

Eleven synthetic tests pass, covering context validation, confidence gating,
presence conflicts, manager priority, evidence tracing, missing optional tools,
conditional runtime inventory, policy resume, malformed output, anchored
apt-file commands, exact-path parsing, and empty-provider rejection.

The case-free inventory used the frozen evaluator image
`ghcr.io/jetbrains-research/envbench-python:latest` at image ID
`sha256:7bcf2ab3b1dec59e1f05cd96fbc0f41966dd1f957d1366e93b0c1e38b287c3d4`.
The temporary container had no mounts and network mode `none`. Seven probe
actions succeeded and observed:

- `pyenv`;
- Python `3.8.18`, `3.9.18`, `3.10.13`, `3.11.7`, `3.12.0`, and `3.13.1`;
- `apt-get` as the selected system package manager.

The trajectory contains 39 events, seven terminal actions, fourteen evidence
items, no failures, and an independently valid snapshot. It contains no
capability-package or module-distribution mapping. The runtime inventory can
support the recorded Python-conflict repair after image-provenance transfer;
the recorded `pg_config` conflict still requires provider evidence.
