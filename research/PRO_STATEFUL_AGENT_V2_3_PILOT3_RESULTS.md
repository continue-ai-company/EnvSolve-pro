# EnvSolve-Pro Stateful-Agent V2.3 Pilot-3 Results

## Status

This is consumed development evidence. All nine artifacts are hash-valid, but the runs
started from a dirty worktree and are therefore scientifically ineligible. The results
may guide a generic mechanism change; they cannot support an effectiveness, paper-table,
or leaderboard claim.

The three repository-disjoint cases compared:

1. strong single-session goal-aware Codex;
2. same-model multi-session raw repair;
3. EnvSolve-Pro structured V2.3.

All conditions used `gpt-5.5`, the same public executable goal, the same official
terminal evaluator boundary, and an open cumulative Bash program.

## Descriptive Results

| Condition | Official Pass | Wall time (s) | Commands | Input tokens | Output tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Strong goal-aware baseline | 2/3 | 4,576.2 | 97 | 4,805,038 | 50,680 | 21,775 |
| Raw repair V2.3 | 2/3 | 4,335.7 | 98 | 3,601,859 | 42,902 | 22,050 |
| Structured V2.3 | 2/3 | 7,940.6 | 218 | 11,176,127 | 123,352 | 64,447 |

| Repository | Strong | Raw | Structured | Decisive observation |
| --- | ---: | ---: | ---: | --- |
| pypose | Pass | Pass | Pass | The case was solved without a useful structured-repair advantage. |
| StopStalk | Generation fail | Official fail | Generation fail | Caller-visible operation contracts and verifier attribution dominated the outcome. |
| Pulser | Pass | Pass | Pass | Source roots plus `PYTHONPATH` were sufficient; extra state added no success value. |

There is no V2.3 effectiveness gain. Structured V2.3 is also the least efficient
condition in this small sample. Because the source was not clean, even this descriptive
comparison must not be merged into a formal aggregate.

## Failure Analysis

StopStalk exposes one general contradiction: **goal satisfaction and operation
admissibility are different state variables**.

- A raw-repair candidate completed the deployment goal, but its bootstrap left the
  caller in a temporary directory. The terminal evaluator then failed because its
  relative output path was resolved from the wrong directory.
- Structured round 3 built a legitimate environment, inspected a real Python source
  file, and wrote only analyzer configuration. The candidate validator falsely rejected
  it because it globally associated any quoted `.py` path with any write call.
- An earlier structured round satisfied the executable goal but violated repository
  effects. The compact projection collapsed these facts into a generic failure, so the
  next round searched again instead of preserving the construction and repairing the
  exact effect violation.
- The strong baseline satisfied the internal goal but modified a tracked nested
  repository while trying to restore state.

These are not package-specific failures. They concern the interface between a
goal-directed agent and executable operation verification.

## V2.4 Decision

V2.4 adds no deployment heuristic and does not narrow the terminal action space. It
makes four interface corrections:

1. validate actual embedded-Python write targets with AST analysis instead of global
   text correlation;
2. represent `goal_status` and `operation_contract` independently;
3. require a submitted program to restore the caller working directory;
4. retain the exact operation counterexample when the goal already passes, and remove
   stale rejection metadata after a terminal valid Pass.

The V2.3 cases are now consumed. V2.4 must be frozen from a clean committed revision and
tested on new repository identities. The primary outcome remains Official Pass@1; the
mechanism outcome is recovery when the goal is satisfied but an operation postcondition
is violated.
