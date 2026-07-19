# Benchmark-Decoupled Harness Architecture

## Dependency rule

The harness core defines execution contracts and normalized evidence. It never
imports EnvBench, Repo2Run, Pyright, LangChain, or a provider SDK. Dependencies
point inward from plugins to the core.

```text
Solver plugins                 Benchmark plugins
EnvSolve  Repo2Run  ReAct      EnvBench  Synthetic  FutureBench
       \      |      /              \       |       /
          SolverRunner             BenchmarkAdapter
                 \                  /
                  Generic Harness Core
          case, protocol, evidence, budget,
          lifecycle, integrity, artifacts, audit
```

`envsolve_harness/core`, `budget`, `integrity`, `execution`, `storage`, and
`audit.py` are benchmark-independent. Built-in plugins are loaded lazily by
`runners/registry.py` and `adapters/registry.py`.

## Core contracts

### BenchmarkAdapter

A benchmark adapter exposes a `benchmark_id` and evaluates a bootstrap script.
It returns a generic `EvaluationResult` containing:

- `evaluation_completed` and `official_pass`;
- benchmark and case identity;
- normalized `VerificationEvidence` entries with `official` or `diagnostic`
  channels;
- benchmark-owned `raw_metrics`;
- portable raw-artifact paths and provenance metadata.

EnvBench's exit code, issue count, Pyright counts, repository name, and commit
SHA live only in `raw_metrics`. They are not fields in the core result model.

### ExperimentProtocol

Official success is a conjunction of generic metric predicates such as
`exit_code eq 0` or `issues_count lte 0`. Audit reconstructs the verdict from
the frozen protocol and `raw_metrics`; it does not contain benchmark-specific
score logic.

### SolverRunner

A solver runner transforms a frozen case into a replayable bootstrap artifact.
Runner-specific trajectories remain plugin-owned. Successful runners declare
machine-readable `audit_requirements`, allowing core audit to enforce integrity
and online-budget evidence without knowing runner names.

### BudgetLedger

The online ledger accepts only normalized model-usage deltas. Before a logical
model request, `preflight()` enforces request, cumulative-token, and normalized
estimated-cost limits. After a response, `record_response()` atomically records
input, output, and cache-read tokens using a frozen pricing snapshot.

LangChain and Repo2Run use thin bridges to the same ledger. Pricing is explicit
configuration and provenance, never a hidden algorithm constant. Provider
billing may differ from the normalized estimate; actual billed cost will be
recorded separately when a provider exposes it.

## Adding a benchmark

1. Add a `BenchmarkConfig` entry with an adapter ID, root, and opaque settings.
2. Implement `BenchmarkAdapter` outside the core.
3. Register its factory with `register_benchmark_adapter`.
4. Define official success through metric predicates in a protocol JSON file.

The synthetic registry test demonstrates this path without changing core or
`run_case.py`.

## Adding a solver

1. Implement `SolverRunner` outside the core.
2. Register a factory and default method name with `register_solver_runner`.
3. Emit generic artifacts and declare required audit capabilities.
4. Use `BudgetLedger` directly or provide a framework-specific thin bridge.

## Current plugin boundary

EnvBench remains the first official benchmark plugin and the default protocol,
not the definition of environment synthesis. Repo2Run and EnvBench ReAct remain
baseline solver plugins. Historical artifacts use their original schemas;
manifest schema `0.5.0` marks the benchmark-decoupled result format.
