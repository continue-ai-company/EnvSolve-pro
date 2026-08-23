# EnvSolve-Pro V2 Target-State Replay Bad-6 Results

Status: failure-enriched development stress test complete

## Question

Can a free Agent repair defects hidden by its construction environment when it can replay a **complete bootstrap** from
the target image and a fresh checkout, with the raw failure returned to the same active session?

This is not a held-out test. The six cases came only from a pre-existing census of gpt-5.5 Codex Official failures, and
the cases, order, model, provider, seeds, image, prompts, limits, and analysis were fixed before execution. The result can
guide the next algorithmic hypothesis; it cannot support population, significance, generalization, leaderboard, or SOTA
claims.

## Methods

- **A-F:** one continuous DeepSeek Flash Agent session with ordinary execution feedback and final full-bootstrap delivery.
- **B-FCsR:** the same interface plus repeatedly callable whole-program target-state replay. Counterexamples return to the
  same session, and only a replay-passed program can be delivered.
- **minimal-H:** the evaluator and repository integrity boundary shared by both arms. It is harness infrastructure, not a
  deployment strategy.

The EnvBench Official evaluator was called once after each episode and never supplied online repair feedback.

## Primary Result

End-to-end success requires both candidate formation and Official Pass. An eligible non-submission is deployment failure,
not censoring.

| Case | A-F | B-FCsR | Mechanism |
|---|---:|---:|---|
| quacc | Fail | Fail | A hit a download timeout; B search expanded before candidate formation |
| ajenti | Fail | Fail | Both reached zero missing imports but failed to deliver in time |
| clarity | Pass | Pass | B passed its first replay; no repair |
| HA-Battery-Notes | Pass | Pass | B repaired build isolation through Fail-to-Pass replay |
| hark | Fail | Pass | B repaired fresh-checkout Git ownership through Fail-to-Pass replay |
| micropy-cli | Fail | Pass | B formed a candidate and replay-repaired a dependency conflict |

A passed `2/6`; B passed `4/6`. The paired table has two both-pass, two B-only, zero A-only, and two both-fail cases.
The exact two-sided McNemar value is `p=0.5`. The direction is promising, but six pairs cannot establish a stable effect.

Both arms formed candidates on `4/6` cases. All four B candidates invoked replay: seven replays yielded one first-pass
certification and three Fail-to-Pass repairs. Final replay and Official outcomes agreed on `4/4` delivered B candidates.

## Three-Layer Failure Analysis

### Observation: what did the target state reveal?

Construction can hide facts that appear only under a fresh target state. HARK A first saw Git ownership failure in the
terminal Official checkout; B exposed the same failure during internal replay. HA-Battery-Notes exposed unavailable
Cython under build isolation, while micropy-cli exposed a resolver conflict among pinned dependencies.

quacc demonstrates ambiguity. A failed because the Pyright wheel download and extraction exceeded a 30-second UV network
timeout. Official correctly records a failure, but the trace does not support a LAPACK or package-version diagnosis.

### Constraint: what was actually missing or conflicting?

HARK provides the cleanest executable constraint: before an editable install in the target checkout, Git must accept the
current root as a safe directory. The same session added one operation and replayed. HA-Battery-Notes required Cython to
be visible outside isolated build dependency resolution; micropy-cli required a non-conflicting dependency set.

These case-local findings are not promoted into cross-repository package rules. In the minimal method they remain grounded
facts interpreted by the current active Agent session.

### Operation: why did eligible episodes still fail?

The unsolved bottleneck occurs before replay. quacc B explored optional scientific packages, native builds, and multiple
environments through request 120 without producing a candidate.

ajenti is more revealing: A reached zero missing imports at requests 103-104, and B at request 100. Both continued to
pursue broader runtime completeness and ended at request 120 without submission. micropy-cli A likewise observed zero
missing imports repeatedly but did not deliver.

The dominant problem is therefore not another package rule. It is **successful-candidate retention and stopping**: the
Agent conflates the Official objective with broader deployment completeness and can lose an already sufficient path while
continuing optional exploration.

## Causal Case

HARK is the cleanest causal rescue:

1. A failed Official because a fresh checkout triggered `dubious ownership`.
2. B's first internal target replay reproduced the same error.
3. The same active session added `git config --global --add safe.directory "$REPO_ROOT"`.
4. The second replay passed, followed by Official Pass.

This supports a narrow claim: **target-state counterexamples can repair complete-program defects hidden during
construction.** It does not yet establish candidate-formation or population-level gains.

## Path Quality

micropy-cli B passed the preregistered minimal boundary and Official, so its primary label remains Pass. Its program also
created an untracked `micropy/cli.py` re-exporting the real application and empty MicroPython `.pyi` stubs. This is not an
evaluator modification or an empty application-module fake, but it exposes a separate environment-purity and completeness
question. quacc A likewise created a synthetic `torch` import stub.

Official success, deployment completeness, environment purity, and path cost must therefore be reported as separate axes,
not collapsed into a post-hoc gate.

## Resources

| Metric | A-F | B-FCsR | B vs A |
|---|---:|---:|---:|
| Model requests | 416 | 448 | +7.7% |
| Provider attempts | 438 | 464 | +5.9% |
| Tokens | 16,127,687 | 17,066,670 | +5.8% |
| Tool results | 450 | 446 | -0.9% |
| Endpoint time | 19,138 s | 21,124 s | +10.4% |

B improved successes in this batch but did not reduce aggregate resources. Tokens, time, and commands are measured
outcomes, not hard success thresholds; no efficiency claim is supported.

## Decision

Retain minimal target-state replay: it addresses hidden target-state failures **after candidate formation**, with HARK as
direct causal evidence. The dominant unresolved problem is now candidate formation and stopping.

The next simple hypothesis is to preserve the first executable Official-equivalent candidate and replay it before optional
completeness or cost exploration. Later exploration may improve the path but must not erase a viable candidate. Success,
completeness, and resource cost remain separate outcomes. This hypothesis requires discussion and a new fixed development
batch; the consumed Bad-6 cases must not become package-specific tuning examples.

The machine-readable result is
`experiments/validations/envsolve_pro_v2_target_state_replay_screened_bad6_v1_result.json`.
