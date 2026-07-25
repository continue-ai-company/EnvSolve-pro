# EnvSolve-Pro Goal Contract Casebook v1

## Scope

This casebook records consumed development evidence for the goal-contract line. It supports
mechanism qualification and debugging only. It is not a held-out effectiveness estimate
and must not be pooled into a leaderboard claim.

## 1. `jaraco/irc` (`c2`)

- `EnvSolve-Pro goal-contract-v1` completed generation and terminal evaluation.
- Official Pass was true with bootstrap exit zero and zero scoring issues.
- This run establishes end-to-end compatibility among the generic goal runtime, the
  EnvBench adapter, candidate release, and terminal evaluation.
- The detailed trajectory remains on Spark and must be audited after SSH service is
  restored. Until then, this case does not identify whether success required a repair.

## 2. `censys/censys-python` (`c10`)

### First mechanism run

The first candidate ran `poetry install` and activated the resulting environment. The
public executable goal then returned exactly one failing finding:
`sphinx_rtd_theme` was absent in `docs/conf.py`. The Constraint layer admitted a
provenance-linked module requirement and negative fact. The second model call produced a
complete program that additionally installed `sphinx_rtd_theme`; a new fresh environment
passed both the internal goal and Official evaluation with zero scoring issues.

This closes the intended within-case chain:

```text
candidate -> executable goal Fail -> typed obligation
-> revised complete program -> executable goal Pass -> Official Pass
```

### State-consistency repair

Post-run audit found that the goal was satisfied while the historical requirement
remained marked active in the snapshot. This did not affect candidate selection or the
Official result, but it violated the algorithmic state contract and would corrupt future
trajectory learning. Goal evidence now carries a contract-specific evidence scope. A
Pass retires constraints from that exact scope, while unrelated verifier evidence is
preserved. The fix passed the full regression suite and a fresh c10 execution; both the
old requirement and fact finish as `superseded`.

### Same-model controlled pair

`envsolve-pro-goal-aware-raw` receives the same model, public goal, verifier, open program
interface, fresh environments, retention rule, and execution limits, but hides
`constraint_conflicts`, active requirements, and causal frontiers from the model. It sees
the original candidate and goal report instead.

Both methods failed on the first candidate, installed `sphinx_rtd_theme` in the second,
and passed officially. In this single stochastic pair:

| Method | Attempts | Official Pass | Total tokens | Wall-clock |
|---|---:|---:|---:|---:|
| goal-aware raw history | 2 | yes | 15,314 | 223.5 s |
| explicit goal constraints | 2 | yes | 17,494 | 361.1 s |

The explicit-state candidate also installed an unnecessary `attrs` package. These values
are descriptive, not an efficiency claim.

## 3. Decision

1. c10 supports executable goal visibility and iterative repair.
2. c10 does **not** support an incremental benefit from typed constraint visibility; the
   strong model repaired the raw goal report equally well.
3. The raw-history baseline must receive the complete bounded goal report rather than
   lose findings inside installation logs. The verifier now preserves the raw report and
   allocates it a larger model-visible section.
4. The next consumed pairs must stress multiple findings, cross-round persistence, or
   feedback compression. `astropy/extension-helpers` (`c15`) and
   `nonebot/nonebot2` (`c16`) are the next mechanism cases.

## 4. `astropy/extension-helpers` (`c15`)

### Invalid diagnostic pair

Both methods first observed four missing-import findings: `pkg_resources`, `numpy`,
`helpers_test_package`, and `helpers_test_package.compiler_version`. The explicit-state
method's second candidate resolved three of them, and the next executable report
contained only `pkg_resources`. However, the stored Constraint state still marked the
three absent requirements as violated. The implementation retired a contract scope on
Pass but did not distinguish an exhaustive failing snapshot from partial evidence.

This is a state-machine defect, not evidence for or against explicit constraints. The
raw-history run also explored several invalid setup variants, including an obsolete
`setuptools` pin, but the pair was interrupted once the defect was identified. Both runs
are `invalid-for-comparison` and must never enter an effectiveness table.

### Minimal repair

Goal reports now declare `finding_set_complete`. A complete report may retire prior
same-scope constraints absent from the new finding set. A partial report may only add or
refine evidence; absence is not treated as resolution. The EnvBench Pyright scan emits a
complete finding set, while a capability short-circuit emits a partial set. Synthetic
tests cover both transitions, and the full suite passes with 517 tests, 2 skips, and 75
subtests.

### Integrity incident and protocol v2

The first explicit-state rerun after the snapshot repair reached Official Pass in five
candidates, but its final program directly created empty `helpers_test_package` modules
under `/tmp` and exposed them through `PYTHONPATH`. This violates the declared
no-fake-module rule, so the result is diagnostic only and remains invalid for
effectiveness comparison. The paired raw-history run was interrupted once the integrity
mismatch was confirmed.

Protocol v1 had an inconsistent boundary: it broadly prohibited path injection even
though the open-program validator allowed legitimate repository and installation path
configuration. Protocol v2 instead permits real environment-path configuration while
forbidding synthetic import artifacts and goal shadowing. A small benchmark-independent
admission guard now rejects direct shell creation or copying of importable artifacts
such as `.py`, `.pyi`, `.pth`, and `.so`; normal package and build tools remain available,
including temporary `setup.py` build drivers. The exact cheating candidate is rejected
by the new guard, and targeted plus full regression tests pass.

### Source-routed evidence and retained anchor

The integrity-valid reruns exposed two further failures. First, a goal finding named a
missing module but did not expose the repository-local code that explains how that
module should be produced. Second, later candidates could solve a newly visible finding
while forgetting dependencies that an earlier candidate had already satisfied. These
are partial-observation failures rather than missing shell expressivity.

`goal-contract-evidence-anchor-v1` adds two small state mechanisms:

1. each active finding routes a bounded, read-only view of its exact source location and
   related subject occurrences into the Constraint layer;
2. the best complete, integrity-admissible candidate is retained as an explicit anchor,
   and the Operation layer is asked to preserve it while merging subsequent repairs.

The action space remains an open Bash program. Repository evidence is selected by
current executable findings rather than exposed as an unrestricted browsing tool, and
the anchor is evidence-backed state rather than a hand-written recipe.

### Valid mechanism result

Run `pro-goal-contract-evidence-anchor-v1-c15-mechanism1` passed both the internal goal
and Official evaluation with zero scoring issues. The useful trajectory was:

- candidate 4 established a valid four-finding baseline;
- candidate 5 resolved `numpy` and became the retained anchor;
- candidates 6--8 attempted protected configuration or a synthetic artifact and were
  rejected by the integrity boundary;
- repository-routed evidence led candidate 9 to the project's real
  `_extension_test_package` build helper;
- candidate 10 corrected that build path and reduced the complete finding set to
  `pkg_resources` and `numpy`;
- candidate 11 merged the valid build repair with the retained dependencies and reached
  zero findings in a fresh environment.

The run used 11 candidates, 13 model requests, and 261,722 tokens. These are descriptive
development measurements, not a claim of efficiency. The run demonstrates that source
routing plus retained state can close this hard mechanism case without a fake module or
goal suppression. Because c15 directly motivated both mechanisms, it remains consumed
development evidence and cannot estimate generalization.

The next controlled pair uses consumed case `nonebot/nonebot2` (`c16`) and compares
explicit constraints with raw history while holding the public goal, source evidence,
retained anchor, action interface, model, and limits fixed.

## 5. `nonebot/nonebot2` (`c16`)

### Infrastructure censoring

The first explicit-state attempt completed one candidate and then remained inside a TLS
read during its second OpenRouter request for more than 20 minutes. The OpenRouter health
endpoint remained responsive, no response or request error was recorded, and no second
candidate was produced. The process was interrupted and the run is classified as
`infrastructure-censored`, not an algorithm failure. A new run identifier was used for
the retry.

### Controlled pair

Both methods used `deepseek/deepseek-v4-pro`, protocol v2, the same executable goal,
constraint-routed source evidence, retained admissible anchor, open Bash interface, fresh
environments, and terminal-only Official evaluation. The only intended difference was
the model-visible state: explicit active constraints versus bounded raw goal history.

The explicit-state retry first failed during Poetry setup. Its second candidate used pip
and exposed 35 findings, comprising only `pytest`, `nonebug`, and `tomli`. Candidate 3
installed the repository's local test package plus the remaining dependency and passed.

The raw-history run's first partial Poetry setup exposed 51 findings. Candidate 2 reduced
them to 18 optional-driver findings. One subsequent model response violated the candidate
output schema and was rejected before execution; the next response merged the remaining
drivers and local test package into candidate 3, which passed.

| Method | Executed candidates | Model requests | Official Pass | Total tokens | Wall-clock |
|---|---:|---:|---:|---:|---:|
| explicit goal constraints | 3 | 3 | yes | 40,438 | 482.6 s |
| goal-aware raw history | 3 | 4 | yes | 90,748 | 651.7 s |

Both terminal programs passed integrity audit and Official evaluation with zero scoring
issues. This pair does not show a success-rate advantage or fewer executed candidates.
It is consistent with the narrower hypothesis that explicit state can make a
many-finding repair trace easier for a strong model to consume: the explicit method used
one fewer request and 50,310 fewer tokens. A single stochastic, consumed pair cannot
establish that efficiency effect; replicated repository-disjoint qualification is
required.
