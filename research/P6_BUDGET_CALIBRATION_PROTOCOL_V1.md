# P6 Budget Calibration Protocol v1

## Scope

This protocol does not alter the already frozen Dev-5 qualification schedule.
It defines how EnvSolve will choose and defend the resource budget used by the
later held-out comparison. Only development-only resource traces may inform the
choice; held-out outcomes remain unopened.

## Resource vector

Fairness is defined by a shared vector, not by equal realized cost:

- model backbone, provider, seed policy, and price snapshot;
- candidate, fresh-environment, and command caps;
- model calls, input/output/cache tokens, and estimated USD;
- per-request, container-create, command, episode, and evaluator timeouts;
- one terminal evaluator attempt, except for one preregistered exact-script
  retry after machine-classified infrastructure censoring.

All methods receive identical upper bounds. Savings from stopping early are an
outcome, not unused budget that must be spent.

## Externally anchored limits

The 900-second command/container limit and 1,800-second evaluator-process limit
match the EnvBench execution boundary. The 180-second model-request and
container-create limits are infrastructure controls and are reported separately.

## Budget frontier

1. Run the current outcome-blind Dev-5 qualification without changing its
   existing limits.
2. Reconstruct audit-valid resource trajectories, retaining Fail and Unknown.
3. Treat EnvSolve as an anytime solver and report candidate caps
   `K in {1, 3, 5}`. These points are fixed before held-out execution and are not
   selected by development or held-out success.
4. Run one causally ordered episode with maximum `K=5`. Its immutable prefixes
   determine the lower-budget states: an official Pass reached at attempt `j`
   counts for every `K >= j`; no accepted candidate by `K` is Fail; an
   infrastructure censoring at attempt `j` makes every `K >= j` Unknown. Official
   evaluation is still terminal and occurs at most once.
5. Designate `K=5` as the leaderboard setting before Canary-20 or Official-Test
   is opened, while the paper reports the full frontier rather than claiming that
   five is an optimal natural constant.

The policy may make at most two consecutive recoverable proposal failures before
a candidate. Therefore the model-call cap is derived as `3K`, rather than the
current loose value of 30. Provider transport retries are counted separately.

The terminal token and USD safety caps are set from audit-valid development
usage only: 125% of the maximum observed usage at `K=5`, rounded up
to the next 10,000 tokens and $0.01. These caps prevent runaway execution; the
paper reports realized usage and does not claim they are natural constants.

The episode wall limit is the smaller of the infrastructure maximum and the
derived sequential bound for `K=5`. Every ledger must be finalized,
so terminal command time is included.

## Reporting

The main table reports Official Pass@1 across the frozen `K={1,3,5}` frontier,
with `K=5` separately identified as the leaderboard configuration. Cost analysis reports
fresh environments, model calls, tokens, USD, and wall time for every outcome,
including censored Unknown. No budget is selected by maximizing held-out score.
