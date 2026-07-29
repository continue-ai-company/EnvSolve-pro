# Stateful Agent V1: Consumed Mechanism Result

## Scope

This study used two already-consumed EnvBench development repositories. It tests
mechanism plumbing only and cannot support a held-out, generalization, or leaderboard
claim. Both conditions used Codex CLI with `gpt-5.5`, the same public executable goal,
the same open cumulative Bash interface, and no online official-evaluator feedback.

## Result

| Case | Raw history | Structured state | Scientific adjudication |
|---|---:|---:|---|
| Lark | Official Pass, 1 round | Official Pass, 1 round | Both valid |
| micropy-cli | Official Pass, 1 round | Official Pass, 1 round | Both provenance-invalid |

The official aggregate is `4/4`, but only the two Lark positions are valid repository
reproductions under the stronger scientific contract. Both micropy-cli programs added
an older `micropy-cli` distribution to `PYTHONPATH`, supplying `micropy.cli` from code
outside the target revision while the rest of the `micropy` namespace came from the
checkout. Fresh replay reproduced this mixed-source environment; it did not prove that
the target revision itself was deployed consistently.

## What V1 Did and Did Not Test

All four episodes accepted the first submitted candidate. No candidate was rejected,
no executable-goal failure entered a second model session, and the structured
goal-obligation frontier remained empty before the only operation. The experiment
therefore tested the strong interactive Operation layer and final replay plumbing, but
it did not exercise the proposed structured repair mechanism.

The Lark pair shows that the open agent can produce legitimate environment-only
programs. Its single structured run used fewer commands and tokens than raw history,
but one stochastic pair cannot support an efficiency claim. The identical micropy-cli
shortcut in both conditions shows that the failure belongs to the shared verification
contract, not to one state representation.

## Scientific Decision

`stateful-agent-v1` is retained as a frozen diagnostic baseline but is not qualified as
the EnvSolve-Pro method. The next revision makes three minimal changes:

1. execute a shared read-only goal probe before the first model operation;
2. reject external search roots that overlay a top-level namespace supplied by the
   target checkout;
3. restore trusted shell invariants before verifier-controlled checks.

V2 must first demonstrate on consumed data that an invalid first candidate becomes a
typed observation and changes a later operation. Only then may a repository-disjoint
development batch be opened.
