# EnvSolve-pro P1 Fair-Interface Results v1

## Decision

P1 is qualified on repository-neutral tests and already consumed P0 evidence. The open
candidate boundary removes representation-based rejection, adapter preconditions expose
the previously hidden state mismatch, and the effect audit preserves repository
integrity. This is an interface result, not an effectiveness result.

No untouched Dev case was opened and no model request was made.

## Frozen-Prediction Check

| Prediction | Observation | Decision |
|---|---|---|
| Successful shell compounds and probes remain executable | All six frozen Raw ReAct and Repo2Run trajectories compiled with zero unsupported commands | Supported |
| Repo2Run `futaba` needs its native Python/Poetry context | Preserving Python 3.10 and activating the Poetry environment reduced official issues from 159 to 2 | Supported |
| `importlib_metadata` still conflicts with evaluator state | Raw ReAct and Repo2Run both failed because `build_output/` became an extra top-level package | Supported |
| Old EnvSolve acceptance disappears under matched state | The frozen accepted candidate failed its first install after `build_output/` was materialized | Supported |
| Effect audit rejects task-boundary violations | Synthetic source mutation, import injection, and precondition deletion failed; generated environments remained admissible | Supported |

## Official Replays

The final open-interface replays all reached a completed official evaluation. None was
rejected by the candidate representation layer.

| Candidate | Exit | Issues | Errors | Official Pass | Interpretation |
|---|---:|---:|---:|---|---|
| Raw ReAct, `futaba` | 0 | 2 | 740 | No | Real residual Pyright failure |
| Raw ReAct, `importlib_metadata` | 1 | 0 | n/a | No | `build_output/` package-discovery conflict |
| Repo2Run, `marimo` | 0 | 372 | 2109 | No | Native tests and official Pyright optimize different outcomes |
| Repo2Run, `futaba` | 0 | 2 | 740 | No | Real residual Pyright failure after native-context closure |
| Repo2Run, `importlib_metadata` | 1 | 0 | n/a | No | `build_output/` package-discovery conflict |

The consumed Raw ReAct `marimo` trajectory was compiled but not rerun officially because
its P0 native execution had not completed successfully. Compilation is sufficient for
the frozen representation-loss prediction; it is not counted as an effectiveness run.

## What P1 Changed

- A deployment artifact is now a complete Bash program rather than a closed action list.
- EnvSolve executes each candidate in a fresh checkout and audits final effects.
- Benchmark adapters declare non-outcome workspace preconditions.
- Raw ReAct causal replay preserves every successful command in order.
- Repo2Run replay preserves successful shell programs plus documented runtime context.

The structured Observation and Constraint layers remain advisory. They may explain or
rank operations, but an unknown operation form is not rejected merely because the schema
does not contain it.

## Validation

- Full test suite: 431 passed, 2 skipped, and 75 subtests passed.
- Real Docker integration: 1 passed.
- Frozen compilations: 6 targets, 0 unsupported.
- Final official replays: 5 completed, 0 representation rejections, 0 Official Pass.
- Frozen internal replay: effect audit valid, candidate correctly rejected under matched
  `build_output/` precondition.

Machine-readable evidence is in
`experiments/validations/pro_p1_evaluation_v1/evaluation_summary.json`.

## Next Scientific Step

Freeze P1, then begin P2 with a newly salted, outcome-blind Dev sample. P2 must analyze
the first complete trajectories without changing the method and identify one frequent,
actionable deployment contradiction. Only that cross-case bottleneck may motivate the
first EnvSolve-pro algorithm change.
