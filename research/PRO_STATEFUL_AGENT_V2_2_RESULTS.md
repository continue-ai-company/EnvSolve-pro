# EnvSolve-Pro Stateful-Agent V2.2 Dev-5 Results

## Status

This is a consumed-development mechanism study, not held-out evidence. The five
repositories and all outcomes may be used for failure analysis and V2.3 design, but
must not be reused to claim effectiveness.

The compared methods used the same strong model, public executable goal, terminal-only
official evaluator, fresh candidate replay, and resource settings:

1. strong single-session goal-aware Codex baseline;
2. same-model multi-session raw-feedback loop;
3. EnvSolve-Pro stateful-agent V2.2.

## Aggregate Results

| Condition | Official Pass | Wall time (s) | Commands | Input tokens | Output tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Strong goal-aware baseline | 5/5 | 3,990.6 | 132 | 4,363,200 | 62,772 | 32,161 |
| Raw-feedback loop | 5/5 | 6,387.0 | 142 | 9,999,463 | 96,930 | 56,666 |
| Structured V2.2 | 4/5 | 6,386.6 | 119 | 8,059,643 | 81,164 | 46,402 |

Relative to raw feedback, V2.2 used 16.2% fewer commands and 19.4% fewer input
tokens, but did not reduce wall time and lost one Official Pass. Relative to the strong
single-session baseline, it used 60.0% more wall time and 84.7% more input tokens.
The baseline is the clear winner on this diagnostic sample.

EnvBench `errorCount` is not a scoring field. Official success is bootstrap success
plus zero `reportMissingImports`; other Pyright errors remain diagnostic only.

## Case-Level Evidence

| Repository | Strong | Raw | V2.2 | Decisive observation |
| --- | ---: | ---: | ---: | --- |
| aqtinstall | Pass | Pass | Pass | The loop added no success value; structured feedback reduced neither attempts nor wall time materially. |
| moat-mqtt | Pass | Pass | Fail | A blanket source-provenance veto rejected legitimate namespace composition from sibling distributions. |
| smart_open | Pass | Pass | Pass | The strong baseline preserved an intentional failing-import fixture; stateful variants found a weaker name-only workaround. |
| molecularnodes | Pass | Pass | Pass | Official static visibility can accept a runtime-incompatible binary, exposing a benchmark-versus-execution semantic gap. |
| plotnine | Pass | Pass | Pass | 572 surface findings collapsed to 15 dependency roots, but raw reports still produced 2,557 state events and roughly 630 KB model inputs. |

## Failure Analysis

V2.2 made three generic mistakes.

First, it observed the complete public goal before the strong model had inspected the
repository. This paid a large diagnostic cost even on first-attempt successes and
anchored the model on surface symptoms. Second, it grouped findings only in a derived
view while retaining complete reports in the model projection and converting every
surface finding into two solver events. Third, it promoted inferred provenance rules to
hard vetoes. The `moat-mqtt` false rejection shows that a plausible semantic heuristic
cannot have more authority than the official goal.

The successful parts are narrower. A fresh-container feedback loop is executable;
root grouping can focus the model; and the open operation program lets a strong model
discover solutions outside a fixed action schema. These components remain.

## V2.3 Decision

V2.3 is the smallest correction:

- **Observation:** the first model action uses repository inspection only. Executable
  goal feedback is created after a submitted candidate fails.
- **Constraint:** complete findings remain in an immutable audit archive, while the
  solver and model receive root obligations with counts and representative samples.
  Only the official goal and shared experimental admissibility rules are hard;
  provenance and semantic interpretations are advisory.
- **Operation:** the strongest agent retains an open terminal and unrestricted
  cumulative deployment program.

The candidate goal and integrity audit now resolve `python` through the same shell
environment. A certified terminal candidate has no repair-candidate assessment. V2.2
remains frozen as a structured baseline.

V2.3 requires new repository-disjoint cases. The present Dev-5 may validate regression
tests and explain the design, but cannot estimate the new method's success rate.
