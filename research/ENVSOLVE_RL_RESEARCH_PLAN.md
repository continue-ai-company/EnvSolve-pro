# EnvSolve-RL Research Plan / EnvSolve-RL 研究计划

Status / 状态：独立后续项目，当前不属于 EnvSolve 的论文 claim、方法或实验。

## 中文版

### 1. 核心问题

EnvSolve-RL 研究：能否利用大量可执行部署轨迹，学习一个比固定 LLM policy 更有效的
constraint-to-program policy，并在严格的跨仓库划分和共享实验条件下泛化到未见项目？

它不研究如何重新定义 verifier，也不把 EnvSolve 的规则包装成 RL。前置条件是 EnvSolve 已经产生
稳定、可审计的状态、操作和结果接口，并且数据规模足以支持学习。

### 2. 从 EnvSolve 继承什么

冻结并复用：

- 不可变 observation 与 provenance；
- 版本化公开可执行目标及其内容哈希；
- Pass、Fail 与 Unknown 观测语义；
- typed constraint state；
- 开放的完整部署程序接口；
- fresh-environment verifier；
- 统一的 candidate、token、environment、wall-time 和 cost ledger；
- terminal-only official evaluation 规则。

可以学习：

- 给定目标与约束状态时的完整部署程序生成；
- 首次失败后的修复策略和证据选择；
- 在剩余预算下继续、停止或探索的策略；
- 对 hypothesis 的风险敏感排序。

不得学习或读取：

- Official-Test case 的在线 evaluator feedback；
- 同一 evaluation case 的官方结果；
- 违反环境边界的源码修复；
- train/evaluation 之间的仓库身份泄漏。

### 3. 最小数据单元

每个 transition 至少包含：

```text
repository split and revision
state before action
source constraints and hypotheses
public goal contract and current goal state
candidate action/program
guard decision
fresh-environment observation
verifier outcome
resource cost
termination reason
```

Raw event 永远不可修改。Reward、advantage、failure cluster 和训练样本都是独立版本化的 derived view。

### 4. 暂定研究假设

1. Typed state-action trajectories 比 raw terminal-history trajectories 更具样本效率。
2. 在相同 backbone 和总预算下，学习后的 policy 能提高 unseen-repository success-cost frontier。
3. Provenance、Unknown censoring 和目标状态转移能减少错误 credit assignment。

### 5. 必要实验

- 固定 EnvSolve 与 EnvSolve-RL 的 verifier、action space、信息和评测权限；
- 按 repository identity 做严格 train/dev/test 切分；
- 比较 imitation learning、offline RL、online RL 和无训练 EnvSolve；
- 消融 typed state、provenance、Unknown mask、goal transition 与资源条件；
- 报告 Official Pass@1、success-cost frontier、OOD 泛化和 invalid-action rate；
- 检查训练数据规模曲线，证明收益不是简单来自更多推理计算。

### 6. 启动门槛

只有满足以下条件才启动正式研究：EnvSolve 的核心算法和 evaluator 冻结；轨迹 schema 稳定；具有足够
数量的跨仓库有效 transition；数据泄漏审计通过；固定 policy baseline 已经建立。否则只收集数据，
不提前声称 RL 是有效方向。

### 7. 版本化轨迹契约与最终系统

每个 transition 必须额外绑定 `harness_version`、`policy_version`、前后状态哈希、candidate lineage、
constraint delta、effect-audit 结果和 termination provenance。Official evaluator 只形成 episode 结束后的
独立标签，不能混入在线 state。这样同一条 raw trajectory 可以派生 imitation、offline RL、reward model
和 failure-census view，而不重写原始事实。

EnvSolve-RL 与 Auto-EnvSolve 的职责不能混淆：前者学习在一个冻结 harness 内如何从约束状态选择操作；
后者决定何时以及如何发布新的 harness 版本。最终的自进化环境对齐系统可以交替进行版本化 harness
改进和 policy 训练，但在正式 held-out episode 中两者都保持冻结。当前 EnvSolve-Pro 实验应持续积累
这种可复用数据，而不是只保留最终 pass/fail。

P4 还给出新的数据要求：transition 不能只保存平铺 module constraint，而要保存 root-cause edge、scope、
trust level、platform identity 和 surface-to-root amplification；effect-audit 误杀、verifier 被绕过和网络删失
必须是不同标签。Reward 以最终成功为词典序第一目标，token、候选数和时间只作为同成功条件下的次级
信号；不能把当前会删失搜索的 5-candidate 上限学习成“正确停止”。

P5 将这份要求落成可执行 transition view：每个 action 保存操作前后的 causal frontier、各观测通道的
scope、根因首次出现、复发与闭合，以及完整 raw evidence 的哈希引用。Policy 输入可以使用前沿，但动作
仍是开放部署程序；因此后续可以比较 raw-history policy、flat-state policy 和 frontier-conditioned policy，
而不会把收益混同为更小的动作空间。训练标签必须区分“根因被后续同通道观测证明闭合”和“后续候选
未运行到该探针”；后者是删失，不是正 reward。

训练数据还必须同时保存完整内部 frontier 与模型实际可见的 bounded projection，并绑定 projection schema、
hash、included/omitted count 和完整性标签。若动作产生时的投影是整体截断、缺少根因列表或遗漏状态不明，
该 transition 不能用于比较 frontier-conditioned policy，也不能用事后重建状态替换。这样 EnvSolve-RL
学习的是可复现的信息条件下的策略，而不是拥有历史模型未见信息的离线 oracle。

P7 进一步把学习目标锚定到公开可执行目标。每个 transition 必须保存 goal contract ID、程序摘要、
report schema、操作前后 goal status、typed finding disposition、evidence scope 以及 finding set
completeness。只有同一 contract 从 Fail 转为 Pass，或完整的同 scope 快照解除同一 finding，才构成
可靠的中间正标签；partial report 中未再次出现、未运行目标、目标报告损坏和基础设施失败都不能提供
closure reward。goal-aware raw-history 与显式 constraint-state 的受控轨迹将成为 EnvSolve-RL 的第一组
表示学习对照。

当策略使用 finding 定向源码证据和保留候选锚点时，transition 还必须保存模型可见证据投影的 schema、
内容哈希、查询范围与截断信息，以及锚点 candidate ID、程序哈希、准入评估和选择 rank。否则离线训练
可能看到在线策略当时没有看到的源码，或无法判断新程序是在修复锚点还是遗忘锚点，形成不可审计的
credit assignment。

### 8. 后置条件资格实验带来的数据要求

新的资格实验提供了第一组 matched fresh/persistent 轨迹，但也说明中间进展不能直接当 reward：三个
condition 都在 `openqasm` 上降到 7 个 finding 后失败，多次 finding 数下降、成功安装和 state reuse
都没有转化成 Official Pass。可靠的正 reward 仍是 clean fresh replay；finding delta 只能作为带 scope
和完整性标签的 shaping signal。

每个 action transition 还应保存 operation-family identity、目标 finding、前提证据引用、预期 finding
delta、实际完整快照 delta 和 effect-boundary decision。EnvSolve-Pro v1 已生成这些版本化字段，可直接
作为 EnvSolve-RL 的离线数据接口；但 model-declared family 只能作为带噪行为标签。手工复制生成 parser、
写 evaluator 配置或制造 import artifact 的动作必须标记为 `integrity_invalid`，即使它们减少诊断也不能
获得正 reward。重复
不可行 operation family 且没有新前提证据，应形成负的策略监督；provider 延迟和 transport timeout
只进入基础设施与资源视图，不进入部署动作 reward。

操作相关性资格轨迹要求再保存两个视图：完整 active finding 集合，以及模型实际看到的 target/evidence
projection，包括 included/omitted 数量和 policy rejection。Trax 中“真实但未展示的 target”和“不活跃
target”必须使用不同标签，不能都作为 hallucination 负样本。UER-py 中，候选触发固定命令超时表示策略
没有在协议内提交成功答案，应获得 terminal non-pass mask；其后环境状态仍是 Unknown，不能伪造具体
constraint reward。Provider 402、请求超时和 evaluator 事故使用 external-censor mask，不产生动作负
reward，也不能用重跑轨迹覆盖原始 transition。

### 9. 因子化目标与操作标签

V2.3 Pilot-3 表明，一个 transition 不能只有单一的 pass/fail 标签。训练单元必须分别保存：

- 公开目标状态：`satisfied`、`unsatisfied` 或 `unknown`；
- 操作契约：policy、repository effect、caller CWD 等逐项后置条件；
- 候选验证器的原始决策、版本和精确 violation；
- construction state 的 reusable/damaged/unknown 判定；
- 独立 clean replay 与 Official Pass。

“目标已满足但操作违规”应训练局部修复，而不是奖励重新搜索整个部署方案。验证器误拒属于
`measurement_censored`，不能给策略负 reward；真实 effect 或 CWD 违规则可以提供精确约束监督。
终局合法 Pass 后的旧 CandidateAssessment 必须从 policy state 中移除，否则 learner 会把成功状态
错误标成 inadmissible。这样的因子化标签允许未来重新定义 reward，而不需要重跑第一篇论文的轨迹。

### 10. 具有因果依据的操作奖励

StopStalk 的已消费复放消除了一个因子化标签的歧义。candidate 内部目标完整通过，但最终停在临时
工作目录；不修改 candidate 的 Official 复放随后因为 evaluator 无法创建相对
`build_output` 结果路径而在 Pyright 前失败。因此该 transition 应标为
`goal_satisfied=true`、`operation_cwd_valid=false`、`official_pass=false`，并绑定
evaluator continuity 的因果证据。

这是操作策略的局部负监督，不是依赖选择的全局失败 reward。被网络删失的重复执行继续 mask。
未来 RL 数据必须区分“具有官方因果证据的操作 violation”和“尚未证实的验证器拒绝”；后者只有
通过反例资格验证后，才允许塑造策略。

### 11. Minimal B 的认证与修复标签

Minimal B Dev-5 要求把 clean-replay 轨迹至少拆成两种学习样本：`first_replay_pass` 表示 Agent 面向
可认证交付物的一次构建，`replay_fail_then_repair` 才表示反例条件下的修复。当前 5 条 treatment
全部属于前者，不能作为 repair policy 的正样本。

每次提交必须保存规范化程序 hash、fresh environment receipt、replay 状态、失败后是否继续提案、
最终 Official Pass，以及基础设施 censor。`plugin.video.netflix` 还说明 official goal 与
required-interface compatibility 要保留独立标签；辅助语义标签不能覆盖榜单 reward。这样的数据格式让
第二篇可以重新定义多轴 reward，而无需重跑第一篇的原始轨迹。

### 12. Verifier 非干扰与来源标签

Readux 三臂轨迹不能被压成一个终局 reward。C 组应保留
`official_goal_pass=true`、`protocol_admissible=false` 与
`verifier_interference=true`；A 组则保留 `construction_goal_pass=true`、
`repository_configuration_provenance=tracked_exact_copy` 和旧策略误拒标签。RL 数据不得把 C 当成合法成功，
也不得把 A 的合法配置动作当成负样本。

第一篇保存原始观测、策略版本和修正后裁决，第二篇才可以在不重跑环境的前提下重建多轴 reward。公开
榜单 reward、协议合法性与辅助语义兼容始终分开。

### 13. EnvSolve-Pro V2 的最小学习接口

第一篇当前不维护模型外的长期约束状态，因此后续 RL 不应假设一个尚未被证明必要的复杂表示。最小
transition 以同一 session 中的事件序列为准：模型可见历史、shell 操作与结果、完整程序 hash、软反例
及其原始证据、后续程序、clean replay、Official 终局和基础设施 mask。`replay_fail_then_repair` 是核心
修复样本；`first_replay_pass` 只监督一次构建；provider retry 和网络删失不产生部署动作 reward。

Dev-12 同模型 F 对 F+S+R 的轨迹将首先回答结构化软反例是否提供额外可学习信号。只有该信号跨 case
重复出现后，第二篇才比较 raw-history、soft-constraint-conditioned imitation 与 RL，避免先造复杂状态、
再用训练包装一个没有因果作用的接口。

## English Version

### 1. Core question

EnvSolve-RL asks whether executable deployment trajectories can train a
constraint-to-program policy that improves unseen-repository deployment under fixed
information and shared experimental conditions. It is a separate project, not an
extension of the current EnvSolve claim.

### 2. Inherited and learnable components

The immutable observation/provenance layer, versioned executable goal, Pass/Fail/Unknown
semantics, typed constraint state, open-program interface, fresh verifier, resource
ledger, and terminal-only evaluation protocol remain frozen. The policy may learn
complete program generation, post-failure repair, evidence selection, stopping, and
hypothesis ranking. It may not use official online feedback, evaluation-case leakage,
or source-edit repairs.

### 3. Data and evaluation contract

Training examples preserve the complete state-constraint-action-guard-observation-
outcome-cost chain. Raw events are immutable; rewards and training views are
versioned derivatives. Experiments require repository-disjoint splits, matched
execution settings, fixed verifier access, comparisons with imitation and RL
alternatives, and ablations of typed state, provenance, censoring, goal transitions,
and resource conditioning.

### 4. Start criterion

Formal work starts only after EnvSolve and its trajectory schema are stable, enough
cross-repository transitions exist, leakage audits pass, and a fixed-policy baseline
is available.

### 5. Versioned trajectory contract and final system

Every transition additionally binds the harness and policy versions, before/after
state hashes, candidate lineage, constraint deltas, effect-audit outcomes, and
termination provenance. Official evaluation is a separate post-episode label and
never part of the online state. EnvSolve-RL learns actions within a frozen harness;
Auto-EnvSolve governs evidence-based harness version changes. A future self-evolving
alignment system may alternate these two processes, while freezing both during
held-out evaluation. EnvSolve-Pro should therefore retain reusable transitions, not
only terminal pass/fail labels.

P4 adds concrete schema requirements: transitions must preserve root-cause edges,
scope, trust level, platform identity, and surface-to-root amplification rather than a
flat module list. Effect-audit false positives, verifier manipulation, and network
censoring require distinct labels. Reward is lexicographic with final success first;
tokens, candidates, and time are secondary among equally successful outcomes, and a
binding candidate cap must not be learned as a correct stopping signal.

P5 makes this requirement executable: every action transition stores the causal frontier
before and after the action, observation-channel scopes, first appearance, recurrence,
closure, and hashes of the complete raw evidence. The policy may condition on the
frontier, but still emits an open deployment program, allowing raw-history, flat-state,
and frontier-conditioned policies to be compared without an action-space confound. A
root is a positive closure label only when a newer observation from the same channel
retires it; failure to reach that probe is censoring, not reward.

Training data must preserve both the complete internal frontier and the bounded projection
actually shown to the policy, binding its schema, digest, included and omitted counts, and
integrity label. A transition with whole-object truncation, a missing root list, or unknown
omission status is inadmissible for evaluating a frontier-conditioned policy and cannot be
repaired by substituting an offline reconstruction. EnvSolve-RL must learn under the
reproducible information set available online rather than an offline oracle with historical
information the policy never observed.

P7 grounds the learning target in the public executable goal. Every transition binds the
goal contract ID, program digest, report schema, before/after goal status, typed finding
dispositions, evidence scope, and finding-set completeness. A reliable intermediate
positive label requires the same contract to move from Fail to Pass or a complete
same-scope snapshot to retire the same finding. Absence from a partial report, a skipped
goal, a malformed report, or an infrastructure failure provides no closure reward.
Controlled goal-aware raw-history and explicit constraint-state trajectories provide the
first representation-learning comparison for EnvSolve-RL.

When the policy receives finding-routed source evidence and a retained candidate anchor,
each transition must also preserve the model-visible evidence schema, digest, query and
truncation metadata, plus the anchor candidate ID, program digest, admissibility
assessment, and selection rank. Otherwise offline training may see source context that
was unavailable online or cannot distinguish repairing an anchor from forgetting it,
making credit assignment unauditable.

The five-case evidence-anchor qualification adds two mandatory labels. A transition that
passes the executable goal through an import alias or equivalent synthetic capability is
`integrity_invalid` and receives no success reward, even if the terminal benchmark
passes. A suffix repair executed from an immutable verified environment prefix must bind
the prefix image digest, parent candidate, reactivation context, and final clean-replay
result. Search-time checkpoint success cannot replace the reward from full-program
certification.

Each transition also binds logical model-call identity to its ordered provider attempts,
including duration, retry reason, deadline exhaustion, and censoring provenance.
Transport retries are resource observations, not additional policy actions, and an
in-progress attempt has no negative deployment reward.

The River external-agent trajectory adds a transition label that command logs alone
cannot express. A timed-out environment-creation action was followed by satisfied
runtime and toolchain postconditions, so the action outcome is incomplete while the
resulting state transition is useful. Later transitions downgraded a compiler, rebuilt
native artifacts, and migrated a verified environment outside the repository to change
verifier discovery scope. EnvSolve-RL must bind reward to observed postconditions and
clean terminal replay, not to shell exit status or repeated execution of the original
prefix.

The consumed LitGPT trajectory adds negative evidence for naive persistence: a timed-out
install retained useful package data but also a missing generated executable. Training
labels must therefore distinguish `reusable`, `damaged`, and `unknown` state transitions.
Only executable postconditions may assign state-retention reward; clean replay remains
the terminal success reward.

The frozen postcondition-persistent implementation records the first directly usable
supervision for this objective: construction lineage, state-transition disposition,
freshness, verification role, source candidate, and clean-replay outcome. EnvSolve-RL can
later learn retention or repair value from these fields while treating construction Pass
as an intermediate label and clean fresh replay as the success label.

### 6. Data Update from the Postcondition Qualification

The matched fresh/persistent trajectories show why intermediate progress is not itself a
reward. All three conditions reduced `openqasm` to seven findings and still failed
officially; finding reductions, successful installs, and state reuse did not imply
deployment success. Clean fresh replay remains the positive reward, while finding deltas
are scope- and integrity-qualified shaping signals.

Each action transition should additionally preserve operation-family identity, target
finding, precondition-evidence references, expected finding delta, observed
complete-snapshot delta, and effect-boundary decision. EnvSolve-Pro v1 now emits this
versioned interface for offline learning, although model-declared families remain noisy
behavior labels. Manual parser copying, evaluator-configuration changes, and synthetic
import artifacts are `integrity_invalid` even when diagnostics fall. Repeating an
infeasible family without new precondition evidence is negative policy supervision.
Provider latency and transport timeouts belong to infrastructure and resource views,
not deployment-action reward.

The operation-relevance qualification requires paired transition views: the complete
active-finding set and the target/evidence projection actually shown to the model,
including included and omitted counts plus policy rejections. Real but unexposed targets
and genuinely inactive targets require different labels; neither may be collapsed into
a generic hallucination penalty. A candidate that reaches the frozen command timeout
receives a terminal non-pass mask because the policy submitted no passing answer, while
its resulting constraint state remains Unknown and supplies no fabricated constraint
reward. Provider HTTP 402, request timeout, and evaluator incidents receive an external
censor mask, no negative action reward, and immutable source transitions even when an
identical-episode retry is allowed.

### 7. Network-censored transition masks

The DeepSeek-direct replication shows that one episode may contain useful policy actions
followed by external package failures and a provider timeout, while later episodes fail
before any action during repository acquisition. EnvSolve-RL must preserve the valid
prefix but mask all outcome and stopping rewards after the first independently
attributable infrastructure incident. A paired retry is a new trajectory linked to the
source attempt, not a replacement label. Cache hits, misses, and transferred bytes are
context and resource features; shared cache state is never policy memory or success
reward.

### 8. Dependency-closure and cache context

The UER-py replay shows that repository declarations can expand into a multi-gigabyte
platform-specific closure before the policy receives goal feedback. Training transitions
must therefore preserve the resolved package graph, platform tags, artifact identities
and bytes, cache snapshot ID, hit/miss status, and upstream-read evidence. These fields
are environment context for learning operation feasibility, not privileged outcome
memory.

Cache state can change whether an otherwise identical action finishes before a hard
episode timeout. EnvSolve-RL must stratify or condition rewards by attested initial cache
state and never compare trajectories that began from different snapshots as if only the
policy changed. Per-episode runtime cache mutations may inform acquisition-cost shaping,
but terminal reward still comes from integrity-valid clean replay; a cache hit is never
a deployment-success reward.

### 9. Strong-agent submission and repair labels

The external trajectories establish a useful hierarchy for later training. Native-test
success with an unsatisfied public goal is `proxy_success`, not terminal reward. A
public-goal Pass produced by synthetic import artifacts is
`goal_pass_integrity_invalid`, not positive reward. A legitimate program rejected by a
faulty environment-root measurement is `measurement_censored`; after an identity-
preserving wrapper repair, its clean official Pass becomes valid terminal supervision.

`stateful-agent-v1` should retain the full interactive command trajectory but define one
policy action at each submitted cumulative program. Candidate validation, construction
execution, complete goal delta, and clean replay form ordered outcome labels. A rejected
submission may still contain useful search evidence, but receives no success reward; the
next repair round supplies a transition showing whether the model responds to the exact
violation without forgetting verified environment facts.

This structure supports both offline imitation and later Agent RL while keeping the
first paper model-agnostic. The first paper should log immutable raw events, normalized
observations, model-visible projections, submitted programs, rejection reasons, and
clean-replay identity so that reward definitions can change without rerunning cases.

The v1 consumed study adds two required masks. A trajectory in which the structured
state is empty before the only policy action provides no supervision for state-conditioned
repair and must not be labeled as such. A clean replay that passes by overlaying a
checkout namespace with an older same-name distribution is
`goal_pass_provenance_invalid`, not terminal reward. V2 should preserve the initial
read-only goal observation, the resulting raw and structured projections, the rejected
overlay program, and the next cumulative repair so later learning can assign credit to
an actual Observation-to-Constraint-to-Operation transition.

### 10. First complete state-conditioned repair trajectory

V2.1 now supplies the first complete transition sequence for later learning: a complete
initial goal snapshot, a 70-finding to 24-obligation projection, a submitted cumulative
program, an exact policy rejection, a second model-visible state containing the rejected
program and line-level violation, and a repaired program with internal and official
success. This trajectory can supervise rejection-conditioned repair without inventing
credit from terminal evaluator feedback.

It also requires a two-axis terminal label. Candidate 2 is
`official_goal_pass=true` under EnvBench, but
`module_identity_qualified=false` under the posthoc V2.2 construct. Future rewards
should preserve both labels rather than silently replacing the benchmark objective with
an integrity objective. Identity qualification may be used as a constraint, preference,
or auxiliary reward only after its policy version is bound to the trajectory.

### 11. Failure-Triggered Compact State for Learning

The Dev-5 study adds a required distinction between audit context and policy context.
The learner should retain the full verifier report by digest and artifact reference,
but its action state should contain root obligations, counts, representative locations,
constraint authority, and the exact prior cumulative program. Surface findings that map
to one root must not become hundreds of independent reward-bearing transitions.

No structured-state credit is assigned before the first candidate failure. A first-round
success trains repository-conditioned deployment; a later success trains
counterexample-conditioned repair. An inferred semantic or provenance warning cannot
produce terminal negative reward unless the shared protocol makes it normative.
Official goal success, protocol validity, and auxiliary semantic qualification remain
separate labels. This prevents EnvSolve-RL from learning V2.2's false veto while keeping
the richer trace available for future preference or constraint learning.

### 12. Factorized Goal and Operation Labels

Pilot-3 shows that one transition cannot have a single pass/fail label. Each training
unit must separately retain public-goal state; policy, repository-effect, and caller-CWD
postconditions; the validator decision, version, and exact violation; construction-state
reusability; clean replay; and Official Pass.

A goal-satisfied but operation-invalid transition should supervise local operation
repair, not a restart of deployment search. A validator false rejection is
`measurement_censored` and receives no negative policy reward, whereas a real effect or
CWD violation provides exact constraint supervision. Stale candidate-assessment
metadata must be removed after a valid terminal Pass. This factorization permits future
reward changes without rerunning the first paper's trajectories.

### 13. Causally Grounded Operation Reward

The consumed StopStalk replay resolves one ambiguous factorized label. The candidate
achieved a complete zero-finding internal goal, but ended in a temporary working
directory. The unchanged Official replay then failed before Pyright because the
evaluator could not create its relative `build_output` result path. The transition is
therefore `goal_satisfied=true`, `operation_cwd_valid=false`, and
`official_pass=false`, with a causal evaluator-continuity witness.

This is valid local negative supervision for the operation policy, not a global failure
reward for dependency selection. Network-censored repetitions remain masked. Future RL
data should distinguish operation violations with an official causal witness from
uncorroborated validator rejections; the latter require counterexample qualification
before they can shape policy.

### 14. Within-Session Compatibility Transitions

Pilot-4 shows that candidate-level trajectories alone are too coarse for strong-agent
learning. All raw and structured episodes passed on the first submission, so they
contain no state-conditioned cross-candidate repair action. They must be labeled as
first-round deployment trajectories, not as positive evidence for a repair policy.

The hard trajectory still contains useful action-level supervision. Package resolution,
version conflicts, build feasibility, static visibility, and runtime ABI coherence
should be stored as distinct observed postconditions linked to the command that exposed
them. Repeating an action whose relevant precondition is already falsified is local
negative supervision; recovering from a transport failure is infrastructure context,
not a deployment-policy penalty.

Terminal data must retain at least three independent axes:
`official_goal_pass`, `protocol_admissible`, and `runtime_coherence`. A static Official
Pass with unknown or contradictory ABI coherence is not relabeled as benchmark failure,
but it must not receive full reproduction-integrity reward. This representation lets
EnvSolve-RL later learn a monotonic compatibility frontier without changing the first
paper's frozen objective.

### 15. Minimal B Certification and Repair Labels

The Minimal B Dev-5 batch requires at least two clean-replay transition labels.
`first_replay_pass` describes certification-aware one-shot construction;
`replay_fail_then_repair` describes counterexample-conditioned recovery. All five current
treatment trajectories are the former and must not be used as positive repair-policy
examples.

Each submission should retain the canonical program hash, fresh-environment receipt,
replay result, whether another proposal followed failure, terminal Official Pass, and an
infrastructure censor mask. The `plugin.video.netflix` audit additionally requires
separate `official_goal_pass` and `required_interface_compatible` labels. Auxiliary
semantic labels must not overwrite benchmark reward, allowing later multi-axis reward
definitions without rerunning the first paper's trajectories.

Certification-Repair Ablation v1 adds an explicit one-shot arm, enabling two distinct
future learning contrasts: certification-aware construction from A versus B, and
counterexample-conditioned recovery from B versus activated C transitions. Unactivated C
episodes are not positive recovery demonstrations.

### 16. Verifier Non-Interference and Provenance Labels

The Readux three-arm trajectories must not collapse into one terminal reward. Arm C keeps
`official_goal_pass=true`, `protocol_admissible=false`, and
`verifier_interference=true`. Arm A keeps `construction_goal_pass=true`,
`repository_configuration_provenance=tracked_exact_copy`, and the old-policy false-veto
label. An RL learner must neither treat C as an admissible success nor learn A's legitimate
configuration action as a negative example.

The first paper therefore preserves raw observations, policy versions, and corrected
adjudications. EnvSolve-RL can later rebuild multi-axis rewards without rerunning the
environment, while keeping public benchmark reward, protocol validity, and auxiliary
semantic compatibility distinct.

### 17. Submitted-State and Operation-History Labels

The `trader` calibration trajectory shows that identical terminal import visibility can
arise from different causal operations. RL data must retain protected-configuration
writes even when their files are later deleted, while separately labeling generated
dependencies whose repository declaration and revision-bound lock are verified. A final
state snapshot cannot replace the action history.

The first paper now stores candidate hashes, pre-candidate runtime-template hashes,
package-lock verification, submitted-program fresh replay, construction residue, and
infrastructure censorship as separate fields. These permit EnvSolve-RL to learn operation
preferences without turning a boundary false positive into negative deployment reward or
turning a public-goal exploit into an admissible success.

### 18. Build-Provenance Labels Across Verifier Versions

Boundary-v5 adds two provenance labels that must remain outside the deployment reward:
`committed_source_copy_valid` and `committed_native_provider_valid`. The failed v4
calibration is `measurement_false_negative`, while the unchanged A program under v5 is a
measurement correction, not a new successful policy action.

Training data must retain the same program hash across both boundary versions so a learner
cannot receive contradictory action rewards from a changing verifier. Repository location
is context; verified source derivation is the label.

### 19. Minimal Learning Interface from EnvSolve-Pro V2

The first paper currently keeps no model-external long-term constraint state, so later RL
should not assume a complex representation before its necessity is established. The
minimal transition is the within-session event sequence: model-visible history, shell
action and result, complete-program hash, soft counterexample with raw evidence, revised
program, clean replay, terminal Official outcome, and infrastructure mask.
`replay_fail_then_repair` is the core repair example; `first_replay_pass` supervises
one-shot construction only; provider retries and network censoring produce no deployment
action reward.

The matched F versus F+S+R Dev-12 traces first test whether normalized soft
counterexamples add a repeatable learnable signal. Only after that signal recurs across
repositories should the second paper compare raw-history policies,
soft-constraint-conditioned imitation, and RL. This avoids inventing a rich state and
training around an interface with no demonstrated causal effect.

### 20. Scheduled-Observation Transition Contract

The optional-ledger pilot must not be treated as a homogeneous treatment dataset: one
successful episode received zero ledger calls. Future training records therefore include
the scheduled trigger, actual observation time, environment identity, complete obligation
set, resolved and introduced deltas, shell-action interval, candidate-ready time, replay
counterexample, exact program hash, and Official outcome. Provider retries and censored
infrastructure events remain masked from deployment-policy reward.

Deterministic observation creates comparable state-action transitions without prescribing
the action. This is the minimal interface EnvSolve-RL can reuse to test whether a learned
policy observes or repairs more efficiently than a strong free Agent. Optional-dose v1
episodes remain useful observational trajectories, but not causal positive labels for the
constraint-conditioned policy.

### 21. Repair-Type and Paired-Cost Labels

The target-state replay development expansion adds a second activated transition type.
`importlib_metadata` is a complete-program compatibility/workspace repair, while `pygeo`
is a network-acquisition robustness repair after a pip timeout. Both end in replay and
Official success, but they should not share an undifferentiated positive repair label.
First-replay passes remain certification examples rather than recovery demonstrations.

Training records should preserve `repair_type`, failed phase, external-host involvement,
program revision, replay order, and terminal outcome. Resource supervision must use paired
per-repository differences or distributions rather than aggregate batch reward: the pygeo
outlier lowered total requests, tokens, and time even though the treatment's median paired
generation time increased. This prevents a future policy from learning that long retry
logic or a single easy stopping path is universally efficient.
