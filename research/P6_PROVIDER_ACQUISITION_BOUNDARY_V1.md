# P6 Provider Acquisition Boundary V1

Status: synthetically qualified; online normal-path pass-through qualified. This is
inference-boundary evidence, not deployment evidence.

## Trigger

Consumed replay v2 produced seven parsed model responses, then failed inside
`model.invoke` while decoding the eighth provider/API response. The frozen run was
closed without retry or replacement as
`inconclusive_provider_exception_after_practical_trigger`.

The failure occurred before EnvSolve received model message content. It is therefore
an acquisition failure, not malformed candidate output and not a repository
constraint. Treating it as `candidate-policy-exception` both terminates too early and
misstates the responsible layer.

## Minimal Boundary

EnvSolve now retries only Python `JSONDecodeError` raised by the provider/client
response boundary. It reuses the existing `model_max_retries=2`, giving at most three
attempts. Other exception types are not retried by this layer.

Every attempt crosses the same online budget callback. Failed attempts increment
`requests_started` and `request_errors`; scheduled parse retries and successful
recoveries are recorded separately. A recovered response continues through the
unchanged structured policy. Exhaustion becomes a solver-owned
`provider-acquisition-failure` with the exact attempt count, never a candidate-policy
failure. Model, prompt, constraint, operation, verifier, evaluator, candidate,
environment, token, cost, and wall-clock limits remain unchanged.

The output analyzer now distinguishes provider failure before versus after the
five-response trigger and exposes recovered parse errors separately. The frozen v2
raw decision is not overwritten.

## Qualification

A deterministic repository-free fault probe exercised both branches:

- One failed decode followed by success used two requests, one request error, one
  parse retry, one recovery, and one parsed candidate.
- Three failed decodes used three requests, three request errors, two retries, zero
  recoveries, and terminated as `EpisodeProviderAcquisitionFailed(attempts=3)`.

An online repository-free pass-through probe also returned one parsed JSON candidate
with `finish_reason=stop`, zero retry/error, 2,072 input tokens, and 2,065 output
tokens. Candidate and reasoning content were not persisted. Focused tests pass 65 plus
the end-to-end probe test; full pre-freeze regression is `396 passed, 1 skipped` with
only the expected stale-freeze failure.

These results qualify only acquisition accounting, bounded recovery, terminal
classification, and normal pass-through. After a new freeze, the next admissible
effectiveness-facing step is an outcome-blind unseen development qualification; no
consumed case is rerun.
