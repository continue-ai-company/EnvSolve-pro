# EnvSolve-Pro Confirmation Experiment V1

Status: proposal for review; no Canary episode may start from this document alone.

## Question and Fixed Method

Does **in-session complete-program target-state counterexample replay** improve terminal
repository deployment success without restricting a strong or weaker Agent's operation
space?

The candidate method is Minimal B and has two arms:

| Arm | Interface |
|---|---|
| `A-F` | One continuous Agent session with ordinary construction feedback. |
| `B-FR` | The identical session and tools, plus repeatedly callable execution of the complete candidate from the target initial state; failures return to the same session, and only the exact replay-passing program is delivered. |

There is no external constraint state, frontier, checkpoint search, handoff policy,
package rule, or cross-case memory. Official evaluation remains post-episode and is never
returned to the Agent.

## Protected Canary and Execution Order

The Canary is the existing 20-line `experiments/cases/canary20.jsonl`. It was selected on
2026-07-13, outcome-blind, as the first 20 SHA256-ranked Official-train cases after
excluding Dev-5; the line order is the fixed case order. Exposure audits through
2026-08-30 record all 205 Dev identities as consumed and reserve Canary and Official Test
for unseen estimation; no Canary repository has been opened by this study. Case
identities, order, and membership are not changed after execution begins.

Each model--case pair runs both arms on the same host, source snapshot, EnvBench image,
provider policy, seed, and operational allowance. Case positions 1--10 run on Spark and
11--20 on AgentHub. Odd positions run `A-F` then `B-FR`; even positions run `B-FR` then
`A-F`. Construction environments are fresh; shared download caches are read-through
infrastructure and cannot expose another arm's environment state.

The primary weaker-model stratum uses the pinned DeepSeek V4 Flash snapshot already
qualified on consumed Dev. It estimates replay's effect under an open, less capable
backbone. The strong-model stratum repeats the same paired design with the exact Codex
GPT-5.6 identifier qualified on consumed Dev before Canary access. It tests whether replay
still adds value, is neutral, or constrains a frontier Agent. If the strong-model adapter
cannot preserve the same active session and identical arm interface, that stratum is
declared unavailable rather than replaced by an unmatched native Codex run.

This design contains 40 paired comparisons and 80 core episodes. There is no Token or
monetary stopping threshold. A generous per-episode wall-clock deadline and provider
request guard are fixed from consumed-run operating ranges and applied identically within
each model stratum; reaching either after the Agent has started without an Official pass
is algorithmic failure.

## Outcomes and Adjudication

The primary endpoint in each model stratum is **paired EnvBench Official Pass@1**. No
submission, request-limit exhaustion, and program-induced timeout count as failures.
Report the paired transition table, pass-rate difference with interval, and exact McNemar
test. Do not pool model strata to hide a regression.

Infrastructure censoring is narrow:

- source acquisition, host interruption, authentication failure, or provider outage
  before the first model response may be rerun on the same case and arm;
- evaluator crash or transport failure may receive an evaluation-only retry of the exact
  submitted program;
- a valid Official Fail, agent-caused timeout, or failure to submit after reasoning begins
  is never censored;
- no censored case is replaced by another identity.

Secondary outcomes are replay activation, replay Fail-to-repair-to-Pass, candidate
formation, final replay--Official agreement, deployment completeness, wall-clock, model
requests, Tokens, network traffic, disk growth, and peak memory. Resource comparisons are
case-paired and success-conditioned. They cannot override Official success.

All algorithmic non-success trajectories receive one earliest OCO label. Two annotators
independently label a blinded trajectory packet; agreement and adjudicated disagreements
are reported. Infrastructure-censored episodes are excluded from OCO prevalence.

The decision interpretation is fixed before outcomes are observed:

- a positive paired difference with more treatment-only than control-only successes
  supports the terminal-success claim for that model stratum;
- replay--Official agreement or genuine Fail-to-repair-to-Pass trajectories without a
  positive paired success difference support replay reliability only;
- a tie provides no success-rate evidence, and a negative paired difference contradicts
  the success-rate claim for that stratum.

Strong and weaker strata are reported separately. A gain in only one stratum is evidence
about that capability regime, not a claim that the effect is model-independent.

## Baselines and Claim Boundary

Only `A-F` versus `B-FR` with the same runner and backbone is a causal replay comparison.
Repo2Run and EnvBench FreeAgent may use the same DeepSeek snapshot, but their different
prompts, tools, recovery semantics, and candidate interfaces make them end-to-end system
comparisons. Native Codex GPT-5.6 is a frontier end-to-end reference. A harnessed GPT-5.6
`A-F` versus `B-FR` pair is causal; native Codex versus EnvSolve-Pro is not.

External adapters are qualified only on already consumed Dev cases. Their Canary runs,
if qualified, cannot change Minimal B and are divided between the two machines as complete
episodes rather than splitting one method--case pair across hosts.

## Machine Assignment and Post-Canary Rule

Spark runs Canary positions 1--10, GPU/CUDA-sensitive external baselines, and Linux-native
Official evaluation. AgentHub runs positions 11--20, CPU-only Repo2Run and EnvBench
baseline episodes, and independent result aggregation. The local Mac coordinates sealed
artifacts and analysis; it does not become a third experimental environment.

After the first Canary episode starts, no change is allowed to the algorithm, prompt,
tool schema, replay timing, submission semantics, shared validity boundary, model
identifier, or OCO rules. An infrastructure-only retry must preserve model-observable
semantics. Discovery of a shared measurement defect invalidates the confirmation study;
it does not license repair-and-continue on the same Canary. Canary outcomes are sealed and
reported whether positive, null, or negative. No protected 100-case evaluation begins
until this design and the completed Canary evidence receive explicit review.
