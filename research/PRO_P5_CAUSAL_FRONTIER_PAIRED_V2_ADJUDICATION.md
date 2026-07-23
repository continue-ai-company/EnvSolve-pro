# P5 Causal Frontier V2 Adjudication

## Decision

V2 cannot estimate the effect of flat versus causal-frontier state. The frozen analyzer
exited while reading the model-visible state at LangGraph candidate 2 because
`causal_roots` was absent. An independent posthoc audit confirms a real model-input
contract failure rather than an incidental analyzer crash.

The three causal episodes persisted sixteen model decisions. Fifteen pass digest and
structure checks. The one invalid decision replaced a 10,409-character frontier with a
whole-object truncation wrapper containing neither a root list nor a summary. Under the
preregistered rule, both measurement integrity and effect admissibility are false.

The descriptive Official Pass counts are causal `1/3` and flat `0/3`, but they motivate
continued study rather than an improvement claim. Offline reconstruction cannot repair the
historical experiment because the model did not receive the reconstructed state.

## Minimal follow-up

V3 changes only generic semantics: a root-first bounded structured projection and tuple-
guard evaluation for `sys.version_info`. An integrity canary first runs on the same three
consumed cases, with Official Pass excluded from its gate. A consumed-case multi-block pair
is frozen only after measurement passes, while fresh Dev remains untouched.

The machine-readable decision is
`experiments/validations/pro_p5_causal_frontier_paired_v2_adjudication.json`.

