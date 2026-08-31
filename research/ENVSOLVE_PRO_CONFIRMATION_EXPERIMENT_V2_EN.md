# EnvSolve-Pro Protected Canary Protocol V2

Status: review proposal. It does not authorize opening a protected case.

## Estimand and Frozen Arms

The primary hypothesis is that in-session complete-program target-state replay improves
paired Official Pass@1 for a **strong** Agent. A weaker-backbone stratum tests mechanism
replication and capability dependence; strata are never pooled.

`A-F` is one continuous Agent session with ordinary construction feedback. `B-FR` is the
identical runner, prompt, tools, model, and operating allowance, with one difference: the
Agent may execute its complete program from the target initial state, receive failure in
the same session, and deliver only the exact replay-passing program. Official feedback is
post-episode only. Neither arm contains external constraint state, frontier, checkpoint
search, handoff policy, package rules, or cross-case memory.

## Data, Identity, and Isolation

The protected Canary is the existing 20-line `experiments/cases/canary20.jsonl`, selected
outcome-blind on 2026-07-13 as the first 20 SHA256-ranked Official-train identities after
excluding Dev-5. Its membership and line order were fixed before this study; exposure
audits through 2026-08-30 reserve it for unseen estimation. Case content remains unopened.

Positions 1--10 are complete pairs on Spark; 11--20 are complete pairs on AgentHub. Odd
positions run A then B and even positions B then A. A pair never crosses hosts. Every
episode receives an independent cache cloned from the same pre-run package-cache base,
so the first arm cannot warm the second arm's cache. The Mac only schedules and analyzes.

Execution identities and launch blockers are:

| Stratum | Exact identity | Fixed allowance | Launch state |
|---|---|---|---|
| Weaker | `deepseek/deepseek-v4-flash-0731`; OpenRouter; DeepInfra only; no fallback | 120 model requests; 18,000 s generation; 1,800 s command; 600 s provider request; 2,400 s Official | Qualified on consumed Dev |
| Strong | `gpt-5.6-sol`; Codex CLI `0.151.0-alpha.7.2`; existing `CodexCliRunner`/`EnvSolveProMinimalBRunner`; native Codex account backend | 18,000 s generation; 1,800 s command; 2,400 s Official | **Hard launch gap:** consumed-case adapter qualification is pending, and the current runner does not enforce the configured per-turn request guard. No strong Canary episode starts until the same-runner interface and one fixed request policy are demonstrated without creating a new runner. |

Tokens and money are measurements, not stopping thresholds. A scientifically eligible
episode that starts reasoning but never submits, reaches its operating guard, or causes a
program timeout is an algorithm failure.

## Feasible Schedule

Consumed timings give weak-model p50/p90 generation times of 16.0/30.2 minutes (8
episodes) and strong-model p50/p90 of 19.7/51.0 minutes (10 episodes). The failure-enriched
weak Bad6 averaged 51.5 minutes, so scheduling uses 70 minutes per episode including
replay and Official overhead rather than the optimistic median.

| Phase | Work and order | Duration target |
|---|---|---:|
| 0 | On consumed Dev only: qualify `gpt-5.6-sol`, resolve the request-policy gap, verify independent cache clones on both hosts | 3--6 h |
| 1 | Core Canary only: 40 episodes per host, at most 2 concurrent lanes per host; arms within a pair remain sequential; no external baseline shares either host | earliest 11 h, p90 plan 24 h |
| 2 | Seal paired Official outcomes and infrastructure adjudication | 1 h |
| 3 | Run qualified Repo2Run/EnvBench/Codex end-to-end baselines after core results are sealed; begin blinded OCO annotation in parallel | does not delay the core decision |

Thus the earliest core decision is approximately 15 hours after approval; the planned
latest under measured p90 load is 30 hours. Provider or host outages are reported as
schedule deviations rather than hidden by higher concurrency.

## Endpoint, Censoring, and Decision Branches

The endpoint is paired Official Pass@1, reported separately by backbone with paired
transition counts, effect interval, and exact McNemar test. With 20 pairs and no
control-only success, at least six treatment-only successes are required for a two-sided
exact McNemar p-value below 0.05; a larger p-value is not interpreted as proof of no
effect, and the interval and detectable effect are reported.

Infrastructure censoring is limited to source acquisition, host interruption,
authentication, or provider outage before the first model response, plus evaluator crash
or transport failure independent of the submitted program. The former may rerun the same
case/arm; the latter may evaluation-only rerun the exact program. A valid Official Fail,
agent-caused timeout, or post-start non-submission is failure. No case is replaced.

The Canary has four predeclared branches:

- **Advance:** treatment-only exceeds control-only, no shared measurement defect occurs,
  and at least one genuine replay activation is observed. This is a promising direction,
  not a confirmatory success claim; it permits the unchanged method to enter the 100-case
  Official Test.
- **Tie:** replay--Official agreement may support reliability, but the Canary provides no
  effect evidence. The expensive Test does not open unless the user explicitly elects to
  narrow the confidence interval.
- **Negative:** control-only exceeds treatment-only. The success direction for that
  backbone is rejected and its Test stops.
- **Shared measurement defect:** the entire Canary study is invalid. It is not repaired
  and continued on the same protected identities.

Only the 100-case Official Test carries the confirmatory success-rate claim. The strong
stratum is primary; the weaker stratum explains replication or capability dependence.
Reliability, activation, candidate formation, completeness, time, requests, Tokens,
traffic, disk, and memory are secondary outcomes and cannot override Official success.

## Baselines and Post-Opening Rule

Only same-runner `A-F` versus `B-FR` is a causal replay comparison. Repo2Run and EnvBench
FreeAgent with the same DeepSeek model, and native Codex with `gpt-5.6-sol`, remain
end-to-end system comparisons because their prompts, tools, and recovery semantics differ.
External adapter qualification uses consumed Dev only and cannot delay the core Canary.

After the first Canary episode starts, the algorithm, prompt, tool schema, replay timing,
submission semantics, validity boundary, model identity, allowances, and OCO rules do not
change. Any later mechanism is a separate study and cannot be written back into this
Canary. Two annotators must independently label blinded OCO packets before the final
paper reports a failure distribution, but annotation does not block paired generation.
