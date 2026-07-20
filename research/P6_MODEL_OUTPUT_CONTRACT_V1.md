# P6 Model Output Contract V1

The Q10 budget calibration exposed three consecutive responses with empty final
content in one run. Those responses consumed output tokens but yielded no candidate.
This is an inference-boundary failure, not evidence for another repository constraint.

The minimal contract is provider-configurable and defaults to the historical behavior.
For the current DeepSeek V4 Pro qualification, it sets reasoning effort to `high` and
requests `json_object` output. An online synthetic probe with no repository or
evaluator context returned the exact `script` and `rationale` object with
`finish_reason=stop`; 124 of 150 output tokens were reported as reasoning tokens.

EnvSolve now records whether final content was empty, finish reason, output-token
count, reasoning-token count, and whether reasoning content existed. It never stores
the reasoning content itself. Online budget exhaustion is represented separately as
`episode-budget-exhausted`, not as a policy exception.

This probe establishes API compatibility only. Before another unseen development
batch, the contract requires synthetic tests, a new algorithm and Harness freeze, and
a preregistered consumed-development replay that cannot support an effectiveness
claim.
