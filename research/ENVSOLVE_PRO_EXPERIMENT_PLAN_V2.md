# EnvSolve-Pro Experiment Plan v2

Status: active method selection; scheduled observation was not promoted
Date: 2026-08-19

## 1. Research Thesis

Automated repository deployment is a partially observable, stateful constraint-solving
problem. An agent observes only the failures exposed by its current environment and
actions. It must infer compatibility requirements, change the environment, and deliver
a program that reproduces the compatible state from a clean checkout.

The first paper studies this problem with three contributions:

1. A causal failure taxonomy grounded in the Observation--Constraint--Operation
   architecture, together with cross-baseline failure profiles.
2. EnvSolve-Pro, a fixed and minimal verifier-guided repair algorithm that combines
   free-form search, soft counterexample constraints, and in-session clean replay.
3. A controlled evaluation against native Codex, Repo2Run, the EnvBench agent, and the
   prior hard-constraint EnvSolve, including same-backbone effects, failure-distribution
   shifts, Official Pass@1, and success-first resource efficiency.

EnvSolve-Pro does not search over harness designs. Cross-case harness mutation,
mechanism-combination search, version promotion, and automatic rollback belong to
Auto-EnvSolve. Model training belongs to EnvSolve-RL.

### 2026-08-19 method-selection correction

The preregistered scheduled-observation qualification completed with 16 valid episodes.
Both B-FSR and E-SCHEDULED passed Official 8/8. The mechanism itself was reliable, but
there was no treatment-only win and no preregistered efficiency signal. Fixed cadence is
therefore frozen as a negative candidate and is not the EnvSolve-Pro treatment. We will
not tune the cadence or expose frozen Dev identities for this candidate. The next method
hypothesis must target a decisive failure found in the already fixed baseline bad-case
corpus and must be stated before running a new treatment.

## 2. Deployment Mechanisms and Experimental Foundation

We describe deployment systems using four composable mechanisms rather than treating
system names as explanations. These mechanisms describe how a deployer reasons and acts;
they are separate from the shared harness that makes an experiment valid.

| ID | Primitive | Definition | Characteristic risk |
|---|---|---|---|
| F | Free feedback search | A continuous agent chooses unrestricted environment operations from ordinary execution feedback. | Meandering, state contamination, and non-reproducible success. |
| C_h | Hard-constraint deployment | Encoded compatibility rules require, reject, or rewrite deployment operations or candidates. | False rejection of valid repairs and suppression of stronger models. |
| C_s | Soft-constraint deployment | Execution evidence is normalized into an actionable obligation without removing raw evidence or restricting the action space. | Incorrect normalization can mislead the agent. |
| R | Clean replay and recovery | A complete candidate program is executed in a fresh environment; failure is returned for repair in the same active session. | Added time, network, and storage cost. |

All arms share an experimental-integrity foundation, **E**: evaluator isolation,
repository and goal integrity, result-channel protection, exact-script binding, and
content-addressed artifacts. E does not infer compatibility or choose deployment actions;
it is therefore neither a deployment mechanism nor an EnvSolve-Pro contribution.
Continuous-session access is also matched across controlled arms and is an execution
condition rather than a treatment.

Preliminary baseline mapping, to be verified from frozen code and native traces:

| System | Mechanism profile | Experimental role |
|---|---|---|
| EnvBench FreeAgent / Raw ReAct | F followed by successful-command distillation | Native API baseline |
| Native Codex | Strong F in a continuous session and persistent construction environment | Independent frontier baseline |
| Repo2Run | F plus local checkpoint/rollback after modifying failures | External recovery baseline |
| Prior EnvSolve | F + broad C_h + historical replay machinery | Representative hard-constraint baseline |
| goal-aware boundary-v5 | F + broad C_h + post-session R | Frozen historical baseline, not a frontier claim |
| EnvSolve-Pro | F + C_s + in-session R | Proposed method |

The prior EnvSolve comparison is a system-level comparison, not a pure causal estimate
of C_h, because its replay and policy implementations also differ. Exhaustive mechanism-
combination search is explicitly outside this paper.

## 3. Failure Taxonomy

The unit of annotation is the earliest causally decisive failure, not an error string.
Each failed episode receives one primary category, optional secondary tags, and an
artifact anchor. Infrastructure incidents are censored rather than classified as
algorithmic failures.

### 3.1 Observation failures

- a required fact is never observed;
- construction and clean environments expose different facts;
- runtime, architecture, dependency manager, or goal identity is observed incorrectly;
- a partial or noisy observation is treated as complete.

### 3.2 Constraint failures

- a declared runtime dependency is missed;
- a transitive build-time or system dependency is missed;
- a version, runtime, ABI, platform, or architecture conflict is not represented;
- benchmark-goal satisfaction is confused with executable deployment completeness.

### 3.3 Operation failures

- the selected action cannot satisfy the active constraint;
- action ordering or shell-state propagation is wrong;
- the successful construction state cannot be reproduced by the submitted program;
- a hard guard rejects a valid repair;
- the path reaches the metric through an incomplete or inconsistent environment.

### 3.4 Cross-layer closure failures

- observed evidence is not converted into an active constraint;
- an active constraint does not influence the next operation;
- a repair is not revalidated in the state where it must hold;
- a resolved surface symptom hides an unresolved root requirement.

Taxonomy induction uses only already consumed trajectories from multiple systems. The
taxonomy is frozen before confirmatory method evaluation. New confirmatory phenomena
are mapped to `unresolved` and may motivate a later taxonomy version; they cannot alter
the current paper's categories after outcomes are known.

## 4. EnvSolve-Pro Algorithm

EnvSolve-Pro is a counterexample-guided deployment repair loop.

```text
P0 <- continuous agent constructs a replayable bootstrap program
for t = 0, 1, ...:
    Et <- execute Pt in an exact clean checkout and base environment
    Vt <- run the public executable goal and the minimal integrity audit
    if Vt passes:
        certify hash(Pt) and return Pt
    ct <- normalize the earliest actionable counterexample in (Et, Vt)
    return ct and bounded raw evidence to the same active agent session
    Pt+1 <- agent freely repairs the complete program
```

The soft counterexample record contains only:

- replay status: Pass, Fail, Unknown, or Infrastructure;
- failed phase and earliest failing operation;
- required condition and observed state;
- bounded raw evidence and provenance;
- retryability and environment identity.

It is advisory. The raw evidence remains visible and the agent may reject or revise the
interpretation. No package rule base, candidate graph, cross-case memory, learned
weights, physical checkpoint frontier, or harness self-modification is part of the
algorithm.

The shared E foundation protects benchmark integrity: no Official evaluator feedback in
the loop, no mutation of the goal or tests, and no falsification of the result channel.
It is applied identically to every arm and is not part of the algorithm. It does not
reject deployment actions merely because they create configuration, compile tracked
source, or use an unfamiliar package strategy. Deployment completeness is a non-scoring
secondary axis, not a hard substitute for Official evaluation.

## 5. Models and Provider Policy

### 5.1 Same-backbone API comparisons

All new non-Codex model-backed experiments use:

- OpenRouter model: pinned `deepseek/deepseek-v4-flash-0731`;
- reasoning effort: `xhigh` when the native interface supports it;
- OpenAI-compatible API base: `https://openrouter.ai/api/v1`;
- no model fallback;
- a provider endpoint pinned after a consumed-case smoke test;
- `require_parameters=true` for tool-calling experiments.

The OpenRouter key is supplied only through the process environment. Its value must
never appear in a repository file, command argument, artifact, log, or schedule.
Provider identity and response model metadata are recorded. A provider outage may
trigger one exact semantic retry under the frozen infrastructure policy.

The earlier `deepseek/deepseek-v4-pro` Dev-12 remains a frozen historical pilot and is
not pooled with Flash outcomes. We do not use the moving `flash-latest` alias. Flash
0731 passed a consumed-case qualification covering tool calling, a 53-request continuous
session, feedback-conditioned clean-replay repair, exact-hash submission, and Official
evaluation.

### 5.2 Codex frontier baseline

Codex uses its native CLI and native OpenAI model rather than the shared API backbone.
The intended configuration is the current `gpt-5.6` alias to GPT-5.6 Sol, at the
strongest CLI-supported reasoning setting. The exact CLI version, requested model,
resolved model metadata when available, and reasoning setting are frozen before the
first run. Codex is reported as an independent frontier reference, not as a
same-backbone causal control.

## 6. Experimental Stages

### Stage T: retrospective taxonomy discovery

- Input: all scientifically valid, already consumed Codex, Repo2Run, EnvBench, prior
  EnvSolve, and EnvSolve-Pro trajectories.
- Output: taxonomy v1, baseline mechanism vectors, primary-cause annotations, and an
  unresolved queue.
- No success-rate claim is made from this nonuniform retrospective corpus.
- A deterministic 20% sample stratified by system and primary category is independently
  re-annotated; raw disagreement, Cohen's kappa, and adjudication are reported.

### Stage Q: adapter and measurement qualification

- Use two already consumed repositories.
- Verify the pinned DeepSeek V4 Flash 0731 slug, tool calling, provider pinning,
  token accounting, secret redaction, trajectory preservation, clean replay, Official
  isolation, and Spark execution.
- Outcomes cannot be used for algorithm selection.

### Stage M: consumed-case mechanism selection

- The optional-observation pilot rejected voluntary tool use as an unreliable mechanism.
- The deterministic-observation study verified 34/34 complete observations and 8/8
  compliant treatment episodes, but both arms passed 8/8 and the efficiency criterion
  was false.
- Decision: do not promote or tune scheduled observation; retain it only as observation
  infrastructure and a negative treatment result.
- Next input: the frozen baseline bad-case census, analyzed by earliest decisive
  Observation--Constraint--Operation failure rather than by final error strings.

### Stage D1: small outcome-independent Dev pilot

- Freeze 12 repositories by a deterministic identifier hash before running any new arm.
- The completed V4 Pro pairs are retained as a historical mechanism pilot, not pooled
  with the new model.
- Primary new pair: API free agent F versus EnvSolve-Pro F+C_s+R, both on pinned
  DeepSeek V4 Flash 0731.
- Run order is paired and randomized; the same repository, revision, base image,
  architecture, public goal, and infrastructure rules are shared.
- This stage diagnoses terminal reach, first-replay failures, actual repair activation,
  and unexplained regressions. It is not a SOTA claim.

### Stage D2: targeted ablation and development expansion

Only after D1 completes and passes integrity gates:

- select 16 cases from the taxonomy-consumed reserve by an outcome-independent identity
  hash before any Flash arm is run; these cases are Flash-treatment-unrun, not
  repository-unseen;
- compare F, F+R, and F+C_s+R under a randomized within-case order and the same pinned
  DeepSeek V4 Flash 0731 backbone;
- run the frozen prior EnvSolve on the same identities as the representative
  F+C_h+R system baseline, with every API arm on the same Flash 0731 snapshot;
- interpret F+R minus F as the replay effect, and F+C_s+R minus F+R as the incremental
  soft-constraint effect;
- interpret EnvSolve-Pro versus prior EnvSolve only as a system-level soft-versus-hard
  comparison, not a pure C_s-versus-C_h causal effect.

This produces 64 episodes and does not search any other mechanism combination. If D1
reveals no feedback-conditioned repair, the algorithm claim is revised before D2 rather
than hidden by more cases.

### Stage C: frozen Canary confirmation

- Freeze implementation, prompt, tool schema, model/provider identity, taxonomy, and
  analysis code.
- Run the primary F versus F+C_s+R pair on the untouched 20-case Canary.
- Run external baselines only if their adapters passed Stage Q without changing native
  semantics.
- No algorithm changes are allowed after opening Canary.

### Stage P: protected and leaderboard evaluation

- Run the final selected systems on the protected 100-case split.
- Report protected-test results separately from development results.
- Run the official full 329-case protocol for direct leaderboard comparison after all
  claims and analysis rules are frozen.
- Codex GPT-5.6 is reported as a native frontier reference; pinned DeepSeek V4 Flash
  0731 provides the controlled same-backbone matrix.

## 7. Outcomes and Statistics

### Primary outcome

- Official Pass@1 under the frozen EnvBench evaluator.

### Mechanism outcomes

- construction success but clean-replay failure rate;
- first-replay failure rate;
- feedback-conditioned repair rate: a failed replay followed in the same session by a
  different certified program that passes Official;
- failure-category distribution and paired category transitions;
- false rejection rate of hard boundaries;
- metric-pass but deployment-completeness-flagged rate.

### Resource outcomes

- wall-clock time;
- model input, cached input, output, and reasoning tokens;
- model request count and tool-call count;
- clean-replay count and duration;
- network bytes, disk growth, and peak memory when directly measured.

Token count and monetary price are measurements, not scientific stopping thresholds.
Each episode has only a generous operational safety deadline and provider-request guard.
Success is prioritized; resource Pareto comparisons are conditioned on success or
reported jointly with success.

### Analysis

- paired pass-rate difference with bootstrap confidence intervals;
- exact McNemar test when both arms have Boolean Official outcomes;
- paired transition tables over failure categories;
- category proportions with uncertainty intervals;
- sensitivity analyses that keep infrastructure censoring separate;
- no imputation of missing resource measurements.

## 8. Optimization Boundary

EnvSolve-Pro development may change:

- counterexample normalization fields and evidence bounds;
- when a complete candidate is submitted for replay;
- how replay evidence is returned to the same session;
- script certification and exact-hash handoff;
- resource instrumentation and infrastructure classification.

The first paper may not change or optimize:

- the Official evaluator, benchmark goal, split identity, or protected data;
- baseline source code to make a comparison favorable;
- taxonomy categories after confirmatory outcomes are observed;
- model weights;
- cross-case memory or experience;
- automatic mechanism-combination search;
- automatic harness patch generation, version promotion, or rollback.

Those excluded capabilities define the scope of Auto-EnvSolve and EnvSolve-RL.

## 9. Promotion Gates

Stage D1 may expand only if:

1. every arm uses the bound model/provider and exact repository revision;
2. Official output never enters an active Agent session;
3. at least one treatment trajectory exercises a failed replay and subsequent repair,
   or the study explicitly concludes that the mechanism did not activate;
4. no unexplained treatment regression is hidden by infrastructure censoring;
5. all submitted programs and replay results are content-addressed and reproducible.

Stage C may open only after the method, taxonomy, analysis code, and claims are frozen.
Stage P may open only after Canary results are sealed without algorithm modification.

## 10. Current Freeze

Stage Q has qualified the execution path on consumed cases and contributes no
effectiveness result. Stage D1 now freezes 12 repositories and 24 paired episodes. From
Dev-209, identity-only evidence excludes 153 cases with a prior run manifest or terminal
record; a fixed salt ranks the remaining 56 and selects 12 without reading repository
content, outcome, or failure class. The within-case F/FSR order is also salt-frozen.

The execution is bound by:

- `experiments/validations/envsolve_pro_v2_dev12_preregistration.json`;
- `experiments/validations/envsolve_pro_v2_dev12_mechanism_semantics_amendment.json`;
- `experiments/validations/envsolve_pro_v2_dev12_preselection_audit.json`;
- `experiments/cases/dev_envsolve_pro_v2_pilot12.jsonl`;
- `experiments/schedules/envsolve_pro_v2_dev12.json`.

After the first episode opens, the algorithm, prompt, tool schema, model, provider, and
batch identity do not change. A zero-model-request infrastructure incident may receive
one semantics-identical retry only after preserving the original evidence and recording
an amendment before retry. Later provider-envelope and container-timeout defects are also
preserved as infrastructure-censored attempts and repaired only through generic,
case-independent interface changes recorded before rerun. EnvSolve-Pro V2 now uses
V2-only registry and schedule entrypoints so historical baseline freeze hashes remain
byte-identical.

The semantic amendment does not change any episode. It interprets A as F and B as
F+C_s+R under the common E foundation; the frozen F/FSR run identifiers remain stable.
The preregistered minimal-H label is common experimental integrity, not an algorithmic
treatment or paper contribution.

## 11. Running Evidence

The first frozen pair, `tensorflow/model-analysis`, is a both-fail result. A-F and B-FSR
each exhausted 120 requests without submitting a bootstrap, so both count as Official
Pass@1 false. B-FSR invoked clean replay zero times; this pair therefore exposes a
candidate-formation failure but does not estimate the effect of replay feedback after
activation. The immutable record is
`experiments/validations/envsolve_pro_v2_dev12_pair01_result.json`.

This single pair supports no pass-rate claim. It raises a batch-level diagnostic question:
does delayed or absent candidate formation recur across the outcome-independent Dev-12,
or is it specific to an unusually difficult ARM dependency closure?

The second frozen pair, `rcmdnk/homebrew-file`, is a both-pass result. B-FSR activated
the intended mechanism: its first clean replay exposed six missing imports, the same
session changed the program, and the next two replayed programs passed before exact
submission. A-F also passed Official evaluation. Descriptively, B used 31 versus 56
model requests, 557,816 versus 2,325,002 tokens, 43 versus 88 shell calls, and about
461 versus 1,600 seconds of generation time. These differences are mechanism evidence,
not an expected resource effect from one pair. B's first post-episode Official evaluation
was network-censored and was replaced only by a preregistered exact-script retry without
model re-execution. The immutable record is
`experiments/validations/envsolve_pro_v2_dev12_pair02_result.json`.

Across the first two pairs, both arms are 1/2 on Official Pass@1. The evidence currently
supports mechanism feasibility but neither a pass-rate nor an efficiency claim. The
remaining frozen pairs must determine whether candidate formation is the dominant
failure and whether feedback-conditioned repair yields a reproducible advantage.

The third frozen pair, `nabla-ntnu/nablaweb`, is also both-pass and provides a second,
deeper activation trace. A-F submitted at request 55 and passed. B-FSR first replayed at
request 19: a locally working Pipenv isolated dependencies from the trusted evaluator and
produced 806 missing-import findings. Its second program failed before verification while
parsing the lock file. Its third program installed locked dependencies into the evaluator-
visible Python, passed clean replay, and then passed Official at request 46. B used about
30% fewer tokens, 34% less generation time, and 44% fewer shell calls on this pair. The
immutable record is `experiments/validations/envsolve_pro_v2_dev12_pair03_result.json`.

Across three pairs, both arms are 2/3 on Official Pass@1. B has two feedback-conditioned
repairs but no pass-rate advantage yet. The unconditional resource picture is deliberately
less flattering than the two successful activation traces: B used 197 versus 231 model
requests and 288 versus 307 shell calls, but 11.061M versus 11.044M tokens and 8,606 versus
8,209 seconds of generation time. The first pair's candidate-formation failure erased the
conditional efficiency gains. This strengthens, rather than resolves, the hypothesis that
the next uncertain complete candidate must be formed earlier enough for replay to matter.

The fourth frozen pair, `wpi-lnl/lnldb`, does not yield a paired Official effect. A-F
formed a program at request 71. Its first Official adapter launch was infrastructure-
censored because `uv` was absent from the host PATH; the preregistered exact-script retry
then suffered a TLS EOF while downloading the public Python 3.7.7 source archive, before
Pyright. The single retry allowance is exhausted, so A has no imputed pass/fail outcome.
B-FSR reached the frozen 120-request safety cap without proposing a program, invoked clean
replay zero times, and is an algorithmic failure. B used 6.986M tokens and 146 shell calls,
versus A's 2.852M and 110. This pair therefore cannot estimate pass-rate difference, but it
provides strong failure-mechanism evidence: exposing replay is insufficient when the Agent
treats complete local dependency closure as a prerequisite to program formation. The
immutable record is `experiments/validations/envsolve_pro_v2_dev12_pair04_result.json`.

Across the four attempted pairs, three are pairwise Official-observable and both arms remain
2/3 on those pairs. Pair four is retained for trajectory and resource analysis but excluded
from the paired Official denominator. No algorithm change follows from this case inside the
frozen Dev-12.

The fifth frozen pair, `pypa/twine`, is both-pass. A-F first observed zero local
`reportMissingImports` findings at request 18 but repeated local checks and submitted at
request 49. B-FSR first observed the local goal at request 11, sent a complete program to
clean replay at request 16, passed on the first fresh environment, and submitted on request
17. B used 17 versus 49 model requests, 244,539 versus 1,153,043 tokens, 25 versus 72 shell
calls, and about 222 versus 696 seconds of generation time. This is evidence that clean
replay can act as an explicit certification and stopping signal; it is not a feedback-
conditioned repair because the first replay passed, and one pair cannot establish an
expected efficiency effect. B's first post-session Official attempt was censored during
repository acquisition and the exact script passed the single audited retry without model
re-execution. The immutable record is
`experiments/validations/envsolve_pro_v2_dev12_pair05_result.json`.

Across five attempted pairs, four are pairwise Official-observable and both arms are 3/4 on
those pairs. B now has two feedback-conditioned repairs and one first-replay certification,
but still no pass-rate advantage. The remaining seven frozen pairs are required before
judging whether replay mainly improves repair, termination, both, or neither in expectation.

The sixth frozen pair, `quantumjot/btrack`, is both-pass and sharpens the termination
diagnosis. B-FSR first reached the local goal at request 16 but did not form a replayable
program until request 40; that first clean replay passed and submission followed at request
41. A-F first reached the local goal at request 24 and submitted only at request 56. Both
arms spent the intervening requests pursuing non-scoring runtime completeness questions,
including Pydantic, NumPy, Napari, Qt, Eigen, and the native tracker library. B used 41
versus 56 model requests, 0.981M versus 2.302M tokens, and about 861 versus 1,774 seconds of
generation time. A generated Eigen and an ARM-compatible native library; B installed only
the Python dependency surface. This is a deployment-path difference, not proof that A
achieved complete reproduction or that B is preferable beyond the Official objective.
A's first Official attempt was network-censored during a public package download; the
exact script passed the single audited retry without model re-execution. The immutable
record is `experiments/validations/envsolve_pro_v2_dev12_pair06_result.json`.

Across six attempted pairs, five are pairwise Official-observable and both arms are 4/5 on
those pairs. B has two feedback-conditioned repairs and two first-replay certifications.
Pairs five and six agree that successful clean replay is followed by immediate submission,
but pair six also shows that the current interface does not make the Agent propose a
complete candidate early: 24 requests elapsed between B's first local goal pass and its
first replay. The emerging algorithmic question is therefore not whether replay can verify
a candidate, but how to preserve an already sufficient candidate while optional completeness
exploration continues, without converting a secondary quality objective into a new hard gate.

The seventh frozen pair, `has2k1/plotnine`, provides the strongest repair trace so far but
no paired Official effect. A-F reached a whole-repository local goal pass at request 42 and
submitted at request 68. Its original Official attempt and single exact-script retry both
failed while pip cloned the public `qrenderer` dependency from GitHub; repeated TLS
truncation occurred before Pyright, so A remains infrastructure-censored with no imputed
outcome. B-FSR began replay at request 52. Its first three candidates respectively failed
to return to the goal, exposed 34 evaluator-visible missing imports, and hit the same Git
TLS failure. The same session replaced the Git clone with a tarball, and the fourth and
fifth replays passed before the exact program passed Official. B used 73 versus 68 model
requests, 3.174M versus 1.973M tokens, 100 versus 66 shell calls, and about 4,984 versus
3,093 seconds of generation time. This is feedback-conditioned repair, not evidence of
pass-rate or efficiency improvement. The immutable record is
`experiments/validations/envsolve_pro_v2_dev12_pair07_result.json`.

Across seven attempted pairs, five remain pairwise Official-observable and both arms are
4/5 on those pairs. B has three feedback-conditioned repairs and two first-replay
certifications. Two further pairs retain useful trajectories but no paired effect because
A exhausted its preregistered infrastructure retry. Pair seven also exposes a protocol
boundary that must be frozen before the next study: resilience to dependency-download
failures can be deployment competence when repaired inside the active session, yet the
same failure is currently censored after session termination. Dev-12 will not be changed
post hoc; its remaining five pairs continue under the frozen rule.

The eighth frozen pair, `mov-cli/mov-cli`, is both-pass and isolates certification-driven
termination on a simple dependency closure. B-FSR reached zero local missing imports at
request 12, passed its first clean replay at request 14, and submitted at request 15. A-F
first reached the same goal at request 13, then repeated the goal check eight more times
before submitting at request 43. Both final programs installed the editable project plus
`fastapi` and `mov-cli-youtube`; B additionally installed verifier-side conveniences.
B used 15 versus 43 model requests, 158,559 versus 1,007,718 tokens, 21 versus 69 shell
calls, and about 172 versus 1,963 seconds of generation time. Both passed Official with
the same non-scoring error count. The immutable record is
`experiments/validations/envsolve_pro_v2_dev12_pair08_result.json`.

Across eight attempted pairs, six are pairwise Official-observable and both arms are 5/6
on those pairs. B has three feedback-conditioned repairs and three first-replay
certifications. Pairs five, six, and eight independently show that a successful replay is
followed by immediate submission; pair eight most cleanly attributes the resource gap to
termination because the two final dependency strategies are nearly identical. This still
does not establish an expected efficiency gain: pair seven shows repair can be expensive,
and two candidate-formation failures remain. Four frozen pairs remain.
