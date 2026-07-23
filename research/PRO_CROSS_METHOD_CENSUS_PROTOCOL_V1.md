# EnvSolve-pro Cross-Method Trajectory Census Protocol v1

## Purpose

This consumed-development study compares complete EnvSolve-pro, Codex CLI, and
Repo2Run trajectories on the same 16 repositories. It is designed to identify the
next cross-repository algorithm bottleneck, not to estimate held-out effectiveness.
No new untouched case is opened.

## Frozen Objective

The only terminal success criterion is the unchanged EnvBench Python contract:

`exit_code == 0 and issues_count == 0`

`issues_count` counts `reportMissingImports`. Total Pyright `errorCount`, warnings,
and other diagnostics are non-scoring and cannot determine a failure category,
candidate preference, or mechanism priority.

## Methods

| Method | Host | Role |
|---|---|---|
| EnvSolve-pro causal v3 | DGX Spark | Current three-layer method |
| Codex CLI, `gpt-5.5`, high reasoning | Mac | Strong native-agent reference |
| Repo2Run reproduced open program | DGX Spark | External deployment baseline |

Existing earlier EnvSolve-pro census trajectories remain valid historical controls;
the current method is rerun because its model-visible constraint frontier changed.

## Analysis

For every method and case, record:

- terminal reach, Official Pass, bootstrap exit, and `issues_count`;
- model requests, tokens, executed environments, commands, and wall time;
- whether a replayable final program was emitted;
- the earliest decisive divergence at Observation, Constraint, Operation,
  Finalization, or Infrastructure.

The primary mechanism statistic is the number of distinct repositories exhibiting
each earliest decisive divergence. A next-version intervention requires one unique
largest category, evidence in at least four repositories, and a repository-independent
counterexample. Infrastructure failures remain Unknown. No source, prompt, wrapper,
or solver change is allowed after execution starts.

## Execution

The 16 cases are the complete union of the two already consumed P4 censuses. Execution
order is fixed by a salted hash. Mac runs one Codex lane. Spark runs one EnvSolve-pro
lane and two disjoint Repo2Run lanes. Every final program is evaluated once by the
unchanged terminal-only evaluator.
