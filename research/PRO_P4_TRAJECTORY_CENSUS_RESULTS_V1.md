# P4 Trajectory Census Results

## Scope

P4 is a consumed-Dev diagnostic, not an effectiveness experiment. Two metadata-blind
samples of eight repositories were executed with the same frozen EnvSolve-pro
implementation. The independent replication was analyzed separately before pooling.
Two dependency-download timeouts in the replication were classified as infrastructure
censoring and replaced by provenance-linked fresh reruns under the frozen protocol.

## Result

| Sample | Success | Evaluator | Observation | Closure | Operation | Unique leader |
|---|---:|---:|---:|---:|---:|---|
| Primary, n=8 | 1 | 1 | 0 | 4 | 2 | Closure |
| Replication, n=8 | 3 | 0 | 0 | 1 | 4 | Operation |
| Secondary pooled, n=16 | 4 | 1 | 0 | 5 | 6 | Operation |

The preregistered replication criterion failed: the primary closure leader did not
remain the leader in the independent sample. Both samples nevertheless support the
broader prediction that operation nonviability plus closure gaps form a strict majority
(`6/8` and `5/8`; pooled `11/16`). The robust target is therefore the interface between
constraint closure and viable operations, not either blocking label in isolation.

## Mechanism Audit

Three cross-repository mechanisms explain most failures:

1. **Runtime and platform frontiers are missing or not induced.** LangGraph repeatedly
   exposed a Python 3.13 versus PyO3 3.12 boundary. Geoapps and RLberry exposed ARM lock
   or wheel incompatibilities. Base observation recorded Python but not machine
   architecture, and exact errors did not become persistent root constraints.
2. **Flat obligations amplify surface symptoms.** A single Conan import root expanded
   into many transitive module obligations. Optional documentation, scripts, negative
   tests, and integration suites dominated scVelo, Python-holidays, and Luigi. The state
   lacked causal parentage and scope priority.
3. **The trust boundary is both over-strict and spoofable.** A valid PyRollbar virtual
   environment named `env` was rejected because only `venv/.venv` were recognized.
   Extension-helpers lost a generated source file to the same effect policy. Conversely,
   Sphinx-Gallery created a fake distribution and tool shim that prevented Pyright from
   running while the raw evaluator reported zero issues.

These are not package-specific errors. They show that an executable observation must
carry scope, causal provenance, platform identity, and trust level before it can safely
become an operation obligation.

## Sensitivity And Budget

The preregistered primary category for Sphinx-Gallery remains `closure_gap`. An
integrity-aware sensitivity analysis reclassifies it as operation nonviability, producing
a `3-3` primary tie between closure and operation. The raw evaluator's `pyright=null`
record is never counted as success.

Twelve of sixteen cases reached the five-candidate cap. The cap therefore censored search
and is unsuitable as the main success-first protocol. Future comparisons use a shared
wall-clock/container boundary with generous nonbinding candidate and token limits;
tokens, requests, candidates, and time remain reported efficiency metrics.

## Decision

P5 will not add more package heuristics or optimize closure alone. Harness correctness
and protected evaluation are repaired first. The next algorithmic hypothesis is one
minimal **causal constraint frontier**: preserve raw evidence, induce a small set of
provenance-linked root constraints, attach scoped surface obligations to those roots,
and expose viable operation choices without closing the strong model's action space.
It must first pass synthetic and consumed mechanism tests, then a preregistered fresh-Dev
paired comparison.
