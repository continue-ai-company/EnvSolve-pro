# Goal-Contract Evidence-Anchor Qualification V1

## 1. Scope

This is a consumed five-case EnvBench Dev qualification of two frozen methods:

- explicit state: `envsolve-pro-goal-contract-evidence-anchor`;
- control: `envsolve-pro-goal-aware-raw-evidence-anchor`.

Both methods used `deepseek/deepseek-v4-pro`, the same public executable goal,
constraint-routed repository evidence, retained admissible anchor, open Bash action
space, fresh candidate environments, and terminal-only Official evaluation. The only
intended difference was explicit constraint state versus bounded raw goal history.

Official success is exactly `exit_code == 0 && issues_count == 0`. `error_count` and
`warning_count` are descriptive diagnostics and do not affect the score.

## 2. Frozen Outcomes

| Case | Explicit state | Raw history | Explicit candidate slots / tokens / generation wall | Raw candidate slots / tokens / generation wall |
|---|---|---|---:|---:|
| River | Unknown: command timeout before Official evaluation | Unknown: feedback exceeded context contract | 4 / 56,699 / 2,970.3 s | 11 / 215,561 / 12,958.5 s |
| LitGPT | Unknown: command timeout before Official evaluation; best observed goal had 2 findings | Official Fail: 2 issues | 3 / 42,150 / 2,477.6 s | 12 / 220,855 / 5,021.6 s |
| ILAMB | Official Pass | Official Pass | 5 / 98,346 / 2,106.8 s | 6 / 105,771 / 4,089.0 s |
| Flask-Security | Official Pass | Official Pass | 3 / 41,636 / 470.3 s | 3 / 46,510 / 1,935.2 s |
| Starsim | Official Pass, integrity-invalid | Official Pass, integrity-invalid | 4 / 74,785 / 627.1 s | 4 / 85,151 / 1,365.2 s |

The ILAMB explicit result is the preregistered replacement
`pro-goal-anchor-qv1-c03-ilamb-exp-replacement1`. The earlier run was terminated by an
experimenter monitoring race after a new request had already started and is classified
as experimenter-censored, not provider-censored.

Starsim is excluded from scientific effect analysis. Both terminal scripts made missing
module names importable by symlinking them to `starsim`; this can satisfy the benchmark
surface without supplying the named projects. The frozen v1 pre-execution guard rejected
handwritten import modules but did not reject this equivalent alias construction.

Post-qualification integrity v2 now rejects this behavior twice: the open-program
validator blocks symbolic links into Python search paths before execution, and both
internal verifier paths audit the active interpreter after execution. This repair does
not retroactively change or admit either historical Starsim result.

## 3. Descriptive Aggregate

Across the five scheduled method outcomes, explicit state used 19 candidate slots, 20 model
requests, 313,616 tokens, and 8,652.1 seconds of generation wall time. Raw history used
36 candidate slots, 37 requests, 673,848 tokens, and 25,369.5 seconds. These are reductions
of 47.2%, 45.9%, 53.5%, and 65.9%, respectively.

These totals are descriptive, not a causal efficiency estimate: River and LitGPT have
different terminal censoring, provider latency has high variance, and Starsim is
integrity-invalid.

The two integrity-valid pairs where both methods reached Official Pass are ILAMB and
Flask-Security. Explicit state used 8 versus 9 candidates, 139,982 versus 152,281 tokens,
and 2,577.1 versus 6,024.2 seconds. This is consistent with lower search burden, but two
consumed pairs cannot establish an effect.

Gross Official outcomes are three Passes for each method, no scored Fail for explicit
state, one scored Fail for raw history, and two versus one runs without Official
evaluation. After integrity exclusion, the evidence does not support a success-rate
claim.

## 4. Mechanism Findings

1. Explicit state often reached the same useful finding frontier with fewer candidates
   and less model context, without restricting the strong model's open action space.
2. Small state repairs repeatedly paid the cost of replaying a large installation
   prefix. This was dominant on River and ILAMB.
3. Raw history produced no-progress candidates and eventually exceeded its feedback
   context on River.
4. Frozen v1 could not observe output latency or provider retries at the attempt level;
   one Flask-Security raw response took roughly thirty minutes despite a local repair.
5. Frozen v1 integrity rejected direct file stubs, but symlink import aliases bypassed
   the same semantic boundary.
6. Repository effect audit correctly rejected a dependency installation that upgraded
   and rewrote the checked-out Starsim source tree.
7. Adapter-created `build_output/` can collide with setuptools flat-layout discovery,
   so benchmark workspace preconditions must be represented explicitly in repository
   build evidence.

## 5. Decision

No new dependency recipe is justified. The next version has two ordered stages:

1. **Measurement and integrity repair:** integrity v2 now rejects the observed import
   alias at admission and runtime. The v1.1 resource ledger disables hidden SDK retries,
   separates logical calls from transport attempts, shares one deadline across attempts,
   and distinguishes experimenter censoring from completed provider failures. This is
   synthetic-qualified by
   `experiments/validations/pro_provider_attempt_recovery_v2_results.json` and still
   requires a live provider canary.
2. **Operation-layer hypothesis:** branch from an immutable, effect-valid environment
   prefix for suffix repairs, while always certifying the assembled full program from a
   clean environment before Official evaluation. Replacement remains available when a
   repair must revise the prefix.

The second stage targets the replicated contradiction between state-level minimal repair
and execution-level full replay. It must be shared by explicit and raw-history methods
when testing representation effects, and it requires repository-disjoint qualification.

The auditable run-level values and exclusions are stored in
`experiments/validations/pro_goal_contract_evidence_anchor_qualification_v1_results.json`.
