# EnvSolve-Pro Minimal B v1 Design Freeze

Date: 2026-08-04

## Decision

The next EnvSolve-Pro implementation is frozen to one treatment:

> A strong Agent keeps one continuous reasoning session and one persistent construction
> environment, and may repeatedly submit a complete bootstrap program for verification
> in a distinct clean environment. Every replay result returns to the same Agent session.

This is a semantic design freeze, not yet a source-code freeze. An implementation freeze
will bind source, prompt, tool schema, image, model, cases, and analysis hashes after the
minimal mechanism passes unit and Docker integration tests.

## Three-Layer Boundary

### Observation

The Agent observes ordinary terminal results and the raw result of each clean replay:
candidate validation, bootstrap exit, public executable-goal report, repository-effect
audit, environment identity, and infrastructure status. Official evaluator output never
enters the session.

### Constraint

Minimal B enforces only the public executable goal, the shared candidate contract, and
repository-integrity boundaries. It does not maintain a derived constraint ledger,
compatibility frontier, package ontology, hypothesis graph, or cross-attempt semantic
summary.

### Operation

The same strong Agent session controls an unrestricted terminal in one persistent
construction environment. It may call `submit_and_replay` repeatedly. A failed replay
returns evidence to that session; a passing replay certifies the exact submitted program.

## Frozen Online Loop

1. Create one clean checkout and one persistent construction container.
2. Start one Agent session with the repository, public goal, candidate contract, and open
   terminal tool.
3. Let the Agent inspect, install, diagnose, and modify the environment within the shared
   admissibility boundary.
4. On `submit_and_replay(program)`, validate the complete self-contained program.
5. Provision a separate fresh checkout and container from the same base image and declared
   benchmark preconditions.
6. Execute the program, public goal, and repository-effect audit there.
7. Release the replay environment and return its raw bounded evidence to the same Agent
   session.
8. Continue after Fail or Unknown. Stop successfully only after one passing clean replay
   of the exact returned program.
9. Run the Official evaluator only after the Agent episode has ended.

The persistent construction environment and every replay environment are distinct.
Replay never mutates the construction environment. A final answer whose script hash does
not match the certified replay is rejected.

## Explicit Exclusions

The following mechanisms are not part of Minimal B v1 and must remain disabled by
default:

- structured state or constraint projection;
- checkpoints, branching, rollback, or frontier search;
- model-generated hypothesis scheduling;
- action-level postcondition admission;
- cross-session or cross-case memory;
- bootstrap minimization or resource-aware search;
- repository-, package-, module-, or case-specific rules.

They may be studied later only as orthogonal treatments over the frozen Minimal B
interface. None may enter the control condition through prompts, hidden tool behavior, or
analysis-time candidate selection.

## Controlled Comparison

The primary causal pair is:

- **A, strong goal-aware Agent:** one continuous session and persistent construction
  environment, followed by one post-session clean replay whose result is not returned;
- **B, Minimal B:** the same model, prompt prefix, terminal, construction environment,
  public goal, image, and safety limits, plus callable clean replay whose result returns to
  the still-active session.

The only intended treatment difference is whether clean replay is available as an online
tool. Official Pass@1 is primary. Replay-repair success, replay calls, wall-clock time,
commands, tokens, peak memory, disk growth, and network bytes are descriptive secondary
metrics. Tokens and price are not success-stopping budgets; only broad safety limits may
terminate runaway execution.

## Implementation Freeze Gate

Before any new effectiveness case is opened, the implementation must prove:

1. one model session survives multiple replay failures;
2. every replay uses a new environment identity and clean checkout;
3. replay evidence returns through the tool without Official evaluator leakage;
4. construction state is unaffected by replay;
5. only the exact clean-replay-passing script can be accepted;
6. Fail, Unknown, infrastructure censoring, and Pass remain distinct;
7. all excluded treatments are absent or disabled;
8. the frozen EnvSolve and strong-Agent baselines retain their previous behavior.
