# P4D Capability Discovery Round 3 Protocol

## Motivation

Round 2 found two exact, PATH-reachable, apt-installable providers for the same
executable. Frozen P4A ordered equal-risk plans by repair ID and selected the
first candidate. Its V1 `command -v` probe passed, but executable presence alone
does not prove that a dispatching wrapper has a usable backend or that the
consumer-facing interface works.

Round 3 adds semantic candidate qualification and a V2 commit gate. Round 1 and
Round 2 artifacts remain frozen and immutable.

## Candidate qualification

Round 3 consumes the exact candidate set recorded by the frozen Round 2
provider. Each candidate is evaluated independently in a fresh container made
from the same frozen evaluator image:

1. refresh apt metadata;
2. install exactly one candidate package;
3. verify executable resolution with `command -v`;
4. execute the generic version-reporting interface `<capability> --version`.

A candidate qualifies only when all commands exit zero and the semantic probe
emits non-empty bounded output. Candidate containers share no filesystem state
and are removed after evaluation. Qualified candidates are ordered by package
name; repair-ID hashes are not a semantic ranking signal.

The `--version` contract applies only to executable capabilities for which this
generic interface succeeds. Failure means “unqualified under this verifier,”
not that the package is universally invalid. Future capability classes may
require different typed interface contracts.

## V2 repair gate

Frozen P4A still supplies the plan, transition preflight, mutation command, and
V1 presence probe. A P4D V2 policy adds the same semantic probe in the fresh
repair container. It may supersede the old absent fact only after:

- mutation succeeds;
- V1 presence parsing matches the proposed fact;
- V2 semantic execution exits zero with non-empty output;
- post-transition constraint propagation removes the source conflict.

Any V1 or V2 mismatch preserves the old fact and records a failed V2
verification. A successful Round 3 result is a semantically gated capability
state transition, not an EnvBench success.

## Integrity

- Candidate names come only from the frozen Round 2 response artifact.
- Repository contents and identifiers are unavailable to qualification code.
- All candidate and repair containers use the exact frozen image with no mount.
- Network is limited to configured apt sources.
- No model request, Canary-20 inspection, Official-Test-100 inspection, or new
  benchmark execution is permitted.
