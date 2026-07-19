# EnvSolve v0 Error-Analysis Protocol

## Purpose

EnvSolve mechanisms must be selected from observed failure structure rather
than from an architecture-first narrative. Round 0 therefore analyzes the
already consumed same-backbone FreeAgent Dev-5 trajectories before an EnvSolve
v0 mechanism is chosen. It performs no model request, repository execution,
official verification, or held-out inspection.

## Unit of analysis

The analyzer reconstructs each bash decision from the model tool call, its
stated reason, the corresponding tool output, and the authoritative command
history exit code. It records command and normalized-output hashes, action
class, prior exact attempts, prior failures, same-output failures, and whether
an exact retry eventually recovered. Tool-call/history disagreement fails
closed.

This first artifact quantifies symptoms only. It does not infer root cause from
an exit code, label infrastructure failures, select an EnvSolve mechanism, or
claim that repeated commands are irrational.

## Round 0 result

Across five trajectories, FreeAgent executed 83 commands and observed 12
nonzero exits. Six commands exactly retried a previously failed command; all
six occurred in Poetry. Their normalized output hashes were different, and the
sixth retry eventually exited zero. The reasons explicitly described a network
timeout, intermittent network, and progressive acquisition.

This is a counterexample to unconditional failed-command suppression. The
current evidence supports retaining retry progress in the trajectory schema,
but it does not yet establish retry control as the dominant cross-repository
failure or justify an algorithmic intervention. The next step is the minimal
end-to-end EnvSolve v0 runner; its own blinded-development trajectories will be
the first valid source for selecting an EnvSolve mechanism.

The machine-readable result is
`experiments/validations/envsolve_v0_round0_freeagent_trajectory_analysis.json`.

## Round 1 transport qualification

The first frozen paired batch completed ten process attempts, but the v0 graph
wrote an empty initial state and LangGraph terminated before any model request.
This is a transport defect, not an environment-solving failure. The original
batch remains immutable. A minimal state schema that writes the unchanged human
message passed an offline graph-execution test and an already-consumed same-case
qualification: 7/7 requests completed, the old exception did not recur, and the
fixed verifier was called once and passed. The resulting replay rejection did
not admit an algorithm mechanism.

## Round 2 result

Round 2 froze five new outcome-blind cases and alternated condition order. All
ten first attempts and all audits completed; neither condition had a provider
error. EnvSolve v0 used 67 requests and 665,867 tokens versus FreeAgent's 123
requests and 1,702,574 tokens, but neither reached official evaluation.

Four valid v0 trajectories called the fixed verifier once, passed it, and then
failed on the same exact replay representation: `eval "$(pyenv init -)"`. The
fifth v0 trajectory failed repository integrity after creating a virtual
environment inside the repository. The repeated pyenv family therefore met the
preregistered threshold of at least two cases and a plurality of attributable
v0 failures.

The admitted response was deliberately classified as infrastructure, not an
EnvSolve algorithm. Typed Replay IR v5 replaces only the exact pyenv
initialization with an explicit shim-path runtime action; arbitrary `eval`,
command substitution, and unrelated working-directory effects remain rejected.
The full suite passes 228 tests. Read-only redistillation unlocked exactly two
of four trigger trajectories.

Official counterfactual evaluation of those two trajectories produced no pass.
Pyfirebirdsql completed bootstrap but had 11 public issues and 701 Pyright
errors. Islandora failed bootstrap when a package download timed out, so that
record is network-censored. These outcomes show that the in-place `pip check`
gate is not aligned with either fresh replay or the public goal verifier.

## Counterexample Loop v2 status

The minimal clean-replay counterexample loop has now been design-preregistered
and implemented at the benchmark-independent core:

1. distill the candidate action sequence into typed effects;
2. execute it in a fresh environment through a pluggable verifier contract;
3. normalize bootstrap and goal-verifier failures into explicit constraints;
4. append those constraints to solver state before allowing the next repair.

Its first content freeze covered the candidate/verifier protocols, event ordering,
fresh-environment identity, fail-closed contracts, and selective evidence admission.
A synthetic audit before any real case found that parseable but mutually consistent
feedback could otherwise authorize another proposal. V2 therefore requires at
least one explicit constraint conflict. The structured adapter was subsequently
frozen at v3: explicit verifier goal decisions are preserved and finding provenance
remains attached to typed evidence. EnvBench Finding Collector v1 binds official
missing-import diagnostics to revision-owned source while keeping P5 semantic
disposition separate. One read-only recorded qualification recovered 11/11
goal-active findings, split as 5 semantic active obligations and 6 guarded optional
findings, with 0 Unknown; 690 non-environment Pyright errors were not admitted. Nine
core tests, ten adapter tests, seven collector tests, and the 254-test full suite
pass. No new benchmark execution, model request, or repository rule was used.

This is still not an admitted EnvSolve mechanism. The next step is to connect the
frozen loop, adapter, and collector to a matched-budget model policy, then
preregister a separately selected unseen development batch. The loop must improve
that batch over v0 and same-backbone FreeAgent before Canary-20 is touched.
