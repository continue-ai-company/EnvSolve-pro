# EnvSolve-pro P5 Mechanism Casebook v1

## Scope

This document records the mechanism value of three consumed Dev cases. It is not an
effectiveness table and supports no held-out, significance, or leaderboard claim. Any
repair must first become a repository-independent mechanism, pass synthetic and regression
tests, and be frozen before evaluation. Repository, module, and provider names are evidence
instances rather than admissible rules.

## 1. `langchain-ai/langgraph`

### Observations

- At V2 causal candidate 2, the complete internal frontier contained ten module roots and
  10,409 characters, but the model-visible state was replaced by a whole-object truncation
  wrapper. The frozen analyzer could not read `causal_roots`.
- The root-first projection needs 6,095 characters on the same historical state, retains
  all ten roots, and reports zero omitted roots.
- An independent V2 flat trajectory repeatedly observed Python 3.13 exceeding PyO3's 3.12
  maximum. Eight distinct candidates still searched locally over Rust, headers, maturin,
  and package patches instead of switching runtime.
- The V2 causal run reached internal certification but failed officially on one
  missing import. Pyright also emitted roughly 1,700 API/type mismatches, but they
  are non-scoring and outside the current optimization target.

### Three-layer diagnosis

- **Observation:** raw logs contain the exact runtime boundary, but growing history does not
  ensure that a strong model treats it as the dominant contradiction.
- **Constraint:** causal compression exists only if the model-visible projection remains
  structured; a richer posthoc state cannot substitute for the historical input.
- **Operation:** the current repair is evaluated only on whether it closes the
  official missing-import target. Broader dependency-quality diagnostics are not
  folded into mechanism selection.

## 2. `nonebot/nonebot2`

### Observations

- V2 causal persisted `PyO3: Python 3.13 > 3.12` at candidates 2 and 3. Candidate 3 switched
  runtime and the episode later passed officially; the compact projection retains the root.
- V2 flat kept Python 3.13 across eight candidates despite repeated exact diagnostics,
  adding Rust, headers, maturin, and environment variables until its candidate cap bound.
- The old verifier treated `if sys.version_info < (3, 11): import tomli` as active on Python
  3.13. Tuple-guard evaluation is generic control-flow semantics, not a case rule.
- The provider is not strictly deterministic at the same seed: another flat trajectory
  switched to Python 3.11 before a network timeout.

### Three-layer diagnosis

- **Observation:** the decisive signal already exists; attention allocation in raw history
  is the dominant issue.
- **Constraint:** a persistent, compact, revisable root may help a strong model leave local
  search, but one pair cannot identify a causal gain.
- **Operation:** the treatment leaves actions open and does not force a runtime operation;
  the model still writes the complete deployment program.

## 3. `conan-io/conan-package-tools`

### Observations

- Many surface import failures collapse to one runtime `six.moves` missing-name root,
  demonstrating surface-to-root amplification. The causal run still failed to close it.
- Flat candidate 8 had far fewer active conflicts than retained candidate 3 but contained
  Unknown state, making it ineligible under the frozen admissibility contract.

### Three-layer diagnosis

- **Observation:** executable missing names are closer to causes than individual import paths.
- **Constraint:** correct compression does not imply resolvability; it reduces duplicated
  symptoms and makes failure measurable.
- **Operation:** ranking Unknown against active conflicts may affect terminal release, but it
  requires a separate consumed-case replay ablation and is not changed here.

## 4. Cross-case conclusions

1. Exact candidate duplication is not the primary failure; all V2 retry3 scripts differ.
2. Raw-history failures exhibit local search and attention allocation: exact compatibility
   boundaries are present but do not become stable state variables.
3. For strong models, structured constraints should be external, revisable, root-first
   cognitive state rather than a closed planner.
4. Model-input integrity precedes effect analysis; one whole-object truncation among sixteen
   causal decisions invalidates V2.
5. The next batch tests compact-projection integrity only, followed by multi-block pairing
   on consumed cases to address provider nondeterminism.
