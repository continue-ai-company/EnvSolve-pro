# P6 Output-Contract Consumed Replay V2 Results

Status: closed as `inconclusive_provider_exception_after_practical_trigger`.
This remains consumed-development mechanism evidence, not an effectiveness result.

## Result

The single preregistered run completed an audit-valid trajectory in 1,060.6 seconds.
Its first seven model responses all parsed into candidates with no length finish,
empty final, policy-output failure, or request error. Four candidates entered fresh
environments and four reached the fixed internal verifier; none passed and the run
never reached the Official evaluator.

The eighth request failed inside `model.invoke` with a provider/API JSON decoding
exception. The ledger therefore records eight requests, seven completed responses,
one request error, 26,659 input tokens, and 34,618 output tokens. No reasoning content
was persisted.

The preregistered practical rule required both at least five parsed completed
responses and no request error anywhere in the run. The first condition was exceeded,
but the second failed. This is not a v14 contradiction: there was no empty final,
length-accounting violation, reasoning-content persistence, or budget terminal
misclassification. It also does not satisfy the preregistered unexercised clause,
which covers a provider exception before five parsed responses. The strict closure is
therefore `inconclusive_provider_exception_after_practical_trigger`.

The frozen generic analyzer emitted `unexercised_provider_exception` because it did
not condition that label on trigger timing. The raw analysis is retained unchanged;
the machine-readable closure explicitly records the discrepancy and applies the
preregistered rule. There is no retry or replacement.

## Next Boundary

The output allocation has seven-response descriptive support, but formal
qualification remains blocked. The next minimal revision separates transient
provider-response acquisition failures from policy output, applies bounded
request-level recovery with complete attempt accounting, and makes future analysis
timing explicit. It must be qualified without a new repository identity before any
new unseen development batch.
