# EnvSolve: Research and Experiment Plan

> Synchronized Chinese reading version:
> [`ENVSOLVE_RESEARCH_PLAN_ZH.md`](ENVSOLVE_RESEARCH_PLAN_ZH.md). Update both
> files together whenever the research plan changes. Machine-readable frozen
> protocols and experiment artifacts remain the authoritative execution record.
> The living ICLR manuscript is maintained separately in
> [`ENVSOLVE_ICLR_RESEARCH_PLAN.md`](ENVSOLVE_ICLR_RESEARCH_PLAN.md) and
> [`ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md`](ENVSOLVE_ICLR_RESEARCH_PLAN_ZH.md).

## 1. Research objective

The first paper is **EnvSolve**. It studies repository environment deployment
as partially observable, stateful constraint solving rather than free-form LLM
command trial and error.

Given a repository `R` and an internal executable feedback interface `U`, an agent
proposes a replayable deployment program
`P_t`. EnvSolve executes each candidate in a fresh environment `E_t`, converts
the resulting command and project feedback into a provenance-bearing state
`S_{t+1}`, and uses its admitted constraints to synthesize the next candidate.
One final candidate is submitted once to the unchanged benchmark evaluator `Q`.

The primary causal claim is:

> Under the same model, raw execution feedback, fresh-environment opportunities,
> and total resource budget, provenance-bearing explicit constraints improve
> final environment-deployment success over unstructured trajectory history and
> natural-language reflection.

The primary product objective is a competitive EnvBench leaderboard result.
The scientific objective is to establish whether structured execution state,
rather than extra evaluator access or extra retries, causes the improvement.
EnvBench is the final evaluation benchmark; Repo2Run, EnvBench agents, Codex,
and same-backbone feedback controls are baselines.

Resource limits belong to the evaluation protocol rather than the task definition.
Compared methods receive matched limits on primitive resources such as model calls
and tokens, candidate environments, commands, and wall-clock time. Dollar cost is
only an auxiliary conversion under a dated provider-price snapshot.

## 2. Scope and integrity rules

The first study targets the 329 Python repositories in EnvBench. EnConda-Bench
is out of scope.

EnvSolve v1 adapts within one case at inference time. Cross-case autonomous
evolution, policy training, and Agent RL are explicitly outside this paper.
The first paper records reusable environments and transition trajectories, but
does not use them to update the policy during held-out evaluation.
Any later cross-case policy-learning study is reserved for the separately
scoped **EnvSolve-RL** project and is not developed in this plan.
EnvSolve v1 also performs no online retrieval of natural-language summaries,
repair experience, or trajectories from other cases. Shared immutable revision
caches, base-image metadata, and benchmark configuration are experimental
infrastructure rather than cross-case memory.

An environment solution may install packages, select runtimes, install system
libraries, configure package managers, and add environment-only configuration.
It must not:

- modify application source code to hide an environment failure;
- create empty or fake modules merely to satisfy static import checks;
- use repository-specific hard-coded fixes derived from held-out evaluation;
- expose official evaluator implementation details or results to the solving
  agent;
- use an official evaluation result to choose, repair, rank, or retry a
  candidate for the same case;
- silently change model, budget, image, timeout, or verifier settings between
  compared methods.

All runs must record the repository revision, method revision, evaluator
revision and dirty state, model identifier, budgets, container image, script,
trajectory, logs, and parsed metrics.

The official evaluator is invoked once per method, case, and seed after the
online episode terminates. Its result is stored only as post-episode evaluation.
Internal feedback must come from ordinary container execution, dependency
tools, and preregistered benchmark-independent project checks available equally
to compared feedback-loop conditions.

## 3. Method

### 3.1 Candidate deployment program

The unit proposed by the outer loop is a complete replayable environment
program, not an isolated shell patch. Candidate `P_t` contains typed runtime,
system-package, package-manager, repository-installation, and environment
configuration effects. Commands executed only for inspection are retained in
the trajectory but excluded from the final program.

### 3.2 Execution evidence and state

Each candidate is executed in a uniquely identified fresh environment. Raw
commands, working directories, stdout, stderr, exit codes, durations, and
project-native check results are immutable evidence. EnvSolve derives explicit
runtime, package, capability, module, platform, and unresolved-goal state from
that evidence. Every derived fact retains provenance and the evidence that
supports or contradicts it.

### 3.3 Constraint admission

Feedback is separated before it can affect the next candidate:

- reproducible deterministic contradictions become hard constraints;
- ambiguous but grounded observations remain hypotheses and may rank candidates
  but cannot eliminate them;
- infrastructure outcomes such as network timeouts remain Unknown and do not
  become environment constraints;
- malformed, stale, environment-reused, or ungrounded feedback fails closed.

Failed evidence must be committed before it can affect the next proposal. Only
an admitted hard conflict creates a mandatory operation obligation. A
hypothesis-only failure may continue the search, but supplies a soft ranking
signal and cannot eliminate candidates. The method adds no repository-name
branch, held-out package map, or source-edit repair path.

### 3.4 Counterexample-guided candidate update

At round `t`, the same agent backbone receives the repository context and the
current admitted state, then proposes `P_t`. Execution evidence updates `S_t`.
If the internal preregistered checks pass, EnvSolve may stop; otherwise it
generates `P_{t+1}` subject to the accumulated constraints and remaining global
budget. Candidate rounds share one model-request, token, wall-clock, command,
and fresh-environment ledger.

Fresh replay is part of the algorithm because it tests the deployment program
without hidden mutations from an earlier candidate. It is not the official
EnvBench evaluation.

For every supported hard conflict, a deterministic planner emits a
provenance-bearing `OperationPlan` that maps runtime, package, capability, and
module conflicts to allowed mutation kinds such as runtime configuration,
Python-package installation, or system-package installation. The model still
chooses concrete parameters and proposes a complete program. Before a container
is created, `constraint-operation-guard-v1` checks that the candidate introduces
at least one permitted new mutation per obligation relative to the latest
actually executed candidate. A rejected candidate consumes candidate and model
budget, but no environment or command budget.

### 3.5 Evaluation separation

The unchanged EnvBench evaluator is a terminal scorer, not an online verifier.
It is run once on the final candidate and its output is never fed back into the
same episode. The already frozen EnvBench Finding Collector remains useful for
post-episode measurement and error analysis only.

### 3.6 Reusable trajectory contract

The first paper stores immutable raw events and versioned derived views. Each
transition records `case_id`, `episode_id`, `candidate_id`,
`parent_candidate_id`, `environment_id`, `step_id`, state before action, action,
raw observation, state after observation, resource cost, and termination. The
final official result is labeled `post_episode_evaluation` and is not part of
online state. Deployment recipes, base-image digests, installed-version
manifests, and selected terminal snapshots make the environments reconstructible.
This data contract preserves future research value without making cross-case
learning a contribution of EnvSolve.

Each constrained transition additionally records source conflicts, source
constraints, operation requirements, the guard decision, candidate mutations,
and verifier outcomes. These form supervised constraint-state-to-action-to-
outcome data for EnvSolve-RL and expose missing parser or operator classes to a
future Auto-EnvSolve system. The first paper does not read these cross-case
derived data to modify its online policy.

## 4. Research questions

| ID | Question |
| --- | --- |
| RQ1 | Under matched total budgets, does EnvSolve improve final Official Pass@1 over native agents and same-backbone feedback-loop controls? |
| RQ2 | Does provenance-bearing constraint state outperform raw trajectory history and natural-language reflection? |
| RQ3 | Which gains come from explicit constraints, evidence admission, and fresh replay? |
| RQ4 | Does EnvSolve reduce repeated failures and deployment cost while increasing clean-replay reliability? |
| RQ5 | Do the effects generalize across agent backbones, repository classes, and failure types? |

## 5. Dataset protocol

EnvBench provides an official 229/100 train/test partition. The published train
JSONL contains one concatenated record, so the train set is reconstructed as the
329-case source minus the unchanged official 100-case test set. Source revision
and file hashes are frozen in `experiments/cases/split_manifest.json`.

| Split | Size | Policy |
| --- | ---: | --- |
| Dev-5 | 5 | Selected from official train by declared environment category; may be rerun |
| Dev-Extension-3 | 3 | Outcome-blind hash sample frozen before its first execution; may be rerun |
| Canary-20 | 20 | Outcome-blind hash sample from remaining official train; once per milestone |
| Train-Pool Snapshot | 201 | Immutable allocation source after Dev-Extension-3; not a current untouched-count claim |
| P0 Harness Dev | 3 | Consumed only for harness validation; excluded from solver confirmation |
| V0 Discovery Round 1 | 5 | Outcome-blind paired FreeAgent/v0 transport and mechanism-discovery batch |
| V0 Discovery Round 2 | 5 | New outcome-blind paired batch frozen after the Round 1 transport repair |
| Remaining Train Reserve | 188 | Outcome-unseen after the allocations above; future allocations must be preregistered |
| Official-Test | 100 | Fully held out until the method and protocol are frozen |
| Leaderboard | 329 | Final full EnvBench run for leaderboard comparison |

Dev-5 covers conventional metadata, package-manager/version constraints,
system or native dependencies, development/test dependencies, and
platform-specific optional dependencies. Replication experiments use the
official held-out 100 cases for three-seed analysis when budget permits.
Dev-Extension-3 was selected from the frozen Train-Rest-204 allocation pool by
SHA256 ranking with a preregistered salt before any of its repositories,
trajectories, or outcomes were inspected. It expands robustness diagnostics
without consuming Canary-20 or Official-Test-100.

`train_untouched201.jsonl` remains an immutable allocation snapshot. Three
outcome-blind cases were consumed by post-freeze P0 harness validation and are
excluded from solver confirmation. EnvSolve v0 Discovery Round 1 was selected
from the other 198 by a new frozen SHA256 salt. A transport defect prevented
the v0 graph from reaching the model; the source batch remains immutable, and
a same-case qualification verified the generic state-schema repair. Round 2
then selected five new cases from the remaining reserve with a different frozen
salt. Each round compares FreeAgent and v0 on identical case identities,
forbids within-batch method changes, and admits a mechanism only when one error
family occurs in at least two valid v0 trajectories and is the plurality of
attributable failures. A development-informed mechanism must still improve a
separately frozen unseen batch before Canary-20 is touched.

## 6. Baselines

- EnvBench deterministic baseline
- EnvBench Python ReAct agent
- EnvBench procedural agent
- Installamatic
- Repo2Run at a pinned revision
- Codex under a frozen native execution policy
- same-backbone FreeAgent under its native ReAct loop
- raw-history retry: the same agent receives the same fresh-environment
  opportunities and raw prior execution feedback, without structured state
- reflection retry: the same agent receives an LLM-produced natural-language
  reflection of the same feedback, without typed constraints
- EnvSolve v0: the same agent and global budget without persistent
  counterexample constraints

Native systems establish leaderboard context. The primary causal comparison is
raw-history retry versus reflection retry versus EnvSolve under the same
backbone, case, official-evaluation count, internal feedback, candidate-round
limit, and global resource ledger. A condition may stop early, but no condition
receives a fresh per-round budget.

## 7. Experiments

| ID | Experiment | Research question |
| --- | --- | --- |
| E1 | Full EnvBench leaderboard comparison against pinned native baselines | RQ1 |
| E2 | Matched-budget native, raw-history, reflection, v0, and EnvSolve comparison | RQ1-RQ2 |
| E3 | Remove structured state, hard-constraint admission, or fresh replay | RQ2-RQ3 |
| E4 | Candidate-round recovery and failure-transition analysis | RQ3-RQ4 |
| E5 | Repeated failures, commands, tokens, time, cost, and fresh-container count | RQ4 |
| E6 | Cross-agent/backbone replication | RQ5 |
| E7 | Stratification by failure type and repository characteristics | RQ5 |
| E8 | Independent clean replay of final successful deployment programs | RQ4-RQ5 |
| E9 | Mechanistic success, regression, and blocked-outcome case studies | RQ1-RQ5 |

The minimal ablation is deliberately small: unstructured raw history,
natural-language reflection, structured evidence without constraint gating,
structured constraints without fresh replay, and full EnvSolve. A new parser,
repair operator, or state type is added only after the same unmet need appears
in multiple unrelated development repositories and is validated on a separately
frozen batch.

## 8. Metrics and statistics

The primary metric is final Official Pass@1: one final candidate, one unchanged
official evaluation, and no evaluator-conditioned selection. Secondary
effectiveness metrics are round-to-round repair rate, clean replay rate,
bootstrap success, project-native internal-check success, and repository
integrity. Efficiency metrics include total, failed, and exactly repeated
actions; repeated failure families; model requests and tokens; wall-clock time;
commands; and fresh environments consumed. A dated provider-price snapshot may
derive auxiliary dollar estimates, but they are not a scientific matching metric.

Mechanism metrics include the precision and coverage of admitted constraints,
the fraction of failures left Unknown, conflicts that change the next candidate,
and successful repairs directly supported by prior evidence. Infrastructure
outcomes are reported separately and never counted as solved environment errors.

Binary paired outcomes use McNemar tests and paired bootstrap 95% confidence
intervals. Continuous paired outcomes use Wilcoxon signed-rank tests with effect
sizes. Multiple comparisons are corrected. Non-deterministic agents use multiple
seeds on a preregistered representative subset, with the full frozen evaluation
run under a declared seed and replicated further when budget permits. Every
headline comparison reports both effect size and resource usage.

## 9. Paper structure

1. Introduction
2. The Interactive-Success versus Deployment-Replay Gap
3. Repository Environment Synthesis
4. Evidence-Grounded Constraint State
5. EnvSolve Counterexample-Guided Deployment
6. Experimental Protocol and Fairness
7. Main Results
8. Mechanism Analysis and Ablation
9. Generalization, Efficiency, and Failure Analysis
10. Related Work
11. Threats to Validity
12. Conclusion

## 10. Milestones

| Phase | Target | Exit criterion |
| --- | --- | --- |
| P0-P1 | Frozen harness, splits, and baselines | Historical infrastructure and comparison artifacts remain auditable |
| P2-P3 | Explicit state and constraints | State reconstructs from immutable events and every constraint has evidence provenance |
| P4-P5 | Repair and internal-verification qualification | Generic repairs and clean replay are qualified without held-out outcomes |
| P6 | Internal-feedback multi-round runner | Raw-history, reflection, v0, and EnvSolve share one global ledger; official output cannot enter online state |
| P7 | Unseen development admission | Full EnvSolve improves over v0 and both feedback controls without integrity violations or case-specific rules |
| P8 | Algorithm and protocol freeze | Code, prompts, budgets, internal checks, splits, stopping, and final-candidate selection are content-frozen |
| P9 | Canary and Official-Test evaluation | Canary-20 is used once after freeze; Official-Test-100 artifacts complete without method changes |
| P10 | Full leaderboard and replication | Full EnvBench, cross-agent replication, and clean-replay artifacts complete |
| P11 | Analysis and submission | RQ1-RQ5, appendix, code, trajectory schema, and reproducibility package complete |

P7 is the algorithmic go/no-go gate. It requires a separately frozen unseen
development batch, valid paired audits, strict improvement in final official
success over EnvSolve v0 and both same-backbone feedback controls, no repository
integrity regression, and a mechanism analysis showing that admitted constraints
changed later candidates. The exact minimum effect and replication count must be
preregistered before that batch based on baseline variance and available power.

After P8, no parser, repair operator, prompt, state transition, internal check,
budget, or candidate-selection rule may change before Canary and Official-Test.
Any necessary change creates a new version and consumes a new preregistered
development batch; it never triggers tuning on the same held-out outcomes.

## 11. Current status

- EnvBench and Repo2Run have been reproduced locally on macOS with Docker.
- `markqvist/reticulum@6ded42e` has completed EnvBench evaluation.
- A normal editable install yields 18 missing-import issues.
- Empty module stubs can reduce the official issue count to zero, demonstrating
  a benchmark-fidelity risk; such stubs are prohibited by this protocol.
- P0 harness is complete: the official protocol is machine-readable; run
  artifacts are written atomically with lifecycle state and full provenance;
  evaluator failures are preserved; and every run can be independently audited.
  The P0 source, datasets, budgets, protocol, scoring/diagnostic channels,
  registries, external revisions, and evaluator image are now content-addressed
  by a machine-verifiable Harness Freeze Manifest.
- P1 is in progress: Dev-5, Canary-20, Train-Rest, and Official-Test are frozen;
  the deterministic and DeepSeek V4 Pro FreeAgent Dev-5 baselines are complete;
  Repo2Run and EnvBench ReAct adapters produce replayable scripts with
  credential-safe provenance and input integrity checks. Repo2Run Dev-5 and the
  remaining EnvBench agent-family baselines remain to be executed.
- P2 is complete: the typed, hash-chained state kernel now backs a live
  `StatefulSolverLoop`; every action result becomes evidence, action and goal
  budgets have explicit terminal states, snapshots are atomically materialized
  and independently audited, and a 25-command recorded trajectory reconstructs
  deterministically from 103 events.
- P3 is complete: benchmark-independent typed constraints normalize runtime,
  package, capability, module, and platform evidence; high-confidence
  contradictions carry evidence-grounded explanations; and a policy wrapper
  checks declared action effects before the P2 executor. Seventeen synthetic
  tests and two already consumed Dev-result replays pass without a model call
  or new benchmark execution. Arbitrary PEP 440 range-emptiness solving and
  live raw diagnostic capture remain explicit P4 extensions.
- P4A, the typed-repair kernel, is complete while P4 remains in progress.
  Repair plans now declare typed effects, replaced facts, risk, provenance, and
  independent probes. Transition-aware preflight permits a repair to replace a
  conflicting fact but never a requirement; old facts become `superseded` only
  after the probe observes the proposed fact. Thirteen synthetic tests pass.
  A read-only replay of the two consumed P3 conflicts matched both to generic
  operator families but produced zero executable plans because runtime-manager,
  available-version, package-manager, and capability-package context had not
  been observed. Evidence-producing context acquisition is the next P4 step.
- P4B evidence-producing context acquisition is complete, while end-to-end P4
  remains open. A resumable read-only probe policy and strict context builder
  now record tool presence, runtime inventories, system managers, and
  provider-backed package candidates. Eleven synthetic tests pass. A case-free,
  network-disabled run of the frozen evaluator image completed seven probes and
  observed `pyenv`, six Python versions from `3.8.18` through `3.13.1`, and
  `apt-get`; its 39-event state audits successfully with no failures or
  repository mount. This can ground runtime repair after provenance transfer,
  while capability-package and module-distribution discovery remain next.
- P4C image-provenance context transfer and one development runtime transition
  are complete and frozen, while P4 remains open. Exact image ID, repository
  digest, source-state hashes, case manifest, audit, and raw-result hash now
  gate context transfer. Six synthetic tests cover matching transfer,
  idempotence, mismatch rejection, evidence selection, and runtime execution
  contracts. On the already consumed `automl/neps` conflict, the first retained
  diagnostic trajectory showed that `pyenv local 3.11.7` alone did not override
  the image's Conda-first `PATH`. A generic, evidence-derived pyenv-shim
  execution contract then allowed the unchanged frozen repair and independent
  `python --version` probe to verify 3.11.7, supersede only the contradicted
  3.13.2 fact, and make the typed state satisfiable. Both trajectories are
  network-disabled, repository-free, auditable, and explicitly not EnvBench
  success evidence. Capability/module discovery and multi-case repair closure
  remain required for the P4 exit criterion.
- P4D capability discovery has completed three frozen development rounds, while
  P4 remains open. Round 1 showed that per-case full `apt-file` Contents refresh
  is operationally unsuitable: provider bootstrap succeeded but index refresh
  timed out at 600 seconds before any repair. Round 2 replaced it with a
  provenance-hashed, targeted Ubuntu Contents query plus local apt-cache
  validation and found two exact PATH-reachable candidates. The frozen P4A V1
  presence probe then accepted `postgresql-common`, exposing a verifier false
  success: `pg_config` resolved, but `pg_config --version` reported that a real
  development package was still required. Round 3 introduced clean-container
  candidate qualification and a V2 semantic commit gate. After separately
  classifying one transient apt timeout, `libpq-dev` was the only candidate to
  pass the semantic interface probe; a third fresh container then completed the
  V2-gated repair, superseded exactly one absent fact, and reached a satisfiable
  audited state. These results motivate image/source-level provider caches and
  typed capability-interface verifiers. P4E subsequently supplies repository
  installation replay, metadata-grounded module repair, and terminal control.
- P4E repository replay is complete and P4 is frozen. A Dev-5 audit established
  that EnvBench `issues_count` counts only `reportMissingImports`, not total
  Pyright errors. The sole remaining bootstrap failure, `jaraco/inflect`, first
  exposed verifier-owned `build_output` as a setuptools flat-layout conflict.
  A provenance-gated relocation operator moved and restored only that external
  artifact, changing bootstrap exit 1 to exit 0 and exposing three test-file
  module obligations. Project metadata and `tox.ini`, without import-name
  guessing, selected the declared `test` extra. Its first replay was correctly
  classified as infrastructure-blocked after a Python-hosted wheel read timeout;
  the preregistered identical retry reached `exit_code=0`, `issues_count=0`, and
  an audited Official Pass. Final Dev-5 status is 5/5 auditable environment
  terminal states: 2/5 Official Pass and 3/5 bootstrap-satisfied with open
  verifier obligations. No model call, source edit, import stub, held-out
  inspection, or repository-specific repair rule was used. P5 must now classify
  optional/platform imports and verifier scan-scope artifacts; the 3/5 open
  cases are not claimed as leaderboard successes.
- P5 is in progress through nine preregistered development rounds. The import
  audit now fails closed on runtime function arguments: correcting one unsound
  default-value rule increased active obligations from 17 to 20 without
  changing any finding identity or official outcome. A benchmark-independent,
  metadata-derived V3 contract now uses isolated imports, entry-point and CLI
  probes, empty working directories, Docker-enforced network disconnection, and
  three-valued decisions. Iteration exposed and corrected three general errors:
  arbitrary function defaults are not observed calls, legacy editable installs
  use `egg-link`/`PKG-INFO`, and source-tree equality is insufficient when build
  metadata depends on `.git`. The preregistered detached-checkout replay reached
  5/5 bootstrap Pass and 5/5 V3 Pass across 24 network-disabled probes, with no
  source edits, name guessing, case-specific maps, or official verifier calls.
  P5 is not frozen. A strict three-valued V1 metadata-resolver contract passes
  nine focused synthetic tests but has no real-repository claim yet; real V1,
  V4, and V6 remain open.
- A Round 10 full-code design audit was completed before further case tuning.
  It repaired contradictory-range SAT, stale superseded facts, atemporal
  context selection, partial V3 aggregation, CLI-convention probes, ambient
  V1 failures, pyenv layout guessing, core-to-harness coupling, macOS-only
  temporary paths, and non-transactional workspace relocation. The full suite
  passes 181 tests. Its preregistered revised-contract Dev-5 replay reached 3/5
  bootstrap Pass and 3/5 V3 Pass; all 21 executed probes passed with zero
  collection errors. The two unknowns are preserved as an omitted external
  `build_output` fixture for Inflect and repeated package-host timeouts for
  Poetry. A generic preregistered pre-bootstrap-directory contract fixes the
  fixture omission without adding repository logic. After the required
  user-confirmed network change, Round 11 retained the three existing passes,
  recovered Inflect and Poetry, and reached 5/5 bootstrap Pass plus 5/5 V3 Pass
  over 24 network-disabled probes, with zero probe failures or collection
  errors. No verifier policy, bootstrap, source, or official outcome changed.
  P5 remains open pending real V1, V4, and V6 evidence. Event replay is
  incremental, while per-event full snapshot writing remains an explicit
  scaling optimization before Train-Rest batching.
- Round 12 real-V1 preparation now shares project provenance and network
  isolation with V3 instead of duplicating collectors. It content-addresses
  installed project requirements, captures the complete installed state and
  container marker environment, requires extras explicitly bound to frozen
  bootstrap hashes, and executes direct resolver evidence only after network
  disconnection. The V1 policy checks attributable project-closure conflicts
  before classifying an otherwise unattributable nonzero ambient resolver as
  unknown. The preregistered run reached 4/5 V1 Pass over 23 active
  requirements, with four network-disabled resolver exit-zero outcomes and no
  collection errors. Poetry remained unknown because a package-host timeout
  stopped bootstrap before collection. No real outcome was used to tune the
  contract. Round 13 consumed the single user-confirmed infrastructure retry
  and exactly reproduced the four V1 decisions and their metadata/resolver
  hashes. Poetry again remained pre-collection unknown after an incomplete
  `cmake` transfer. Local retry is closed; later server batching needs a
  separately preregistered dependency artifact/cache reliability protocol.
  The full suite passes 188 tests.
- Round 14 V4 preparation freezes a two-mode project-native verifier before
  observing outcomes. Content-addressed explicit pytest configuration selects
  direct network-disabled collection; otherwise standard Python build metadata
  selects a no-dependency, no-build-isolation wheel build into temporary
  storage. The planner never executes arbitrary repository commands or uses
  repository identity. No tests collected is unknown, nonzero/timeout is fail,
  and a successful build without a wheel artifact is fail. The full suite now
  passes 195 tests. Its preregistered replay reached 5/5 V4 Pass: two
  content-addressed network-disabled wheel builds and three explicit pytest
  collections covering 284, 207, and 1668 selected tests. All planner evidence
  matched the frozen expectations. This is collection/build evidence only, not
  V5 test execution.
- Round 15 V6 preparation defines reproducibility as exact normalized state
  equivalence across two independent fresh containers, not repeated bootstrap
  exit zero. The fingerprint includes full installed distribution state,
  project metadata/provenance, Python runtime, and marker environment under one
  frozen plan identity. Replays share no writable volume and collect only after
  network disconnection. Missing evidence is unknown and a component delta is
  fail. The pair runner independently checks snapshot hashes, source identity,
  cleanliness, network isolation, and distinct container IDs. The full suite
  initially passed 204 tests. Frozen Round 15 then failed before Docker startup
  because its direct-file entry point initialized the package path too late.
  The zero-execution failure is retained; no V6 outcome was observed and no
  policy changed. Direct CLI coverage fixes the runner, bringing the suite to
  205 tests. A newly hashed Round 16 is required for paired real execution.
- Harness hardening has closed the batch-cancellation blocker: SIGINT/SIGTERM
  now terminate case process groups, clean case-owned containers, cancel queued
  work, write interruption evidence, and preserve auditable terminal states.
- Typed Replay IR v4 is frozen with a benchmark-independent synthetic safety
  corpus. Official and non-scoring Diagnostic channels are separated, and the
  P0 freeze verifier passes without inspecting Canary-20 or Official-Test-100.
- A preregistered P0 post-freeze Dev-3 run completed and audited all three
  first-attempt artifacts. It exposed online dependency-fetch nondeterminism and
  one non-scoring failure-stage summary bug; the latter is fixed and disclosed
  in Harness Freeze v2 without changing Official scoring or raw results.
- Round 16 executed the unchanged prospective V6 contract and wrote all ten
  required fresh-replay artifacts. Four repositories produced two complete,
  exactly equal full-state snapshots: 4/5 V6 Pass, 0/5 V6 Fail, and 1/5 V6
  Unknown. Gpkit replay A timed out while downloading `plotly` before snapshot
  collection, while replay B completed; this is infrastructure blocked rather
  than state drift. Independent audit recomputed the frozen implementation,
  raw-result, and snapshot hashes and rechecked source cleanliness, network
  isolation, and distinct container identities. All checks passed. No local
  retry is allowed by the frozen round. The result retains the V1 Poetry and V6
  gpkit evidence gaps for explicit freeze-readiness review.
- P5 is frozen after a read-only evidence-matrix audit, without rerunning or
  reclassifying either infrastructure Unknown. The final Dev-5 curve is V0
  5/5, V1 4/5 plus one Unknown, V2 2/5, V3 5/5, V4 5/5, V5 not measured, and
  V6 4/5 plus one Unknown. Official Pass and Robust Pass are both 2/5. Four
  clean replays cover three PEP 610 projects and one legacy egg-link project;
  Reticulum passes every measured non-benchmark Robust level while V2 remains
  false, exposing a concrete benchmark-versus-environment distinction. The
  machine-verifiable freeze keeps Unknown fail-closed, contains no case-specific
  verifier rule, and inspected no held-out case. Server dependency caching is
  now a P6/P7 batch-reliability task rather than a P5 tuning obligation.
- EnvSolve v0 development now follows an error-first, complexity-controlled
  loop. A generic analyzer reconstructed all 83 decisions from the already
  consumed same-backbone FreeAgent Dev-5 trajectories. Twelve commands failed;
  six exact retries after failure were concentrated in Poetry, had six distinct
  output hashes, and eventually produced one recovery. This rules out naive
  failed-command suppression but does not select a retry mechanism or any
  other EnvSolve component. The minimal v0 agent is now executable through the
  generic harness: it retains the same ReAct bash surface and adds only a fixed
  `python -m pip check` completion gate. The gate must be the final action-state
  boundary, and it is excluded from the replay script. Runner registration,
  identity propagation, budget accounting, repository integrity, fail-closed
  finalization, and a no-credential CLI preflight pass 224 tests and produce
  auditable artifacts. A frozen post-batch analyzer preserves malformed or
  incomplete trajectories as hashed analysis errors and assigns only observable
  stage labels; it never infers infrastructure failure from an exit code. The
  paired V0 Discovery Round 1 batch was frozen before
  execution with five outcome-blind cases, two same-backbone conditions, one
  seed, no automatic retries, and cross-case mechanism-admission rules. No
  additional algorithm mechanism has yet been selected.
- Discovery Round 1 completed all ten frozen attempts but was invalid for v0
  mechanism inference: an empty initial graph state caused LangGraph to stop
  before the first model request. A minimal, benchmark-independent state schema
  repair and already-consumed same-case qualification produced 7/7 model
  responses, one passing completion-verifier call, and no recurrence of the
  transport exception. The remaining rejection was replay-only, so no
  algorithm mechanism was admitted from Round 1.
- Discovery Round 2 completed ten new outcome-blind first attempts with valid
  audits and zero provider errors. EnvSolve v0 made 67 model requests and used
  665,867 tokens; FreeAgent made 123 requests and used 1,702,574 tokens. Neither
  method reached official evaluation. Four of five v0 trajectories passed the
  fixed completion verifier and were then rejected by the same conventional
  `eval "$(pyenv init -)"` replay mismatch; the fifth failed repository
  integrity after creating an in-repository virtual environment. The repeated
  replay family satisfied the preregistered mechanism threshold, but it was
  classified as infrastructure representation debt rather than an EnvSolve
  algorithm contribution.
- Typed Replay IR v5 therefore adds exactly one semantic normalization: precise
  pyenv initialization becomes an explicit shim-path runtime action while all
  other `eval` and command substitution remains fail-closed. The policy, its
  negative controls, and audited v0 recorded redistillation are frozen in
  Harness v3; the full suite passes 228 tests. Read-only redistillation unlocked
  exactly 2/4 trigger trajectories and preserved the other two rejections.
  Unsandboxed official evaluation then found 0/2 passes: pyfirebirdsql replayed
  successfully but had 11 public issues and 701 Pyright errors, while Islandora
  was network-censored by a package download read timeout during bootstrap.
  These are development-informed diagnostic outcomes, not held-out evidence.
- The first candidate algorithm mechanism is now constrained by this evidence:
  candidate actions must be replayed in a clean environment through a pluggable
  executable verifier contract, and normalized verifier counterexamples must be
  written into explicit solver state before another repair action. The design
  should reuse the frozen P5 verifier interfaces, add no repository map, and
  remain one loop rather than a collection of case-triggered heuristics. It is
  not admitted until a separately frozen unseen development batch improves over
  v0 and same-backbone FreeAgent.
- Counterexample Loop core is now design-preregistered and content-frozen
  before any new real case. It adds one benchmark-independent meta-loop around
  the existing state and constraint kernel: propose a complete deployment,
  evaluate it with a uniquely identified fresh-environment verifier, and either
  terminate on an accepted Pass or persist typed verifier evidence and its
  normalized constraints before the next proposal. Unknown, malformed,
  unnormalizable, environment-reused, contradictory-Pass, and unverified-success
  paths all fail closed. Free-form action output is not implicitly admitted as
  counterexample evidence. A pre-real-case synthetic audit then superseded v1
  with v2 by adding one gate: failed feedback must leave an explicit constraint
  conflict, not merely parseable constraints. The Structured Finding Adapter was
  then audited through v3: verifier-owned goal decisions cannot be overwritten by
  collector dispositions, and requirement/observation evidence retains finding
  provenance without changing normalized constraint semantics. EnvBench Finding
  Collector v1 is separately frozen. It preserves the exact official goal, binds
  exact missing-import diagnostics to revision-owned source, keeps every attributable
  official finding goal-active, and stores P5 semantic disposition separately for
  risk and Robust-Pass analysis. Its read-only qualification on one already consumed
  case reconstructed 11/11 goal-active findings with 5 semantic active obligations,
  6 guarded optional findings, 0 Unknown, and excluded 690 non-environment Pyright
  errors. Nine core tests, ten adapter tests, seven collector tests, and the 254-test
  full suite pass. No new benchmark execution or model request was used. The unseen
  batch remains required, so this is recorded qualification rather than algorithm
  admission.
- Harness Freeze v4 corrects a source-ownership defect discovered when the new
  algorithm protocols were added. V3's broad `experiments/protocols/*.json` glob
  incorrectly treated unrelated future experiment registrations as harness source
  while omitting the actual `envsolve/v0` and state runtime dependencies. V4 pins
  harness code plus those runtime dependencies and leaves configuration, official
  protocol, Typed Replay IR, and datasets in their existing independently hashed
  fields. It changes no scoring, runner, replay policy, or historical result, and
  its machine verification passes.
- The first-paper scope was narrowed before implementing or running a real
  multi-round policy. EnvSolve now uses only historical container execution and
  preregistered internal project feedback online; the official EnvBench evaluator
  is invoked once after the episode. The frozen EnvBench Finding Collector remains
  a post-episode analysis adapter and cannot drive candidate repair. The next work
  item is therefore a new preregistered internal-feedback runner with matched
  raw-history and reflection controls. Cross-case self-evolution and Agent RL are
  deferred beyond EnvSolve; the immutable transition and environment artifacts are
  retained only so later work can reuse the first paper's data.
- P6 now has an executable, benchmark-independent runtime path. A structured
  model policy receives only a bounded read-only repository profile and prior
  internal execution state, and emits one cumulative deployment program. The
  typed replay validator adds a fail-fast shell contract and rejects observations,
  source edits, and unsupported mutations. Every accepted candidate is replayed
  from a distinct Git checkout in a distinct Docker container, then evaluated by
  the fixed `python-deployment-v1` internal profile (`pip check`, bytecode
  compilation, and test collection when tests are present). Official EnvBench
  output is absent from this online path and remains protected by the atomic
  post-episode evaluation claim. Model requests, candidates, environments,
  commands, and wall clock share one resumable ledger.
- Two first-attempt Civet runs on the development-only extension split are retained
  as diagnostic failures, not algorithm results. R1 made one auditable model call
  but the candidate validator rejected ordinary virtual-environment creation before
  execution. The candidate language now admits only an exact bounded venv form and
  records rejected proposals in candidate lineage and budget usage. R2 then executed
  one fresh-container candidate and passed all V1 internal checks, but the official
  post-episode evaluator reported 16 missing-import issues across five module names
  and 1,589 total Pyright errors. This exposes a verifier-recall problem: V1 is too
  weak for repositories without useful test collection. R2 is additionally invalid
  because a stale execution-ledger instance erased its model request and token
  counts. The persisted artifact is unchanged and the independent audit now rejects
  it explicitly.
- Harness Freeze v6 supersedes, rather than rewrites, v5. It reloads the latest
  persisted ledger before every model or execution mutation and requires auditable
  model usage for every model-backed EnvSolve run. Harness Freeze v7 then adds the
  benchmark-independent `python-deployment-v2` verifier: a bounded AST inventory of
  runtime/test/build imports, candidate-environment module resolution, and typed
  module counterexamples. Existing source semantics distinguish active imports,
  inactive platform branches, and optional imports. V2 additionally models an
  `except ImportError` compatibility import as an alternative: it is inactive when
  the primary branch resolves and Unknown when neither branch resolves, never an
  arbitrarily selected hard dependency. Documentation, fixtures, vendored source,
  local modules, and official evaluator output are outside this check.
- The full suites pass 213 EnvSolve tests and 62 harness tests (one opt-in Docker
  test skipped by default), compilation passes, the opt-in V2 Docker boundary test
  passes separately, and Freeze v7 verifies against the live evaluator image. A
  read-only counterfactual over consumed Civet source classifies all 12 Python-2
  fallback occurrences as inactive while retaining the direct Redis obligation;
  this is coverage qualification, not a rerun or score. P6 remains unadmitted. No
  official feedback from R2 may enter future online solver state, and the next real
  execution is a preregistered, development-informed same-case qualification of
  loop timing and auditability only.
- The preregistered Civet R3 qualification made one model request (2,549 tokens),
  persisted one rejected candidate, launched no container, and invoked no official
  evaluator. It is independently audit-valid but failed qualification because the
  model emitted shell control flow that the candidate validator correctly rejected.
  This exposed a generic interface defect rather than an environment failure: the
  validator-owned candidate DSL was not visible to the policy. Harness Freeze v8
  publishes that exact contract in the model system prompt without widening the
  executable shell language. It also audits every failed run that contains persisted
  budget evidence while preserving valid pre-ledger credential and hard-timeout
  failures. R4 is separately preregistered under v8 and remains same-case,
  development-informed qualification only.
- R4 is independently audit-valid and demonstrates a real two-round internal loop,
  but it is not qualification-valid. Candidate 1 ended in an attributable package
  download timeout; the old V2 path incorrectly let that infrastructure observation
  drive candidate 2, contrary to the preregistered retry rule. Candidate 2 completed
  bootstrap and V2 persisted all typed evidence before candidate 3, but the source
  inventory produced two false external obligations for exact repository-local
  legacy modules (`RecipeReader` and `settings`). This led the model to propose a
  forbidden `PYTHONPATH=$PWD` workaround. The run used three requests, 28,274 tokens,
  three candidate slots, two distinct environments, and no official evaluation.
- Harness Freeze v9 corrects those failure classes without repository identities or
  module maps. Project modules are excluded only when an exact module path exists at
  the repository root or along the importing file's project-owned ancestor chain.
  Attributable network signatures now produce infrastructure Unknown and terminate
  the episode; dangerous export names are explicit in the validator-owned prompt
  contract. A read-only replay removes only the two local false positives and retains
  the active `distutils` and `redis.exceptions` obligations. The suites pass 213
  EnvSolve and 63 harness tests, the V2 Docker boundary passes, and v9 verifies.
- R5 is independently audit-valid and satisfies the V2 precision and event-ordering
  qualification checks, but it does not solve the case. It consumed five model
  requests, 41,014 tokens, five distinct candidate environments, about $0.0233, and
  no official evaluation. Three early candidates were spent on a package artifact
  hash mismatch, an unsupported pip option, and an empty package-index response.
  Candidate 4 completed bootstrap; V2 produced exactly three active occurrences over
  two semantic modules: two project-owned `distutils` imports and one
  `redis.exceptions` import. The two local false positives from R4 did not recur.
  Candidate 5 then demonstrated the remaining reasoning defect by trying
  `pip install distutils`; the episode exhausted its frozen candidate budget.
- Harness Freeze v10 improves evidence transmission rather than adding a package
  map or repair operator. Model state now includes the two latest structured
  verifications and full runtime facts, bounded logs preserve both the beginning and
  terminal error, and the system contract explicitly prohibits equating module and
  distribution names. Dependency artifact hash mismatch now terminates as
  infrastructure Unknown. The suites pass 213 EnvSolve and 65 harness tests, the
  real V2 Docker boundary passes, and v10 verifies. R6 is gated on explicit user
  confirmation that the local network has been changed or checked.
- The preregistered Civet R6 run is independently audit-valid but qualification-
  invalid. It used three completed model requests, 24,100 tokens, two candidates,
  two fresh environments, about $0.0133, and no official evaluation. Candidate 1
  reproduced the active `distutils` and `redis.exceptions` obligations. Candidate 2
  treated unresolved module names as package-index distributions and failed on
  `pip install distutils`; the following model response violated the exact-JSON
  contract, which v10 treated as a fatal policy exception despite three unused
  candidate slots. This is same-case development diagnosis, not algorithm-effect
  evidence.
- Harness Freeze v11 makes proposal-level failures part of the stateful solving
  process without adding a repository map or case rule. Malformed model objects are
  now hashed, bounded, persisted, and returned to the policy, with a cap of three
  consecutive failures; candidate-DSL rejection consumes candidate budget but can
  be repaired on the next turn without creating a container. The model projection
  now lists active module obligations explicitly and includes recent policy failures.
  The suites pass 215 EnvSolve and 66 harness tests, one opt-in real Docker boundary
  test passes, syntax compilation passes with an isolated bytecode cache, and v11
  verifies. No further real same-case run is interpreted as held-out evidence.
- R7 is independently audit-valid and reached an internal V2 Pass after four model
  requests, 28,379 tokens, four fresh environments, about $0.0173, and 2,126.8
  seconds of online wall time. The official evaluator was claimed exactly once
  after the episode and did not pass: `issues_count=15`, with four distinct missing
  module names (`ConfigParser`, `Queue`, `requests.packages.urllib3.exceptions`, and
  `urlparse`); 1,579 of 1,594 Pyright errors were non-missing-import diagnostics.
  This score is development-only. R7 is qualification-invalid because candidates 1
  and 2 each hit the 900-second harness timeout, but v11 mislabeled exit 124 as a
  candidate counterexample and allowed those censored logs to drive later proposals.
  No malformed model or DSL output occurred, so R7 does not directly exercise the
  new v11 recovery branch.
- Harness Freeze v12 makes one causal correction: a harness-enforced execution
  timeout is infrastructure Unknown, carries no counterexample, and terminates the
  episode. The suites pass 215 EnvSolve and 67 harness tests, syntax compilation
  passes, and v12 verifies. The next algorithm question is now explicit: the
  semantic runtime import closure can Pass while EnvBench's static missing-import
  objective fails. Any static-closure extension must be specified generically and
  validated on synthetic cases plus newly frozen development cases; the four Civet
  names cannot become repair rules or a package map.
- Harness Freeze v13 implements the preregistered, benchmark-independent two-layer
  import-obligation contract. For every bounded runtime/test/build source import,
  `python-deployment-v3` keeps runtime-semantic execution and side-effect-free
  static-source resolution as separate evidence layers, then emits one typed module
  finding with explicit required, active, and unknown layer provenance. Guarded and
  compatibility imports remain optional at runtime but required for static source
  closure; `TYPE_CHECKING` imports are static-only; provably inactive target-platform
  branches waive both layers. The static resolver supports Python/package/namespace/
  extension paths, `.pyi` and `name-stubs` layouts, standard-library names, and
  physical origins mapped by editable import hooks, while name/origin-mismatched
  dynamic aliases do not satisfy static closure. Unsupported importers remain
  Unknown. The implementation contains no EnvBench call, Pyright call, package-index
  query, case name, or module mapping.
- The frozen synthetic matrix S1-S10 and an executable probe fixture cover active
  absence, physical resolution, optional and fallback imports, dynamic aliases,
  stub-only `TYPE_CHECKING`, platform inactivity, runtime execution errors, and
  unsupported-layout Unknown. Full regression passes 294 tests with one opt-in test
  skipped; the opt-in real fresh-container Docker boundary passes separately;
  syntax compilation passes. Freeze v13 verifies with manifest SHA256
  `60079e6bfd12d9aead2172a47d334b7394eaac46965458c55b08fc3beefd4ba6`.
  No new real case has been run, so this is mechanism validation, not an algorithm-
  effectiveness result. The next admissible step is a separately preregistered,
  unseen development qualification batch comparing a runtime-only admission
  ablation with full V3 under matched budgets.
- The next qualification is now outcome-blind and execution-ready under Harness
  Freeze v15. Five cases were selected from the SHA256-frozen
  Train-Untouched-201 pool by the preregistered salted-hash rule before repository
  inspection; they are permanently development-only, and the remaining untouched
  training pool contains 196 cases. The controlled comparison is not historical V2
  code: both paired conditions use the identical V3 inventory, probe, model, budget,
  and fresh-container implementation. `envsolve-runtime-only` ablates only the
  admission of static-source evidence, while `envsolve-full` admits both layers.
  A frozen interleaved schedule contains ten independent episodes with unique
  run IDs and no shared ledger or trajectory. Full regression passes 298 tests with
  one opt-in test skipped; syntax compilation and the real Docker boundary pass.
  Freeze v15 verifies with SHA256
  `a3e837a92d090017b3d5a88b9ec887a10464f34f05b9accf5e9f36e2cd455c66`.
  No selected repository has been inspected and no model request has been made at
  the time of this freeze.
- Scheduled position 1 subsequently produced an audit-valid but qualification-invalid
  harness diagnostic. The runtime-only episode used one model request, 5,740 tokens,
  one candidate, one fresh environment, and about $0.00314; it made zero official
  evaluator claims. A generic fixed-check failure carried
  `deterministic_counterexample=false` but was still emitted on the hard
  counterexample channel. The normalizer correctly kept the inferred Python-version
  evidence provisional, while the loop incorrectly required every counterexample
  failure to create a hard conflict and blocked after candidate 1.
- Harness Freeze v16 makes the minimal evidence-admission correction: ambiguous
  fixed-check logs remain grounded hypotheses and can rank the next complete
  candidate; only typed grounded findings enter the hard counterexample channel.
  No case rule, package map, or evaluator feedback was used. Position 1 will not be
  overwritten or replaced, so the batch now supports at most four complete paired
  observations plus one full-method development observation. The full 298-test
  regression, syntax compilation, and real Docker boundary pass. Freeze v16 is
  valid with SHA256
  `99b93549ae60f2f01314b59ce08b8f92d99910912cbe08300a8a5e07884871c3`.
- The first position-2 launch made zero model, candidate, environment, or evaluator
  claims and failed during repository acquisition because a Hugging Face HEAD
  request exceeded its 10-second read timeout. The failed artifact is audit-valid
  and preserved; an infrastructure retry is admissible under a new run ID because
  no method information was acquired. Harness Freeze v17 moves immutable repository
  revisions to a shared source cache while preserving independent clean checkouts,
  ledgers, trajectories, scripts, and containers. It also labels pre-episode
  acquisition failures explicitly instead of conflating them with an EnvSolve
  episode failure. Full regression passes 299 tests with one opt-in skip,
  compilation and the real Docker boundary pass, and v17 verifies with SHA256
  `45279af4a4c201d0aa49cd8dd250921cd8a983e4ad9f994225f56ffeddddbe77`.
  The position-2 revision is present in the shared cache; execution is waiting for
  the declared local-network recovery before retry1.
- The permitted position-2 retry is audit-valid but qualification-invalid and made
  zero official-evaluator claims. Candidate 1 exposed a typed-replay representation
  mismatch: activation of a project-root virtual environment was allowed while
  direct `.venv/bin/pip` mutation was rejected. Candidates 2 and 3 then encountered
  Ubuntu mirror 502/connection failures; the final 900-second censored execution was
  correctly terminated as infrastructure Unknown. The immutable diagnostic used
  three model requests, 21,194 tokens, two fresh environments, and about `$0.01175`.
  It is not rerun, leaving at most four complete pairs beginning at schedule
  position 3.
- Harness Freeze v18 makes two benchmark-independent consistency corrections.
  Typed Replay IR v6 admits only project-root `.venv/venv` `pip` and `python`
  executables, with absolute and nested-path negative controls. The network
  classifier recognizes explicit upstream HTTP 5xx and apt connection failures as
  infrastructure Unknown. The 32-case IR corpus, 32 focused tests, full regression
  of 300 passed plus one opt-in skip, compilation, and real Docker integration pass.
  V18 verifies with SHA256
  `a9e03ee3e594e8cef8912e72d2877fcffe0caf78d68cb1e6e34afc1ed53c8fe2`.
  No case-specific mapping or evaluator-derived rule was introduced; the next
  admissible action is the already scheduled position-3 runtime-only episode.
- Position 3 produced the first clean calibration observation. Runtime-only reached
  internal Pass after two candidates, two model requests, 8,234 tokens, two fresh
  environments, and about `$0.00459`. Its first terminal attempt was censored by a
  package-download read timeout before Pyright ran. Freeze v19 independently
  classifies such nonzero-bootstrap, no-Pyright network failures as evaluator
  infrastructure Unknown and permits exactly one new-run, exact-script retry with
  zero model calls. V19 verifies with SHA256
  `152e2ff0d89f396323fdd44baf48e628b09cf609d78af7dc7ffa189219fe35a9`.
  The audit-valid retry completed: bootstrap passed, while the official static
  objective reported exactly the two modules that runtime-only had left unresolved
  but inactive. Thus runtime-only is an official Fail with `issues_count=2`, not an
  infrastructure result.
- Position 4 used an independent full-method state. Candidate 2 admitted the two
  static obligations plus one build-source obligation as hard constraints, but the
  next system-package candidate reached the 900-second command timeout. The run is
  audit-valid infrastructure Unknown, used three requests, 17,992 tokens, three
  fresh environments, about `$0.01019`, and made zero evaluator claims. It is not
  rerun, so pair 2 is incomplete and supports calibration analysis but no paired
  effectiveness estimate.
- The position-4 audit exposed stale terminal wall-time accounting: the command
  timeout was enforced, but the persisted ledger ended at candidate start and
  understated episode time. Harness Freeze v20 finalizes and closes the shared
  ledger before every SolverResult; runner v0.2 audits require `finalized_at`, and
  post-finalization writes fail closed. Full regression passes 306 tests with one
  opt-in skip; compilation and real Docker integration pass. V20 verifies with
  SHA256 `b178c71cd98578273c484442afb193ba2017a61c687091ae6ef90ebd79912e95`.
- Resource-limit selection is now an explicit open evaluation protocol rather than
  part of the task definition. Before held-out execution,
  `P6_BUDGET_CALIBRATION_PROTOCOL_V1` treats EnvSolve as an anytime solver and
  reports the `K={1,3,5}` candidate/environment frontier from causal trajectory
  prefixes; `K=5` is the preregistered leaderboard configuration, not a claimed
  natural optimum. Model-call caps are derived as `3K`. Comparisons match primitive
  model, token, environment, command, and time limits. Dated dollar estimates remain
  auxiliary ledger fields and nonbinding operational circuit breakers only.
- The main runner now has a minimal typed operation boundary. Hard conflicts are
  projected into provenance-bearing `OperationPlan` requirements, and
  `constraint-operation-guard-v1` requires a permitted new mutation before fresh
  execution. Guard-rejected candidates consume candidate/model budget but cannot
  masquerade as executed history. The event contract preserves constraint-action-
  outcome supervision for EnvSolve-RL and coverage diagnostics for Auto-EnvSolve,
  while EnvSolve v1 performs no cross-case retrieval or update. Focused tests,
  full regression (`308 passed, 1 skipped`), compilation, and real Docker
  integration pass.
- Operation qualification Q1 is permanently closed as a harness diagnostic. Its
  first pair exposed a shared-representation mismatch: bounded project virtual-
  environment creation was accepted by candidate validation but rejected by the
  operation guard. Typed Replay IR v6 now represents this action once for both
  components; all five Q1 cases remain development-consumed.
- Q2 is permanently closed after one audit-valid negative pair. Full EnvSolve
  rejected one repeated candidate without creating a container, but a later
  hypothesis-only failure incorrectly retired an unresolved hard conflict. The
  generic state correction treats fresh verification as partial observation: an
  old fact is superseded only by a new fact with the same domain, subject, and
  predicate. Synthetic transition tests prove both persistence and replacement;
  Q2 made no official-evaluator claim.
- Q3 was preregistered and outcome-blind selected from the remaining 186-case pool,
  then closed after its first pair under the frozen adaptation rule. Both methods
  were audit-valid and made zero official-evaluator claims, but both hit the shared
  64K feedback contract. Read-only reconstruction measured 108,802 characters for
  free-form and 109,760 for full after the old fallback. The cause was generic:
  leaf-wise string truncation did not bound aggregate constraint, verification,
  candidate, hypothesis, and operation-plan collections. All five Q3 cases are
  development-consumed; 181 cases remain in the allocation pool.
- The context projection now exposes compact unresolved conflicts, the two most
  recent cumulative candidates, verifier summaries, bounded hypotheses, and, only
  for full EnvSolve, operation requirements grouped by domain and permitted action
  kind. Every field has a deterministic aggregate JSON budget. Read-only replay of
  the Q3 triggering states is 40,114 characters for free-form and 27,526 for full,
  with no field wrapper required. High-cardinality synthetic tests also satisfy the
  minimum 4K contract. Focused regression passes 61 tests; full regression passes
  `324 passed, 1 skipped`; compilation and real Docker integration pass. A new
  mechanism freeze and outcome-blind Q4 batch are required before further real-case
  execution.
- Q4 completed all five pairs with ten audit-valid trajectories. Among four
  uncensored pairs, full EnvSolve produced one full-only official pass, one shared
  pass, and two shared failures; no pair produced an ablation-only pass. One pair
  was censored by a full-condition read timeout. Four full episodes triggered typed
  operation requirements. The full-only pass repaired two explicit module
  obligations, while the shared-pass pair resolved nine obligations in candidate 2
  versus candidate 5 for free-form. This qualifies the operation mechanism for
  continued development, but does not support a paper-level effectiveness claim.
- Q4 also found a shared candidate-language defect: `.venv` could own all installs
  without becoming the verifier runtime. Candidate policy v3 now requires every
  created `.venv` or `venv` to be activated later at the matching path. Synthetic
  order and path tests, full regression (`330 passed, 1 skipped`), compilation, and
  real Docker integration pass. Q5 was preregistered before metadata-only selection;
  five new cases are frozen from the remaining 176-case pool, leaving 171 untouched.
- A repository-wide hardening review then separated evidence preservation from
  scientific admissibility. The original audit remains an artifact-integrity check;
  a new eligibility layer rejects uncommitted source, primitive-budget overruns,
  incomplete heartbeats, suspected host suspension, and schedule identity mismatch.
  Q4 remains 10/10 artifact-valid but 0/10 scientifically eligible because it
  predates the Git baseline. Q5 is likewise excluded; four episodes additionally
  exceed the frozen generation wall-clock limit after host suspension. Neither batch
  may estimate treatment effect or be rerun after the mechanism revision.
- One generic schedule coordinator now replaces five copied qualification drivers.
  It enforces process-group hard deadlines, atomically records immutable position
  transitions, preserves prior outcomes on resume, censors orphaned positions, and
  rejects changed schedule/config/protocol hashes. A deterministic summarizer runs
  both audits, validates schedule identity, hashes every core evidence artifact, and
  reports descriptive observations separately from scientific estimates.
- Complete Candidate v4 and Typed Replay IR v7 close two execution-language defects.
  Project-root virtual environments are matched by effective path rather than the
  `.venv` basename, and bounded `pdm install/sync` mutations are admitted while PDM
  scripts and publishing remain rejected. Read-only replay accepts both Q5 Giskard
  proposals that V6 rejected; this validates language coverage only. Full regression
  passes 343 tests with one opt-in skip, and the real Docker boundary passes.
- Q6 is the first operation batch with ten artifact-valid and scientifically eligible
  runs under the corrected contract. It produced zero official passes. Four pairs
  were censored because generation never reached official evaluation; the only
  official pair, `rebench`, was a both-fail pair. Full reduced `issues_count` from 28
  to 1, but its internal verifier had excluded the remaining documentation import.
  The three other non-timeout cases exhausted five candidates in both conditions,
  and `datasets` exposed unsigned command timeouts being mislabeled as
  infrastructure failure. Q6 therefore rejects the hypothesis that the current
  reactive operation plan is already sufficient.
- Two generic post-Q6 corrections are implemented without case or package rules.
  Documentation joins runtime/test/build source in the bounded two-layer import
  inventory. A command timeout is candidate feedback unless partial logs contain an
  explicit infrastructure signature; hypothesis-only timeout feedback can drive the
  next fresh candidate. Full regression passes `347 passed, 1 skipped`, and the
  opt-in real Docker boundary passes. Q6 remains consumed and is not rerun. Before
  Q7, the algorithm must define conservative initial observation-to-constraint
  admission, and the patched EnvBench evaluator must be represented by a clean,
  shareable revision.
