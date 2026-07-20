# P6 Output-Contract Consumed Replay V1 Results

Status: closed as unexercised. This is consumed-development mechanism evidence,
not an effectiveness or leaderboard result.

## Result

The single preregistered run ended after 909.3 seconds and passed artifact audit.
It started four model requests, completed three responses, parsed three candidates,
executed one candidate in a fresh environment, and recorded one internal-verifier
failure. It did not reach the Official evaluator.

The first three completed responses produced exact JSON candidates without an empty
final response. The fourth response reached the 16,384-token completion limit before
the structured result could be parsed. The provider exception reports 2,878 prompt
tokens, 16,384 completion tokens, and 16,386 reasoning tokens. The online ledger
recorded this as one request error and omitted those response tokens because the
callback treated every parser exception as a transport failure.

No reasoning content was persisted. No online budget terminal occurred, so the
budget-terminal branch was not exercised. The preregistered practical qualification
required at least five completed parsed responses with no request error; it therefore
failed to trigger. The locked decision is
`unexercised_model_length_exception`, not contradiction and not qualification.

## Boundary Defects

This replay exposes two general output-boundary defects:

1. A length-finished provider response carries real usage and must count as a
   completed, token-consuming response rather than a request error.
2. A structured response that exhausts its output allowance is a recoverable policy
   output failure, not an unexpected `candidate-policy-exception`.

The next revision is limited to those accounting and classification corrections.
Reasoning allocation must then be qualified independently of repository identity
before one same-identity replay. No case-specific operation rule, Official feedback,
replacement identity, or effectiveness claim is allowed.

The locked machine-readable result is
`experiments/validations/p6_output_contract_replay_v1_results.json`.
