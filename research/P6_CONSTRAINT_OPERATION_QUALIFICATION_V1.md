# P6 Constraint-Operation Qualification V1

Status: design preregistration, before selection from the remaining untouched
development pool and before any new repository inspection or model request.

## 1. Question

Does converting admitted hard conflicts into typed operation obligations improve
repair behavior over the same EnvSolve state and verifier with free-form action
generation?

This is a causal mechanism qualification, not a paper-level effectiveness claim.
It adds no parser, package mapping, repository rule, or verifier condition.

## 2. Compared methods

Both conditions use the same repository profile, typed facts, constraints,
hypotheses, bounded execution feedback, two-layer verifier, candidate language,
model, seed, budgets, and fresh-container policy.

1. `envsolve-operation-ablation` receives the typed constraint state but no
   `OperationPlan`; its complete program is not checked by the operation guard.
2. `envsolve-operation` additionally receives the deterministic `OperationPlan`;
   `constraint-operation-guard-v1` checks each candidate before container creation.

The operation layer is the only intended treatment difference. Both conditions
retain the candidate validator and all evidence-admission rules.

## 3. Outcome-blind selection

- Population: `experiments/cases/train_untouched_after_v3_qualification196.jsonl`
  at SHA256
  `337f72f00b3731fe7388628a01e45f09ac07a4b3f579bc2fbdbdeddfede352ce`.
- Salt: `envsolve-p6-operation-qualification-v1-2026-07-17`.
- Rank by ascending `SHA256(salt + "\0" + case_id)` and select five cases.
- Read case metadata only. Repository source, prior outcomes, trajectories, package
  metadata, and evaluator results are forbidden before selection.
- Selected cases become permanently development-consumed and are removed from the
  remaining pool, regardless of infrastructure outcomes.

## 4. Budget and execution

The primary setting is `K=5` candidate attempts. A rejected candidate consumes one
candidate and its model usage, but no environment or command. The model-call cap is
`3K=15`, following the frozen recoverable-output control flow. Existing development
token, USD, and wall-time caps remain nonbinding safety limits and are identical;
all realized usage is reported.

Each method-case pair has an independent ledger, trajectory, script, and container
set. Method and case order are salted before execution. Official evaluation is
terminal, occurs at most once per completed method-case episode, and never enters
online state.

## 5. Outcomes

Report for every pair:

- internal and official terminal outcome;
- whether any hard conflict and operation requirement was produced;
- guard accept/reject counts and rejected candidate classes;
- obligation-response rate and repeated-conflict rate;
- candidate, environment, command, model-call, token, cost, and wall-time usage;
- clean-replay result and all infrastructure Unknown outcomes.

Pairs with no operation requirement estimate neither guard benefit nor harm and are
reported as non-triggering observations.

## 6. Interpretation

The mechanism is qualified only if the implementation boundary remains audit-valid
and triggered episodes show that obligations change candidate behavior without
using forbidden information. Five cases cannot establish aggregate effectiveness.
Negative results are retained. Any code change after selection requires a new
version and a new outcome-blind batch; selected outcomes cannot become repair rules.

