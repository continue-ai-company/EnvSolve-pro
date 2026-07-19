# Structured Finding Adapter v2 Amendment

Status: pre-real-case synthetic amendment to Structured Finding Adapter v1.

V1 inferred goal success from bootstrap success and the absence of active findings.
That conflated two decisions owned by different components. A verifier can fail its
declared goal on a finding that the collector classifies as inactive for environment
repair; ignoring that finding must not relabel the verifier's Fail as Pass.

V2 therefore requires every structured report to carry the verifier's explicit
three-valued `goal_passed` decision. Finding disposition controls only whether typed
repair evidence is emitted. Unknown findings, incomplete execution, and
infrastructure errors still dominate and produce Unknown. A reported Pass with an
active counterexample is preserved as a contradiction so the core pass contract
blocks it.

No real repository, held-out case, model response, or benchmark outcome was observed
while making this amendment. All v1 domain mappings and fail-closed rules remain.
