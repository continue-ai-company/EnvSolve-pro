# P6 Model Output Contract V2

Status: synthetic boundary qualified. This is provider/client compatibility
evidence, not repository-deployment evidence.

## Trigger

The preregistered consumed replay v1 produced three valid JSON candidates, then a
fourth response reached the 16,384-token completion limit before structured parsing.
The run was audit-valid and closed as `unexercised_model_length_exception`.

Two generic runtime defects were corrected. A length-finished response carrying
provider usage now counts as a completed token-consuming response instead of a
request error. The same condition is exposed to the solver as a recoverable
`candidate-policy-output` failure instead of an unexpected policy exception. No
prompt, constraint, operation, verifier, evaluator, or case-specific behavior changed.

## Allocation

The OpenRouter model catalogue snapshot on 2026-07-20 reports that
`deepseek/deepseek-v4-pro` supports only `high` and `xhigh` reasoning effort, defaults
to `high`, and permits up to 384,000 completion tokens. OpenRouter's reasoning
documentation also states that reasoning consumes the completion allowance and that
the allowance must leave capacity for a final answer. Therefore v2 retains the
lowest supported reasoning effort, `high`, and changes only the per-request completion
ceiling from 16,384 to 32,768. Aggregate limits remain 15 requests, 1,000,000 total
tokens, five environments, five commands, two hours, and the same fixed cost ceiling.

Sources: [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens),
[OpenRouter API parameters](https://openrouter.ai/docs/api/reference/parameters), and
the captured public model record in
`experiments/validations/p6_deepseek_v4_pro_capability_snapshot_20260720.json`.

## Synthetic Stress Probe

The production `StructuredModelDeploymentPolicy` received a repository-free synthetic
state with approximately 2,100 input tokens per request. Five requests used the
frozen model, `temperature=0`, `seed=0`, `high` reasoning, JSON-object mode, and the
32,768-token ceiling.

All five responses ended with `finish_reason=stop`; all five parsed into exact policy
candidates; there were zero request errors and zero policy errors. The probe consumed
10,403 input and 13,788 output tokens in 304.3 seconds. Per-response output ranged
from 119 to 5,453 tokens. Candidate and reasoning content were not persisted.

This qualifies the synthetic output boundary only. One preregistered same-identity
consumed replay is required before selecting another unseen development identity.
The replay cannot support an effectiveness, leaderboard, or paper test-set claim.
