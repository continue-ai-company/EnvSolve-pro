# P6 Negative Operation Feasibility V2

## Post-Freeze Counterexamples

The v1 guard was context-sensitive, but the treatment's persistent model view exposed
only the failed command and failure class. Once the source candidate left the bounded
recent-history window, the model could misread a local operation failure as a global
ban even though Guard v4 correctly allowed a changed runtime or provider context.

A second repository-free counterexample combined common dependency-network errors
with pip's trailing `No matching distribution` message. Proxy, TLS, connect-timeout,
name-resolution, retry-exhaustion, remote-disconnect, connection-reset, and apt
temporary-resolution signatures were not all classified before operation admission.
That could turn incomplete acquisition into false target-unavailability state.

No Q12 case had been selected when these counterexamples were added.

## Minimal Revision

V2 introduces one shared provenance function. A failed prefix is grounded only when
the verification is negative, candidate identity agrees, `action_index` identifies
the final prefix entry, and both the failed command and prefix entry match the typed
operation command. The treatment model view and Guard consume this same grounded
prefix; malformed or unpositioned evidence is invisible to both.

The treatment view now carries the commands before the failed operation and states
that infeasibility is scoped to the exact command in its recorded provider context.
The operation prompt explicitly preserves two escape routes: change the runtime or
provider prefix, or use a different command. The free-form ablation still receives no
operation plan or negative-operation view.

The verifier classifies the enumerated acquisition signatures as infrastructure
Unknown before testing provider-target-unavailable grammars. Check profile v7 records
this semantic change. Operation fact identity, accumulation, exact-command guard,
candidate language, primitive budgets, and Official access are unchanged.

## Synthetic Qualification

Repository-free tests cover persistent context visibility, missing-action-index
rejection, duplicate-command position disambiguation, eight network signatures with
misleading target-unavailability tails, changed-context retry, alternative operation,
and rejection before environment allocation. The focused suite passes 110 tests with
52 subtests. The manifest-independent suite passes 411 tests with one skip and 69
subtests; the real Docker boundary passes when explicitly enabled.

These results qualify semantics only. V1 and the first Q12 preregistration remain
historical records. A new algorithm freeze, harness freeze, and superseding
preregistration are required before Spark admission or case selection.
