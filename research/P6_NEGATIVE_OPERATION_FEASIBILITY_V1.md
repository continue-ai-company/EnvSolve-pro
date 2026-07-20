# P6 Negative Operation Feasibility V1

Status: repository-free synthetic mechanism qualification complete; development
effectiveness qualification pending.

## Hypothesis

When a provider deterministically rejects an operation target, persisting that
failure as typed negative feasibility state will prevent the same operation from
being retried in an unchanged provider context. It must not deactivate the repository
requirement, block a different operation, or harden infrastructure-censored feedback.

This hypothesis was generated from consumed Q11 trajectories. Those trajectories
cannot validate the resulting revision.

## Three-Layer Semantics

**Observation.** The verifier emits an `operation-observation` only when three pieces
of evidence agree: the instrumented candidate identifies the exact failed command,
the shared validator identifies it as a Python or system package-install action, and
the command output contains an exact provider-target-unavailable signature. Network,
timeout, artifact-integrity, build, path, and untyped failures emit no negative
operation observation.

**Constraint.** The observation becomes a scoped fact with domain `operation`,
predicate `feasible`, and value `false`. The fact retains candidate and environment
provenance and accumulates across candidate contexts. It is not a negative module,
package, or capability fact and therefore cannot satisfy or deactivate the original
repository obligation.

**Operation.** The full method exposes all active negative operation facts in its
bounded operation view. Before a fresh environment is allocated, the operation guard
rejects the same command only when the relevant provider context matches the failed
candidate. Python context includes runtime selection, virtual-environment binding,
safe environment exports, and prior Python package operations. System context
includes package-index update and safe environment exports. A changed context or a
different command remains admissible.

## Admission Matrix

| Evidence | Negative operation fact | Guard consequence |
| --- | --- | --- |
| Typed pip install + exact no-distribution signature | Yes | Same command and Python context rejected |
| Typed system install + exact unavailable-package signature | Yes | Same command and system context rejected |
| Network/provider transport signature | No, outcome is Unknown | No hard rejection |
| Same text attached to a runtime action | No | No hard rejection |
| Build failure, missing path, or generic nonzero exit | No | No hard rejection |
| Same command after runtime-context change | Existing fact retained | Retry allowed in new context |
| Different provider command or operation kind | Existing fact retained | Alternative allowed |

## Synthetic Qualification

Repository-free tests establish the full transition: typed verifier admission,
constraint normalization and provenance, accumulation across contexts, bounded model
visibility only in the constraint-driven treatment, context-sensitive guard behavior,
and end-to-end rejection before environment allocation. Negative controls cover
network Unknown, error text attached to the wrong action kind, changed runtime, and
alternative operations. Failure context is reconstructed from the verifier-recorded
failed prefix, so repeated identical commands at different positions cannot be
confused; every occurrence in a new candidate is checked against that grounded typed
context. The focused suite passes 107 tests plus 44 subtests, and the real
fresh-container Docker boundary passes. The manifest-independent pre-freeze suite
passes 408 tests with one skip; the final full suite passes 410 tests with one skip.

## Claim Boundary

This result qualifies mechanism semantics, not deployment effectiveness. No package,
module, repository, benchmark split, or evaluator outcome appears in the rules.
Q11 remains closed and is not rerun. After Algorithm v16 and Harness v31 are frozen,
the next admissible effectiveness step is a newly preregistered, metadata-only,
outcome-blind development batch from the 141 untouched identities.
