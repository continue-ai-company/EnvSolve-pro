# P4 Typed Repair Protocol

## Purpose

P4 turns evidence-grounded constraint conflicts into typed, replayable repair
plans. It does not treat a zero command exit code as proof that the environment
changed as intended. A repair transition is committed only after an independent
probe observes the proposed fact.

P4A is the repair-kernel milestone. It freezes the transition semantics and
three generic operator families before another development-case execution.

## Repair plan

Every plan contains:

- a deterministic repair ID and typed repair kind;
- the source conflict and participating constraint IDs;
- existing fact constraints proposed for replacement;
- one proposed fact describing the intended post-state;
- a typed mutation command and risk level;
- an independent read-only verification probe;
- evidence IDs supporting operator context;
- an optional rollback command.

Plan identity is derived from canonical semantic JSON. Repository names,
benchmark IDs, evaluator outcomes, and free-form model explanations are not
part of operator selection.

## Context contract

Operators may consume only explicit `RepairContext` values:

- observed available Python versions and a runtime manager;
- an observed system package manager;
- capability-to-system-package candidates;
- module-to-distribution candidates;
- evidence IDs supporting those observations or mappings.

The kernel does not guess that an import name equals a distribution name and
does not embed a repository-specific repair table. Context providers and their
evidence acquisition will be evaluated separately.

## Initial operator families

### Runtime selection

For a Python-version conflict, select the highest observed available version
that satisfies all active PEP 440 requirements. P4A renders a `pyenv` state
transition only when `pyenv` and the candidate version are present in context.
The independent probe is `python --version`.

### System capability installation

For a required but absent executable, install only a system-package candidate
provided by context. Rendering is allowlisted for apt, apk, brew, dnf, and yum.
The independent probe is `command -v -- <capability>`.

### Python module installation

For a required but absent module, install only a distribution candidate
provided by context. The independent probe imports the module without modifying
the repository.

## Transition-aware preflight

A repair may replace only high-confidence fact constraints. Requirements can
never be superseded by an action. Every replaced fact must:

- exist in current state;
- participate in the declared source conflict;
- have the same domain, subject, and predicate as the proposed fact.

Preflight solves a projected post-state consisting of active constraints minus
the replaced facts plus the proposed fact. It rejects unknown references,
requirement replacement, low-confidence effects, unrelated replacements, and
projected conflicts. This projection permits a mutation to repair an existing
conflict without weakening its requirement.

## Verification-gated commit

The repair state machine uses deterministic action IDs and is resumable from
the P2 trajectory:

1. record transition preflight evidence;
2. execute the typed mutation through the P2 session;
3. execute the independent read-only probe;
4. parse the probe into structured evidence;
5. require the observed fact to equal the proposed fact;
6. mark only the replaced facts `superseded`;
7. propagate constraints again and record V1 verification.

Mutation or probe failure leaves old facts active and records a structured
failure. A successful mutation with a mismatching probe also leaves state
unchanged. The repair engine ignores `superseded` facts during subsequent
solving but preserves them in the append-only trajectory.

## Integrity policy

- Dev-5 and Dev-Extension-3 remain development-only.
- No Canary-20 or Official-Test-100 case may inform P4 operators.
- Synthetic tests define safety and transition behavior before recorded Dev
  conflicts are replayed through the registry.
- A context mapping learned from development evidence must be disclosed and
  cannot be treated as confirmatory generalization evidence.
- P3, P2, and P0 frozen semantics remain unchanged.

## P4A exit criterion

P4A is complete when plan identity, all three operator families,
transition-aware preflight, successful verification-gated commit, failed and
mismatched verification, and resume behavior pass synthetic tests. The two
already consumed P3 conflicts may then be used only for a read-only coverage
audit of the frozen generic registry.

P4 as a whole remains open until Dev-5 can be processed end to end without
repository-specific policy and the resulting environments pass the declared
verification protocol.

## P4A validation result

Thirteen synthetic tests pass. They cover deterministic plan identity, highest
compatible runtime selection, refusal to guess missing context, evidence-backed
context, all three operator families, requirement-replacement rejection,
successful verification-gated commit, mutation failure, probe failure, probe
value mismatch, and trajectory-based resume without action re-execution.

A read-only audit then reconstructed the two already consumed P3 development
states. Both conflicts match a generic operator family:

| Recorded conflict | Operator family | Missing context | Executable plans |
| --- | --- | --- | ---: |
| Python `3.13.2` outside `<3.12,>=3.8` | `runtime_selection` | observed runtime manager, available compatible versions, context evidence | 0 |
| required but absent `pg_config` | `system_capability_install` | observed package manager, capability-package mapping, context evidence | 0 |

The zero-plan result is intentional: the recorded evidence does not establish
those context values, so the audit does not invent them. The next P4 increment
is evidence-producing context probes and providers. No model request, benchmark
execution, Canary inspection, or Official-Test inspection occurred in P4A.
