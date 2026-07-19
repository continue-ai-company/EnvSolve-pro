# P4D Capability Discovery Round 2 Protocol

## Motivation

P4D Round 1 installed `apt-file` successfully but timed out after 600 seconds
while refreshing all enabled Ubuntu Contents indexes. No package candidate was
observed and no repair ran. The complete negative trajectory is frozen by
`p4d_capability_round1_freeze_v1.json`.

Round 2 tests a targeted official-index provider. It changes only capability
discovery; frozen P4A planning, preflight, mutation, and probe semantics remain
unchanged.

## Targeted provider

The provider derives four inputs from structured state and live image evidence:

- normalized executable capability subject;
- Ubuntu `VERSION_CODENAME`;
- `dpkg --print-architecture`;
- executable directories in the container's `PATH`.

It constructs one HTTPS request to the Ubuntu Packages Contents search service
on the fixed host `packages.ubuntu.com`, with `searchon=contents`,
`mode=exactfilename`, and the observed suite and architecture. Neither a package
name nor repository text is an input.

The response action records final URL, HTTP status, byte count, SHA256, and the
response body. The parser accepts only file/package table records that satisfy
all of the following:

1. the returned path basename exactly equals the requested capability;
2. the path's parent directory is in the observed `PATH`;
3. the package name passes the frozen system-package validator;
4. the package is independently present in the container's refreshed apt cache.

HTML structure mismatch, non-HTTPS redirect, unexpected host, truncated body,
non-200 response, empty candidate set, or apt-cache mismatch blocks the round.

## Action sequence

1. Observe platform, architecture, and `PATH`.
2. Verify the capability is initially absent.
3. Run one ordinary `apt-get update` for local installability metadata.
4. Query the targeted official Contents endpoint with a 120-second network
   timeout and a fixed user agent.
5. Parse exact PATH-reachable candidates.
6. Verify candidate package names against `apt-cache show`.
7. Emit structured context evidence for verified candidates only.
8. Let frozen P4A propose, preflight, execute, and independently probe up to
   three deterministic candidate plans.

Provider actions and repair actions remain separately labeled in the state
ledger. A successful capability transition still does not constitute an
EnvBench run or complete P4.

## Integrity

- Round 1 files and artifacts remain immutable.
- The same consumed P3 target and exact evaluator image are used.
- No repository is mounted, cloned, or exposed to the provider.
- No model request is allowed.
- Canary-20 and Official-Test-100 remain uninspected.
- Every failed and successful Round 2 trajectory is retained.
