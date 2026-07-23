# EnvSolve-pro P0 Baseline Qualification v1

## Purpose

Before selecting any untouched P0 case, this qualification verifies that every method
can run its own native loop, produce auditable artifacts, and reach either its native
terminal state or the terminal-only EnvBench evaluator. The diagnostic case
`markqvist/reticulum@6ded42e` was already consumed and supplies no effectiveness
evidence.

## Qualified Methods

| Method | Native loop | Model | Valid terminal outcome |
|---|---|---|---|
| Codex CLI | Codex tool loop through one persistent container MCP | `gpt-5.5`, high reasoning | Official fail, `issues_count=18`; 1,306 total errors were non-scoring |
| Repo2Run reproduced | Repo2Run configuration loop and command history | `deepseek/deepseek-v4-pro` | Official fail, `issues_count=18`; 1,295 total errors were non-scoring |
| EnvBench raw ReAct | EnvBench FreeAgent ReAct loop | `deepseek/deepseek-v4-pro` | Official fail, `issues_count=18`; 1,295 total errors were non-scoring |
| Frozen EnvSolve v1 | Observation-Constraint-Operation candidate loop from `07a208f` | `deepseek/deepseek-v4-pro` | Native terminal failure: five-candidate budget exhausted |

Repo2Run is not claimed to be untouched upstream. It is the upstream implementation at
`65042aa` with audited compatibility repairs for current CLI/model plumbing, exact
revision checkout, ARM64 Docker execution, and dependency drift. The last qualification
repair pins `pipdeptree==3.1.0`, the release available when that upstream revision was
committed; unpinned `4.0.0` had no Linux ARM64 wheel and required Cargo.

## Wrapper Failures Excluded

- Codex attempts v1-v3 failed before a valid tool episode because of prompt transport
  and MCP approval wiring. V4 is the first valid native episode; its immutable trace was
  re-finalized after a generic repository-integrity policy correction.
- Repo2Run v1 made zero model requests and failed while building its unpinned helper
  image. V2 is the first valid episode.
- Raw ReAct v1 made zero model requests because the budget wrapper omitted LangGraph
  `bind_tools`. V2 completed the model loop, then Replay IR v8 rejected read-only dotted
  test-module pipelines. Replay IR v9 fixes the generic finalizer and reuses the audited
  immutable trajectory without another model call.

These attempts are harness or compatibility evidence, not method failures.

## Diagnostic Findings

Repo2Run and raw ReAct both reduced to `pip install -e .`; they validated imports or
project tests but missed platform-optional dependencies required by EnvBench. Raw ReAct
used 16 model requests and 173,537 tokens, repeatedly rerunning the same test suite with
different output filters. Repo2Run used four requests and 27,118 tokens. Codex executed
20 successful container commands and performed broader test and documentation checks,
but still missed the same optional-dependency boundary.

Frozen EnvSolve v1 showed useful stateful repair: it installed `pytest`, repaired its
test-discovery invocation, and finally exposed unresolved import constraints. However,
its fixed verifier treated `pytest` exit 5 as failure for a unittest-style repository,
spending four candidates on verifier reach before the fifth candidate discovered the
actual missing modules. It then exhausted the native five-candidate limit.

## Gate Decision

All four methods are operationally qualified. This does not establish fairness or
effectiveness. P0 may now select five untouched development cases, preserve each native
loop, report resource use without token or dollar success thresholds, and classify
zero-information infrastructure failures separately from method outcomes.
