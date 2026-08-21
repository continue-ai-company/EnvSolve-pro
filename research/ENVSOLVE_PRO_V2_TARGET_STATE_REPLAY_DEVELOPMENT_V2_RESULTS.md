# EnvSolve-Pro V2 Target-State Replay Development V2

Status: complete outcome-independent development mechanism expansion

## Question

Does the unchanged minimal target-state replay treatment continue to preserve Official
success and exercise feedback-conditioned repair on the final four cases of a pre-existing
randomized Dev16 order?

This is a development mechanism study. The four case identities, seeds, arm order, model,
provider, image, prompt, evaluator, and limits were recorded before source acquisition or
model execution. It is not held-out, leaderboard, effect-size, or SOTA evidence.

## Result

| Pair | Repository | A: free feedback | B: free feedback + target replay | Replay evidence |
|---|---|---:|---:|---|
| 1 | rstcheck | Pass | Pass | B passed its first replay |
| 2 | plasmapy | Pass | Pass | B passed its first replay |
| 3 | pygeo | Pass | Pass | B replayed Fail, Pass after adding acquisition retries |
| 4 | starsim | Pass | Pass | B passed its first replay |

Both arms passed `4/4`. The paired table has four both-pass pairs and no discordance, so
exact McNemar is `p=1.0`. This is a ceiling batch: it cannot estimate a success effect.

## What The Mechanism Did

All four B episodes formed a candidate, invoked replay, and ultimately passed Official.
The four final replay outcomes agreed with Official. Rstcheck, plasmapy, and starsim passed
their first replay, so replay served only as certification in those episodes.

Pygeo triggered the repair loop. Its first target-state replay failed when pip timed out
while reading package metadata from `files.pythonhosted.org`. The same active session
changed the complete program to use bounded pip timeouts, retries, and backoff. The second
replay and Official evaluation passed. This is evidence that replay can repair an
executable deployment-robustness defect; it is not evidence of a newly inferred package,
version, ABI, or platform compatibility constraint.

## Resources

Across all four pairs, A used 157 model requests, 4.47M tokens, 190 shell operations, and
5,213 seconds of generation. B used 129 requests, 2.10M tokens, 120 shell operations, and
3,769 seconds. The aggregate reductions are 18% requests, 53% tokens, 37% shell operations,
and 28% generation time.

Those totals are misleading without paired dispersion. B minus A request differences are
`+7, -6, -46, +17`, with median `+0.5`; generation-time differences are `+332, -71,
-2,017, +314` seconds, with median `+121`. The total advantage is dominated by pygeo,
while B is slower on two of four pairs. This batch therefore does not establish a general
efficiency improvement.

## Deployment Completeness

Official Pass is import-oriented and does not identify a unique environment quality.
Both rstcheck and plasmapy pairs installed project development dependencies. Both pygeo
programs mixed real packages with placeholders for optional native modules, so they are
Official-valid without demonstrating a complete functional runtime. Starsim A aliased
legacy package names to `starsim`; B installed the real `stisim` and `hpvsim` packages.
Both passed Official, but B delivered the more complete dependency state. Completeness
must remain a separate outcome rather than silently redefining benchmark success.

## Combined Development Evidence

Combining this batch with the prior outcome-independent qualification gives A `6/8` and
B `7/8`: six both-pass, one B-only, zero A-only, and one both-fail pair. Exact McNemar
remains `p=1.0`. Seven of eight B episodes formed candidates; their final replay and
Official outcomes agreed `7/7`. Across ten completed replays, five passed first and two
episodes produced feedback-conditioned repairs: one compatibility/workspace repair in
`importlib_metadata`, and one network-robustness repair in `pygeo`.

This is solid mechanism-fidelity evidence, but still weak effectiveness evidence. The
sole B-only Official pass was a first-replay pass and cannot isolate replay-conditioned
repair from stochastic search.

## Decision

The preregistered retention rule is satisfied: treatment success did not regress, all
final replays agreed with Official, and one feedback-conditioned repair occurred. The
algorithm remains unchanged. Random Dev scaling should now stop because ceiling-heavy
cases consume evidence without testing the main claim. The next experiment must use a
fixed strong-baseline Official bad-case stratum selected from the pre-existing census,
before treatment outcomes are examined. No network rule or case-specific compatibility
rule is added from this batch.

Machine-readable evidence is in
`experiments/validations/envsolve_pro_v2_target_state_replay_development_v2_result.json`.
