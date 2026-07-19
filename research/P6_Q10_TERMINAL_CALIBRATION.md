# P6 Q10 Terminal Calibration

Status: preregistered before any new Official evaluator outcome.

## Question

Q10 ended with 50 internal-negative candidates and no Official evaluator execution.
That leaves two explanations entangled: the deployment actions may be inadequate, or
the internal verifier may reject scripts that the terminal objective accepts. Solver
changes are not identifiable until these explanations are separated.

## Frozen Intervention

For each of the ten closed Q10 runs, select the candidate attached to the last
`verification_recorded` event. This trajectory-only rule was applied before reading
any new Official outcome. It correctly excludes later proposals rejected by shared
candidate validation or the operation guard.

The ten selected scripts are copied byte-for-byte into
`experiments/scripts/p6_q10_terminal_calibration/`. The binding manifest records the
source episode, candidate ID, event sequence, source path, frozen path, and SHA256.
Proposal, verification, source-file, and frozen-copy hashes must agree.

Each frozen script is evaluated once, in binding order, with the unchanged EnvBench
source revision, protocol, configuration, and Docker image. Every execution uses a
fresh environment. There are no model calls, generation retries, replacements,
overwrites, or infrastructure retries.

## Outcomes

All selected scripts were internally negative. A completed Official pass is therefore
a concrete internal-verifier false negative. A completed Official failure is aligned
at the Boolean level, although diagnostic differences remain descriptive. Evaluator
infrastructure failure is `Unknown` and is neither retried nor replaced.

If any false negative appears, the next change must start from a generic synthetic
counterexample and make the smallest verifier correction before solver search is
modified. If every completed evaluation fails, this calibration provides no evidence
for relaxing the verifier; candidate feasibility and search efficiency become the
primary development target.

## Claim Boundary

This is a post-episode development calibration, not a rerun of Q10, an effectiveness
estimate, or a leaderboard result. The five case identities are already consumed
development data. Results cannot select replacement cases or alter the original Q10
closure.
