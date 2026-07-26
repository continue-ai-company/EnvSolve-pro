# Auto-EnvSolve Research Plan / Auto-EnvSolve 研究计划

Status / 状态：独立后续项目，当前不属于 EnvSolve 的论文 claim、方法或实验。

## 中文版

### 1. 核心问题

Auto-EnvSolve 研究：一个外层研究 Agent 能否根据大量运行中反复出现、且有可执行证据支持的失败，
自动发现内层 EnvSolve 的表示或机制缺口，提出通用修改，并通过冻结的反例、回归测试和未见 case
qualification 安全地改进部署引擎？

它不是让内层 harness 在评测期间偷偷改变规则，也不是把单个 case 的修复写成全局规则。核心对象是
**harness improvement proposal**，而不是 deployment candidate。

### 2. 两层系统边界

内层 EnvSolve：

- 在单个 case 内执行 observation、constraint、operation、verification loop；
- 使用某一冻结版本的 parser、schema、planner、guard 和 verifier；
- evaluation episode 内保持不可变。

外层 Auto-EnvSolve：

- 只读取已完成 episode 的审计 artifact；
- 聚类 unsupported observation、unresolved conflict、invalid action 和 verifier mismatch；
- 提出 parser、constraint type、operator 或 verifier 的通用修改；
- 生成合成反例与回归测试；
- 只有通过独立 qualification 才产生新的内层版本。

### 3. 可更新与不可更新部分

允许版本化更新：

- observation parser 和 evidence normalizer；
- constraint schema 与 admission rule；
- operation type、planner 和 guard；
- benchmark-independent verifier；
- 诊断和审计工具。

永远不可由外层修改：

- 历史 raw event；
- 已冻结实验结果；
- official evaluator；
- held-out split 和预算协议；
- evaluation episode 中正在运行的内层版本。

### 4. 改进事务

每个外层 proposal 必须形成一个可审计事务：

```text
failure cluster and supporting evidence
claimed mechanism gap
minimal generic code change
synthetic counterexamples
regression impact
fresh unseen-development qualification
accept/reject decision
new version manifest
```

单个仓库名称、模块名称或官方 evaluator 输出不能成为准入理由。无法产生通用反例的 proposal 默认
拒绝。

### 5. 暂定研究假设

1. Evidence-grounded outer-loop improvement 比自然语言经验累积更稳定、更可审计。
2. 合成反例加未见 case qualification 能抑制 case-specific overfitting。
3. 随着运行数量增加，parser/operator coverage 和部署成功率能够改善，而回归率保持受控。

### 6. 必要实验

- 按时间和 repository identity 构造严格的 continual stream；
- 比较冻结 EnvSolve、自然语言经验库、无 qualification 的自动修改和完整 Auto-EnvSolve；
- 报告 proposal acceptance rate、regression rate、coverage gain、unseen success gain 和研发成本；
- 对 parser、constraint、operator、verifier 四类修改分别消融；
- 使用 shadow evaluation，保证外层无法接触正式 held-out 结果；
- 对每次版本升级提供可重放的因果证据。

### 7. 启动门槛

正式研究需要多个稳定 EnvSolve 版本、足够大的失败语料、可信的回归测试库，以及真正独立的
qualification reserve。在此之前，只维护机器可读的失败分类和版本 provenance，不自动修改内层算法。

### 8. 统计驱动的外层闭环

外层不能因单个 case 失败就生成代码补丁。一次合法的改进周期必须先冻结一个跨仓库批次，将轨迹按
observation、constraint、operation 和 evaluator gap 聚合，只有某个机制缺口在预先定义的统计规则下
成为主要矛盾，才允许生成一个最小 harness proposal。proposal 随后依次经过：

```text
frozen trajectory census
-> dominant-gap decision
-> one minimal generic proposal
-> synthetic counterexamples and regression tests
-> repository-disjoint shadow qualification
-> promote, reject, or roll back a version
```

因此外层自身也是状态化约束求解器：观测是版本化的失败分布和回归证据；约束包括通用性、数据隔离、
接口兼容和置信门槛；操作是带测试和迁移说明的 harness patch。EnvSolve-Pro 当前生成的 typed event、
candidate lineage、constraint delta、effect audit 和 terminal evaluation 将作为这一闭环的初始数据契约。

P4 的两组独立普查表明，单一 blocking category 的 leader 会随样本从 closure 变成 operation，但两组共享
的机制仍集中在 runtime/platform 前沿、义务因果压缩和信任边界。因此 Auto-EnvSolve 的触发单位应是
跨仓库机制簇，而不是表层类别票数。外层还必须监控 constraint amplification ratio、等价失败重复率、
verifier-integrity incident、基础设施删失率和过早预算停止率；任何自动 patch 都要在独立样本上复现
机制，而不是只让原类别计数下降。

P5 提供第一个适合外层消费的 derived-state 契约：不可变 raw event 之外，版本化记录
`latest_execution_scope`、`latest_module_observation_scope`、surface-to-root edge、trust 和 amplification。
外层应监控三类缺口：可执行失败没有进入任何 root、多个 root 错误合并、已经被同通道新观测反驳的
root 仍然存活。它可以提出通用 parser 或 scope-transition 修改，但必须保持
`hard_state_mutated=false`，并在跨仓库反例和新的 shadow batch 上验证，不能学习 Conan 或 PyO3 名称
本身作为 case rule。

P5 V2 还暴露了外层系统必须优先处理的一类缺口：**模型输入合同失效**。即使完整内部状态可被事后
重建，只要模型当时看到的是整体截断对象，该 episode 就不能用于判断某个内层机制是否有效。外层必须
绑定模型可见投影的 schema、canonical hash、included/omitted count 和审计结果；不得用更完整的事后
derived state 替换真实输入后重新解释效果。投影合同修复属于 measurement proposal，应先通过已消费
轨迹回放和独立 canary，再允许触发算法 proposal。

### 9. 与 Self-Harness 的边界

[Self-Harness](https://arxiv.org/abs/2606.09498) 已经提出一般性的自改进 harness 范式：同一个固定模型
从 verifier-grounded 失败轨迹中挖掘弱点，生成多个最小 harness 修改，再通过 held-in 与回归 split 的
Pass 非退化规则决定是否晋级。它证明“模型参与修改自身 harness”本身不能再作为 Auto-EnvSolve 的主要
novelty。

[Meta-Harness](https://arxiv.org/abs/2603.28052) 已经研究基于历史源码、分数和轨迹搜索 harness code；
[Agentic Harness Engineering](https://arxiv.org/abs/2604.25850) 进一步提出 component、experience 和
decision observability，并报告了冻结 harness 的跨模型迁移；[Adaptive Auto-Harness](https://arxiv.org/abs/2606.01770)
则把自动 harness 优化扩展到开放任务流。因此，“可观测、可回归、持续或跨模型的 harness 自动优化”
也都不能单独构成我们的贡献。

Auto-EnvSolve 应继承三项可靠做法：跨 case 聚类而不是响应单个故事；每个 proposal 绑定明确失败机制和
最小 editable surface；每次修改都形成可逆、可回归验证的版本转移。但研究边界必须更具体：

- 优化对象不是泛化 prompt 或 tool policy，而是部署引擎中版本化的 Observation parser、Constraint
  transition、Operation interface 与 executable-goal adapter；
- proposal 必须由跨仓库 typed evidence 和可执行反例支持，并检验能否跨模型迁移，而不只适配一个模型
  的行为习惯；
- 数据协议至少区分 failure-mining Dev、用于晋级的 shadow qualification 和永不参与晋级的 final test。
  被反复查询并用于 accept/reject 的 split 属于 validation，不能再承担最终泛化结论；
- 外层既可由同一模型运行，也可由独立研究 Agent 运行。主要 claim 应来自证据合同和安全晋级协议，而不
  依赖“self”或“stronger external agent”的命名。

因此，Auto-EnvSolve 的候选问题是：**一个外层系统能否从连续部署流中自动发现内层状态转移机制的缺口，
并在不接触最终测试的条件下，产生可执行、可回归、跨仓库且跨模型有效的新 EnvSolve 版本？**

P7 的开发过程给出了一个完整但仍由研究者完成的外层改进链：完整 finding 快照修复 stale state，
完整性事故触发通用 artifact guard，缺少仓库语义触发 finding 定向源码证据，跨轮遗忘触发保留候选
锚点。它只能作为未来 Auto-EnvSolve 的设计样例，不能宣称已经自动进化。另一个独立样例是 provider
请求在 SDK 内部发生多次 transport retry，而账本只记录一次模型请求；外层应先提出可观测性修复，
把 transport attempt、模型调用、候选执行和 Unknown 分开，再判断是否存在算法缺口。

## English Version

### 1. Core question

Auto-EnvSolve asks whether an outer research agent can identify recurring,
evidence-supported mechanism gaps in a frozen EnvSolve engine, propose generic
changes, and admit them only after synthetic counterexamples, regression tests, and
unseen-case qualification.

### 2. Two-level boundary

The inner EnvSolve runs a fixed observation-constraint-operation-verification loop
within each case. The outer system reads only completed audit artifacts, clusters
coverage gaps, proposes changes to parsers, constraint types, operators, or generic
verifiers, and produces a new inner version only after independent qualification.
It never mutates a running evaluation episode.

### 3. Improvement transaction

Every proposal must preserve the chain from supporting failure cluster to claimed
gap, minimal generic change, synthetic counterexamples, regression results,
unseen-development qualification, acceptance decision, and version manifest.
Repository names and official evaluator output are inadmissible justifications.

### 4. Evaluation and start criterion

Evaluation uses a repository-disjoint continual stream and compares frozen
EnvSolve, natural-language experience, unqualified self-modification, and the full
admission protocol. Formal work starts only when stable EnvSolve versions, a large
failure corpus, strong regression coverage, and an independent qualification
reserve exist.

### 5. Statistically triggered outer loop

The outer system may not patch the harness in response to one salient failure. A
valid improvement cycle first freezes a repository-diverse trajectory census,
aggregates failures by observation, constraint, operation, and evaluator gaps, and
admits one minimal generic proposal only when a preregistered rule identifies a
dominant mechanism gap. The proposal must then pass synthetic counterexamples,
regression tests, and repository-disjoint shadow qualification before a new inner
version is promoted. In this sense, the outer system is itself a stateful constraint
solver whose observations are versioned failure distributions, whose constraints
encode generality and leakage boundaries, and whose actions are tested harness
patches.

The P4 independent censuses show why surface categories are insufficient: the unique
leader changed from closure to operation, while the same underlying mechanism families
persisted. Auto-EnvSolve should therefore trigger on replicated cross-repository
mechanism clusters and track constraint amplification, repeated-equivalent failures,
verifier-integrity incidents, infrastructure censoring, and premature stopping. A patch
must reproduce and repair the mechanism on an independent sample, not merely reduce one
category count.

P5 supplies the first derived-state contract suitable for the outer loop. Alongside
immutable raw events, each version records execution and observation-channel scopes,
surface-to-root edges, trust, and amplification. Auto-EnvSolve should detect executable
failures with no root, incorrect root merges, and roots that survive a contradicting
same-channel observation. It may propose generic parser or scope-transition changes only
when `hard_state_mutated=false` remains true and cross-repository counterexamples plus a
fresh shadow batch pass. Repository or provider names are evidence instances, never
admissible case rules.

P5 V2 exposes a measurement gap that the outer system must handle before algorithmic
proposals: a **broken model-input contract**. Even when the full internal state can be
reconstructed later, an episode cannot identify mechanism value if the model actually
saw a whole-object truncation wrapper. The outer loop must bind the model-visible schema,
canonical digest, included and omitted counts, and integrity decision. It may not replace
the historical input with a richer offline-derived state and reinterpret the outcome.
Projection-contract repairs are measurement proposals and require consumed-trajectory
replay plus an independent canary before any algorithm proposal is admitted.

### 6. Boundary with Self-Harness

[Self-Harness](https://arxiv.org/abs/2606.09498) already establishes the general paradigm
in which the same fixed model mines verifier-grounded failure patterns, proposes minimal
harness edits, and promotes non-regressive candidates. Auto-EnvSolve therefore cannot
claim harness self-improvement itself as the novelty.

[Meta-Harness](https://arxiv.org/abs/2603.28052) already searches harness code from prior
source, scores, and trajectories; [Agentic Harness Engineering](https://arxiv.org/abs/2604.25850)
adds component, experience, and decision observability and reports cross-model transfer
of a frozen harness; [Adaptive Auto-Harness](https://arxiv.org/abs/2606.01770) extends
automatic harness optimization to open-ended streams. Observable, regression-tested,
continual, or cross-model harness optimization is therefore not sufficient novelty
either.

It should inherit cross-case weakness mining, mechanism-linked minimal proposals, and
reversible regression-tested version transitions. Its distinct research object is the
typed deployment engine: versioned Observation parsers, Constraint transitions,
Operation interfaces, and executable-goal adapters. Proposals require cross-repository
typed evidence and executable counterexamples, and should be evaluated for cross-model
transfer rather than only model-specific adaptation.

The data protocol must also separate failure-mining development data, a shadow
qualification split used for promotion, and a final test that is never queried by the
outer loop. Any split repeatedly used for candidate acceptance is validation data, even
when called held-out. The outer optimizer may use the same model or an independent
research agent; the central claim should concern evidence contracts and safe promotion,
not whether the optimizer is labeled self or external.

P7 provides a researcher-driven example of the future outer transaction: complete
finding snapshots repaired stale state, an integrity incident motivated a generic
artifact guard, missing repository semantics motivated finding-routed source evidence,
and cross-round forgetting motivated a retained candidate anchor. This is a design
example, not evidence that automatic evolution already works. A separate measurement
example is an SDK request that performed multiple hidden transport retries while the
ledger counted one model request. The outer system must first separate transport
attempts, model calls, candidate executions, and Unknown outcomes before diagnosing an
inner algorithm gap.

The five-case evidence-anchor qualification adds two concrete outer-loop training
examples. First, two methods obtained Official Pass on Starsim through a symlink import
alias, so an outer proposal must distinguish leaderboard success from integrity-valid
capability and produce a generic alias counterexample. Second, ILAMB repeatedly reached
small finding deltas only after replaying a large installation prefix, motivating a
versioned Operation-layer proposal rather than another package rule. Both examples must
remain typed, consumed development evidence and require independent shadow promotion.

Resource-ledger v1.1 supplies the acquisition boundary: every logical model call owns
an ordered transport-attempt trace with start, finish, duration, outcome, status, retry
reason, and incomplete state. Auto-EnvSolve may diagnose provider infrastructure only
from completed transport evidence; an in-progress attempt at an experimenter
interruption is censoring evidence, not proof that the provider failed.

The River external-agent observation adds a wrapper-repair transaction. A valid solver
trajectory was first rejected because the integrity policy conflated declared native
build outputs with synthetic import artifacts. A safe outer proposal must relax only
repository-declared compiled outputs, add a shared final-program guard, re-finalize the
unchanged recorded output, and verify both regression tests and artifact identity. The
same trace also shows that command status and environment state are separate objects:
an outer optimizer should propose postcondition observers before changing timeout
heuristics or deployment recipes.

The consumed LitGPT observation makes that outer-loop rule stricter. A timed-out install
left both reusable package material and a broken generated entry point, then completed
quickly after explicit inspection. Auto-EnvSolve must therefore test state postconditions
and classify a transition as reusable, damaged, or unknown before proposing persistence;
raising a timeout or caching every nonzero transition is not an admissible repair.

EnvSolve-Pro now makes this proposal executable and versioned. The outer loop can audit
whether every reused lineage had a prior reusable label, whether damaged or unknown state
was released, and whether clean replay contradicted construction success. These are
generic promotion predicates for later harness optimization; the current first-paper
qualification keeps the classifier and promotion rule frozen.
