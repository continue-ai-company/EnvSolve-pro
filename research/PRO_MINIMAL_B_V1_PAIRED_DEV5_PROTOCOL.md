# EnvSolve-Pro Minimal B v1 Paired Dev-5 Protocol

Date: 2026-08-04

## Question

Does online clean-replay feedback improve a strong deployment Agent when the model,
public goal, construction environment, terminal, candidate contract, and terminal
Official evaluator are held fixed?

## Conditions

- **A, strong goal-aware Agent:** one continuous Codex session and one persistent
  construction environment. It returns one complete bootstrap program. The harness
  executes that program after the session; no execution or evaluator result returns to
  the Agent.
- **B, Minimal B v1.0.2:** the same setting plus `submit_and_replay`. Each call executes
  the complete program in a distinct clean checkout and container, and returns bounded
  public-goal and integrity evidence to the still-active session. The final program must
  exactly match a passing replay certificate.

The additional tool and the instructions required to use it are the only intended
treatment difference. Official evaluator output is terminal-only in both conditions.

## Sample And Order

Five repository identities are selected from the frozen 58-row untouched development
pool by ascending `SHA256(salt + NUL + repository)`. Selection uses metadata only: no
repository content, historical result, or failure prescreen. Case order and the two
condition orders are independently frozen by salted hashes. Both conditions run on every
selected repository with the same model, reasoning effort, image, goal, and broad safety
limits.

## Outcomes

The primary outcome is paired Official Pass@1. Integrity failure, generation failure,
Official Fail, and infrastructure Unknown remain distinct. The main mechanism outcome is
replay-conditioned repair: a Minimal B episode receives a failing or unknown replay and
later certifies a passing program in the same Agent session.

Secondary descriptive measures are replay calls, commands, model tokens, wall-clock
time, peak memory, disk growth, and network bytes when available. Token count and dollar
cost are not success-stopping budgets.

## Analysis Rules

All ten scheduled episodes must finish or be classified before a mechanism change. No
case-specific rule, package exception, repository-dependent prompt, or selective case
replacement is allowed. This development batch may reject or motivate a generic
mechanism, but it cannot support held-out or leaderboard claims.

An episode may be censored as infrastructure Unknown for an external provider failure,
Docker unavailability, host suspension, or independently recorded network outage. Any
identical retry requires a frozen amendment; the censored artifact remains preserved and
does not become a model-training example for this batch.
