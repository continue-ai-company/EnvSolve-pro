# EnvSolve-Pro Protected Canary Protocol V3

Status: final launch contract for review. Protected execution remains unauthorized.

## Claim and Arms

The **primary hypothesis** is that in-session complete-program target-state replay
improves paired Official Pass@1 with strong `gpt-5.6-sol`. DeepSeek V4 Flash is a
secondary mechanism-replication stratum; it tests capability dependence and cannot rescue
a null or negative strong-model result.

`A-F` is one continuous Agent session with ordinary construction feedback. `B-FR` is the
same runner, prompt, tools, model, and time allowance, with one additional interface: it
may execute the complete candidate from the target initial state, return the executable
result to the same session, and deliver only that exact replay-passing program. Official
feedback is post-episode only. No external constraint state, frontier, checkpoint search,
handoff policy, package rule, or cross-case memory is present.

## Data and Fixed Execution Contract

The Canary is the unopened 20-line `experiments/cases/canary20.jsonl`, selected
outcome-blind on 2026-07-13 from Official train after excluding Dev-5. Existing line order
is the case order. Positions 1--10 run as complete pairs on Spark and 11--20 on AgentHub;
odd positions run A then B and even positions B then A. A pair never crosses hosts. Each
episode receives an independent cache derived from the same pre-run package-cache base,
so no arm inherits another arm's warm cache. The Mac only schedules and analyzes.

| Stratum | Exact identity | Shared A/B limits |
|---|---|---|
| Primary strong | `gpt-5.6-sol`; Codex CLI `0.151.0-alpha.7.2`; existing `CodexCliRunner` and `EnvSolveProMinimalBRunner`; native Codex account backend | 18,000 s generation; 1,800 s command; 2,400 s Official |
| Secondary weak | `deepseek/deepseek-v4-flash-0731`; OpenRouter; DeepInfra only; no fallback; existing OpenRouter control and Minimal-B runners | 18,000 s generation; 1,800 s command; 600 s provider request; 2,400 s Official |

Request count, Tokens, and money are measured outcomes, not stopping thresholds. If a
runner requires numeric request, Token, or cost fields, they are configured above what is
physically reachable within 18,000 seconds and are not scientific limits. Hitting the
generation wall-clock without successful submission is algorithm failure.

## Phase 0: Required Consumed-Dev Qualification

Before Canary access, run one already consumed repository through both models, both arms,
and both hosts: eight non-effect smoke episodes. They must verify the exact identities
above, identical per-stratum A/B time limits, independent cache derivation, fresh
construction state, and post-episode-only Official access.

Strong qualification must additionally show that A-F and B-FR use the same Codex session
interface, B-FR submits at least one complete program to replay, and the replay Pass/Fail
result returns to that active session. It need not improve success. If this cannot be
demonstrated with the existing runners, the strong stratum is **unavailable**; native
Codex cannot replace the causal pair.

The existing TFMA terminal pair must also finish and be sealed. It verifies only the
shared working-directory and exact-delivery semantics. Any common measurement defect
blocks Canary launch; its arm outcomes never count as algorithm-effect evidence and never
revive the rejected frontier.

## Capacity and Schedule

Consumed generation p50/p90 is 16.0/30.2 minutes for weak-model episodes (n=8) and
19.7/51.0 minutes for strong-model episodes (n=10); the failure-enriched weak Bad6 mean is
51.5 minutes. Planning therefore allocates 70 minutes per episode including replay and
Official overhead.

- Phase 0 identity/cache qualification: 3--6 hours, in parallel with the existing TFMA
  wait.
- Core Canary: 40 episodes per host, at most two lanes per host, with paired arms
  sequential inside a lane. Earliest 11 hours; p90 plan 24 hours.
- Seal paired results and infrastructure adjudication: 1 hour. The core decision is
  expected 15--30 hours after launch approval.
- External Repo2Run, EnvBench FreeAgent, and native Codex baselines start only after core
  outcomes are sealed. They do not share host capacity with the paired run or delay the
  core decision.

## Endpoint and Decision

Official Pass@1 is analyzed separately by backbone using paired transitions, an effect
interval, and exact McNemar. Twenty pairs are a protected directional Canary, not a
confirmation: with no control-only success, six treatment-only successes are required
for two-sided exact McNemar p<0.05. The unchanged method reaches the 100-case strong Test
only when strong treatment-only exceeds control-only, at least one real replay activation
occurs, and no shared measurement defect exists. This supports a promising direction,
not the paper's confirmatory success-rate claim.

- **Strong tie:** reliability may be supported, but the strong Test stops by default.
- **Strong negative:** the strong-model direction is rejected and its Test stops.
- **Strong unavailable:** report the missing causal interface and wait for the user's
  decision on whether a weak-only paper remains worthwhile; do not substitute native
  Codex.
- **Shared measurement defect:** invalidate the entire Canary; do not repair and continue
  on the same protected identities.

Weak outcomes are reported independently under the same branches. Only the unchanged
100-case Official Test can carry a confirmatory success-rate claim. Non-submission after
reasoning starts and program-induced timeout are failures. Only pre-response acquisition,
host, authentication, or provider failures may rerun the same case/arm; only evaluator
crash or transport failure may evaluation-only rerun the exact program. No case is
replaced.

Only same-runner A-F versus B-FR is causal. Repo2Run and EnvBench FreeAgent with the same
DeepSeek model, and native Codex with `gpt-5.6-sol`, are end-to-end comparisons. After
Canary opening, algorithm, prompt, tools, replay/submission semantics, model identities,
time limits, cache isolation, and OCO rules do not change. Later mechanisms are separate
studies. Two blinded annotators are required before the final paper reports OCO prevalence,
but annotation does not block paired generation.

