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

### 10. 后置条件资格实验带来的更新

完成的五 case、三 condition 资格实验为外层晋级规则提供了一个关键负例：状态复用通过了机制完整性
gate，并出现 6 次复用 verification 和 2 次“复用后 clean replay 成功”，但三个 condition 的 Official
Pass 都是 `4/5`。因此 Auto-EnvSolve 不能把“新机制被执行”“内部 finding 更少”或“资源指标改善”
单独作为 promotion 条件；通用算法 proposal 必须在独立 shadow batch 上提高 Official Pass、失败后
修复率或预注册的 success-resource frontier，且不能引入回归。

本轮轨迹还定义了新的外层可观测量：operation-family identity、目标 active constraint、前提证据引用、
预期与实际 finding delta、effect-boundary decision，以及等价失败方案是否在没有新证据时重复。v1
已经把这些字段落成版本化轨迹接口，但 family 仍由模型声明，不能被外层当作无噪声真值。外层
可以据此提出“操作相关性与前提 gate”这一通用 proposal，但单个 `openqasm` 失败不足以自动晋级；
必须先用合成反例和跨仓库 consumed-development 轨迹证明同一机制缺口，再进入新的 repository-disjoint
qualification。

操作相关性资格实验的 pre-closure 轨迹又增加了两个外层事务。Trax 的 unknown-target rejection 不能
直接解释为模型幻觉：完整 active snapshot 表明其中一部分 target 真实存在但没有进入 bounded
projection，另一部分才是不活跃 ID。外层必须比较完整状态与模型实际可见状态，分别提出 representation
proposal 和 policy proposal。UER-py 则说明 finding delta 与证据引用不能替代操作可行性；触发固定
命令超时的动作属于方法 terminal-reach failure，而 provider 402 属于外部删失。外层在提出算法修改前
必须先冻结这类测量 taxonomy，保留旧分析，并用独立 shadow qualification 晋级。

### 11. V2.3 验证器反例与外层改进事务

V2.3 Pilot-3 给出一个更接近 Auto-EnvSolve 目标的事务。外层系统应从轨迹中发现：目标已经满足，
但操作验证器给出拒绝；随后用最小反例重放验证器，判断拒绝来自真实写入还是文本共现。这里，合法
程序只读取真实 `.py` 文件并写配置，却被全局字符串规则误拒。正确 proposal 不是增加 case 规则，
而是把验证对象从“命令中出现过哪些字符串”改为“程序实际写入哪些目标”。

该事务的自动晋级条件应冻结为：

1. 原始失败轨迹、验证器版本和精确 violation 不可变；
2. proposal 只改变验证器归因，不改变公开目标或终局 evaluator；
3. 至少包含一个真实违规反例和一个合法读源码/写配置的 non-regression control；
4. 修改后必须在新的 repository identity 上验证，生成 proposal 的 StopStalk 只能做回归；
5. `goal_status`、`operation_contract` 与 Official Pass 分列，不能用修复测量错误冒充算法增益。

这说明未来外层 harness 的核心不是从单个失败中记住自然语言经验，而是生成可执行反例、提出最小
接口修改，并通过跨 case 证据控制 promotion。

### 12. 规则保留的因果事务

StopStalk 的已消费 V2.4 复放提供了互补的正例。内部执行已经得到完整的零 finding 目标报告，但
操作契约拒绝了 caller CWD；随后，不修改 candidate、也不重新调用模型的 Official 复放在 Pyright
之前失败，因为 evaluator 的相对路径 `build_output` 被解析到了 candidate 的临时目录。这把一个
通用观测与下游官方失败建立了因果绑定。

Auto-EnvSolve 只有在完成这种反事实审计后，才能保留或晋级操作规则：冻结 candidate，不改变模型
行为，重放官方生命周期，并证明被观测的 violation 能预测真实终局失败。同期网络失败必须删失，
不能用来证明规则。该事务既支持自动做加法，也支持自动做减法：没有官方因果相关性的规则应降级；
已经复放验证相关性的规则保持冻结，并继续接受独立 control 的假阳性检验。

### 13. Minimal B 的机制激活事务

Minimal B Dev-5 为外层系统增加了一个必须显式判断的状态：方法组件存在，但关键 transition 没有发生。
5 个 treatment 都有 callable clean replay，却全部在第一次 replay 通过；`5/5` 对 `4/5` 的正向差异
不能证明 failure-conditioned repair。Auto-EnvSolve 不能仅凭 aggregate score 提升就保留“循环修复”
解释，而必须分别统计 first-replay failure、继续提案和同 session recovery。

这次结果还要求外层把三类 proposal 分开：算法 proposal、共享测量修复、以及 verifier scope 扩展。
杀完整进程树和统一 source cache 属于测量修复；required-interface diagnostic 属于 benchmark 之外的辅助
测量；只有“失败反馈是否改变后续操作”才是内层算法事务。任何 promotion 都必须先证明对应机制在新
批次中被激活，再比较新旧版本，不能让一次 case 差异自动生成永久规则。

### 14. 双轴边界事务

Readux validity pilot 给出一个未来外层系统必须识别的回退条件：Official 指标上升，但上升来自候选
改变 verifier；与此同时，共享完整性规则又误拒了合法仓库配置。Auto-EnvSolve 必须把
`official_goal_pass` 与 `protocol_admissible` 作为独立轴。只要新版本通过破坏第二轴换取第一轴增益，
就必须回退；测量修复也不能被计作内层算法提升。

合格的外层 proposal 应同时带有两类固定证据：一个 verifier-interference 反例，以及一个来源明确的
合法配置 non-regression control。只有二者通过，再在全新仓库 identity 上比较 Official Pass，才
允许晋级内层版本。

### 15. EnvSolve-Pro V2 提供的最小外层接口

第一篇当前冻结的 F/S/R/minimal-H 把未来外层优化边界变得更清楚。Auto-EnvSolve 可以修改软反例的
表示、replay 时机和恢复接口，但不能修改 Official evaluator、公开目标、数据划分或用单个生成 case
验证自己的 proposal。每个外层事务必须从跨 case 轨迹统计开始，提出一个最小通用修改，在未参与生成
proposal 的 shadow batch 上与旧版本配对；Official Pass 回归时回退，资源改善只有在成功率不降时才
支持晋级。

当前 append-only 轨迹已经区分模型请求、provider attempt、shell 操作、完整程序 hash、clean replay、
Official 结果和基础设施删失。Dev-12 的版本冻结、身份盲选、成对顺序和基础设施 amendment 是未来外层
系统应自动产生的第一组控制面样例，但本论文阶段仍由研究者执行，不能声称已经实现 Auto-EnvSolve。

### 16. 已认证程序与 Wrapper 结果不一致事务

PlatformIO screen 失败提供了一类新的外层事务：Agent 的最终程序同时通过 fresh clean replay 和
Official counterfactual，但共享 wrapper 因原 construction workspace 中一个临时目录被删除而记录
Pass@1 Fail。Auto-EnvSolve 必须把 `agent_program_valid`、`clean_replay_pass`、
`wrapper_admissible` 和 `official_outcome` 分开比较，不能从单一终局标签生成算法 patch。

这类 proposal 的目标应是确定哪个状态对最终交付具有权威性，同时保留原 construction audit 作为
诊断证据。晋级需要至少一个真实 tampering 反例、一个合法 cleanup control，以及未参与 proposal
生成的 repository-disjoint shadow batch。修复 wrapper false negative 属于 measurement version，
不能冒充内层部署策略提升。

### 17. Bad4 机制未激活回退事务

固定 Bad4 比较为外层系统提供了一个明确的拒绝样例：`F+O+R` 与 `F+O` 均为 `2/4`，且两个失败的
treatment 都没有调用 replay。Auto-EnvSolve 不能因为组件存在、成功 case 资源下降或某条轨迹更复杂就
晋级版本；关键状态转换没有在目标失败层上激活时，应保留旧版本，并把 proposal 重新定位到候选形成。

Pysnmp 还要求把 measurement repair 与 solver promotion 分开。Python 3.9 审计兼容修复可以通过回归
测试和原脚本重放晋级测量版本，但不能记为内层算法收益。未来比较记录至少保留 candidate formation、
mechanism activation、measurement censor、Official outcome 和 deployment completeness 五个独立字段。

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

The operation-relevance pre-closure trajectories add two outer-loop transactions. A
Trax unknown-target rejection mixed real active findings omitted from the bounded
projection with genuinely inactive identifiers. The outer loop must compare complete
state with the model-visible projection and propose representation and policy changes
separately. UER-py shows that finding deltas and evidence citations do not establish
operation feasibility: a fixed command timeout is a method terminal-reach failure,
whereas provider HTTP 402 is external censoring. The outer optimizer must freeze this
measurement taxonomy, preserve the prior analysis, and pass an independent shadow
qualification before promoting an inner-harness change.

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

### 7. Update from the Postcondition Qualification

The completed five-case, three-condition qualification supplies a negative promotion
example. State reuse passed its mechanism-integrity gate, produced six reused
verifications and two reuse-to-clean-replay passes, yet every condition achieved the
same `4/5` Official Pass. Auto-EnvSolve must therefore not promote a proposal merely
because it is exercised, reduces internal findings, or improves a resource statistic.
A generic algorithm proposal requires an independently qualified gain in Official Pass,
post-failure repair, or a preregistered success-resource frontier without regression.

The v1 trajectory contract now records operation-family identity, target active finding,
precondition-evidence references, expected and observed finding deltas, effect-boundary
decisions, and duplicate-family recurrence without new evidence. This is a concrete
outer-loop interface, but the model-declared family is a noisy label rather than ground
truth. The single `openqasm` failure remains only a hypothesis source; synthetic
counterexamples and cross-repository evidence must establish a mechanism before shadow
qualification.

### 8. Infrastructure incident gate

The DeepSeek-direct replication adds a negative outer-loop example. VPN degradation
first appeared as package SSL/HTTP failures, then as provider timeout, and finally as
repository-acquisition failure before the model ran. Auto-EnvSolve must aggregate host,
provider-attempt, and acquisition evidence before proposing an inner-harness patch.
Externally censored positions remain immutable and can be retried only under a
same-setting amendment; they cannot trigger parser, constraint, operation, or timeout
changes. Method-independent caches may reduce resource waste, but changing cache state
is an infrastructure experiment, not an automatic algorithm promotion.

### 9. Dependency-closure confound gate

The preregistered UER-py replay supplies a concrete outer-loop infrastructure
transaction. Six declared requirements resolved to 35 ARM64 wheels and 2.896 GB of
cached content. Direct and empty-cache lifecycles exceeded the wrapper limit, while a
fresh client reproduced the identical closure from process-level offline cache in 93.74
seconds. Auto-EnvSolve should diagnose repeated acquisition as an infrastructure
confound, propose an isolated cache experiment, and verify offline replay before
attributing timeout changes to the inner solver.

Promotion must preserve agent capability and comparison integrity. A frozen-offline
cache is not admissible as the primary setting because a miss silently closes the
operation space; a global mutable cache is not admissible because method order changes
state. The outer harness may propose only method-independent seed snapshots with an
independent writable online-miss copy per episode. Cache improvements never count as
algorithm promotion, although they may qualify infrastructure for a later frozen study.

### 10. External-agent repair transactions

The Lark and micropy-cli external trajectories add three durable outer-loop labels:
`proxy_goal_termination`, `candidate_interface_violation`, and
`measurement_environment_root_error`. Repo2Run's native-test success on Lark is not an
inner solver success because the public goal remained unsatisfied. Codex's synthetic
micropy-cli stubs are not a prompt-writing failure that should trigger a new package
rule; they are an admissibility violation that should become next-round feedback. The
Lark Conda rejection was instead a harness measurement error and was repaired without
rerunning the model.

Auto-EnvSolve must keep these intervention classes separate. Algorithm proposals change
the Observation/Constraint/Operation policy and require unseen qualification.
Measurement repairs preserve immutable trajectories, add adversarial tests, and may be
re-finalized only with artifact-identity evidence. Baseline-interface repairs disclose
the exact contract and invalidate hidden-rule comparisons. This taxonomy prevents the
outer optimizer from turning every failed case into another inner constraint.

The new `stateful-agent-v1` interface also creates a clean outer-loop target: optimize
which verified observations and raw evidence are carried into the next agent session,
while the public goal, admissibility boundary, clean-replay rule, split isolation, and
terminal evaluator boundary remain frozen.

The completed v1 mechanism study adds two negative promotion transactions. First, all
episodes stopped after one submission, so an outer optimizer must reject a claimed
stateful mechanism when its proposed state was never causally available to a later
operation. Second, fresh replay and Official Pass both accepted a mixed-source Python
namespace assembled from the checkout and an older same-name distribution. The outer
system should propose a repository-independent provenance invariant, test it on a
synthetic namespace-overlay counterexample, and preserve v1 as an immutable baseline.
It must not convert the observed package names into an inner deployment rule.

### 11. Module-identity promotion transaction

The V2.1 micropy-cli trace is the first complete outer-loop repair transaction. A base
image was incorrectly attributed to the read-only probe, so the outer process separated
observation role from candidate admissibility and reran under a new method identity.
The corrected run then exposed a second generic gap: source-byte provenance accepted a
setuptools remap from one project module identity to another. The promoted V2.2 proposal
contains one invariant, one same-identity control, one adversarial remap, and no
repository-specific package rule.

This is the target Auto-EnvSolve pattern: preserve the failing trajectory, classify the
failure as a construct-boundary error, propose the smallest invariant, require a
counterexample plus non-regression control, and only then expose the change to unseen
repositories. Official benchmark success remains recorded even when a stricter
integrity label blocks promotion.

### 12. V2.2 Negative Promotion and V2.3 State Contract

The Dev-5 result is a complete negative outer-loop promotion example. V2.2 reduced
commands and input tokens relative to raw history but regressed Official Pass because
an inferred provenance rule had hard authority. Auto-EnvSolve must reject a proposal
when its efficiency gain is accompanied by an official-success regression, and it must
audit every hard veto against one of two sources: the public executable goal or the
frozen shared admissibility protocol.

The V2.3 trajectory contract separates immutable audit state from decision state:
raw report digest and archive reference; compact root obligations and representative
samples shown to the model; authority class for every constraint; cumulative program;
same-environment verifier receipt; official terminal outcome; and infrastructure censor
mask. The outer optimizer may change projection timing, grouping, or advisory state,
but may not silently promote hypotheses to hard constraints. A proposal is evaluated on
new repository identities after synthetic counterexamples and non-regression controls,
never on the cases that generated it.

### 13. V2.3 Verifier Counterexample Transaction

Pilot-3 supplies a transaction close to the Auto-EnvSolve objective. The outer system
should detect that the executable goal was satisfied while the operation validator
rejected the candidate, then replay a minimal counterexample to distinguish an actual
write from textual co-occurrence. The observed legitimate program read a real `.py`
file and wrote configuration, but a global string rule rejected it. The generic proposal
changes the measured object from strings appearing in a command to actual write targets;
it adds no repository or package rule.

Promotion requires an immutable source trajectory and validator version, one true
violation counterexample, one legitimate read-source/write-config control, and
qualification on new repository identities. The generating StopStalk case remains a
regression only. Goal status, operation-contract validity, and Official Pass must remain
separate labels so a measurement repair cannot masquerade as an algorithmic gain.

### 14. Causal Rule-Retention Transaction

The consumed StopStalk V2.4 replay supplies the complementary positive transaction.
Internal execution reached a complete zero-finding goal report while the operation
contract rejected the caller CWD. An unchanged, model-free Official replay then failed
before Pyright because the evaluator's relative `build_output` path was resolved from
the candidate's temporary directory. This binds one generic observation to a downstream
official consequence.

Auto-EnvSolve should retain or promote an operation rule only after this kind of
counterfactual audit: preserve the candidate, vary no model behavior, replay the
official lifecycle, and show that the observed violation predicts a real terminal
failure. A coincident network failure is censored and cannot justify the rule. This
transaction is a template for automatic subtraction as well as addition: rules without
causal official relevance should be demoted, while rules with replayed relevance remain
frozen and are tested for false positives on independent controls.

### 15. Dormant-Mechanism and Evaluator-Gap Transactions

Pilot-4 supplies a clean negative promotion transaction. Every method achieved `4/4`
Official Pass, but every raw and structured episode stopped after one candidate and one
model round. The proposed cross-candidate state was never available to a later action.
Auto-EnvSolve must reject promotion when a mechanism is implemented but causally dormant;
aggregate success alone cannot establish that the proposed component contributed.

The `flavio` trajectory adds a second outer-loop distinction. A structured candidate
passed the static Official goal by placing a Python 3.9 compiled-package directory on
the `PYTHONPATH` of a Python 3.8 environment. Auto-EnvSolve must preserve
`official_goal_pass`, `runtime_coherence`, and `qualification_unknown` as separate
labels. It may propose a generic runtime-coherence observer, but cannot silently change
the benchmark objective or learn a package-specific rule from this consumed case.

Future outer-loop proposals should target the decision point that trajectories actually
exercise. For strong agents, that often means action-level observation and suppression
inside the first interactive session, not a larger state projection after candidate
submission. Promotion still requires a minimal synthetic counterexample, an easy
non-regression control, and outcome-blind repository-disjoint qualification.

### 16. Minimal B Mechanism-Activation Transaction

The Minimal B Dev-5 result adds a required outer-loop state: a component can be present
without its defining transition being exercised. All five treatments exposed callable
clean replay, but all passed their first replay. The `5/5` versus `4/5` direction therefore
does not identify failure-conditioned repair. Auto-EnvSolve must record first-replay
failures, continued proposals, and same-session recoveries before promoting that mechanism
explanation from an aggregate score change.

The result also separates three proposal classes. Process-tree termination and shared
source caching are measurement repairs; required-interface checking is an auxiliary
verifier-scope proposal; only a demonstrated change in post-counterexample action is an
inner-algorithm transaction. Promotion requires activation on a new frozen batch and
cannot turn a single repository difference into a permanent rule.

The frozen Certification-Repair Ablation v1 provides the corresponding outer-loop
transaction template: compare control, one-shot certification, and retryable replay on
the same repositories; promote the retry mechanism only from first-failure-to-later-pass
transitions, never from aggregate score direction alone.

### 17. Two-Axis Boundary Transaction

The Readux validity pilot supplies a mandatory rollback condition for the future outer
loop: Official success increased because a candidate changed verifier behavior, while the
same shared policy rejected legitimate repository-derived configuration. Auto-EnvSolve
must retain `official_goal_pass` and `protocol_admissible` as independent axes. A version
that gains on the first by regressing the second is rolled back, and a measurement repair
is never counted as an inner-algorithm improvement.

Every boundary proposal must carry two fixed tests: an adversarial verifier-interference
counterexample and a provenance-grounded legitimate-configuration non-regression control.
Only after both pass may the version be compared on fresh repository identities.

### 18. Submitted-Program Boundary Transaction

The `trader` calibration case adds a full rollback-and-repair transaction for the future
outer harness. Boundary v2 rejected direct project-native package synchronization while
accepting a trajectory that temporarily created protected build configuration and erased
it before final-state inspection. Auto-EnvSolve must therefore compare versions on both
operation history and the fresh state produced by the submitted program; final
filesystem equality alone is insufficient.

Boundary v3 is promoted as a measurement version, not an inner algorithm version. Its
promotion evidence contains an adversarial historical program, a legitimate
content-locked package-manager program, cross-platform mounted-worktree checks, frozen
source hashes, and infrastructure censor masks. Future automatic boundary proposals must
carry the same typed evidence bundle and must never learn repository-specific path
allowlists from a consumed calibration case.

### 19. Versioned Build-Provenance Transaction

Boundary-v5 adds a concrete promotion example. A native-only proposal reduced one false
rejection but failed its preregistered paired calibration because standard build-tree
source copies remained invalid; the outer system must preserve that version as rejected,
not patch its result in place. The promoted successor uses one repository-agnostic
committed-source provenance rule and passes positive in-repository/external controls plus
modified, renamed, and source-less negatives.

Auto-EnvSolve should treat this as a versioned measurement transaction with immutable
proposal, calibration, adjudication, rollback, and successor hashes. It is not an
inner-algorithm reward event, and its consumed repository cannot enter the successor's
effectiveness estimate.

### 20. Minimal Outer Interface from EnvSolve-Pro V2

The frozen F/S/R/minimal-H design makes the future outer optimization boundary explicit.
Auto-EnvSolve may propose changes to soft-counterexample representation, replay timing,
or recovery interfaces, but not to the Official evaluator, public goal, split identity,
or a proposal's own generating cases. Each transaction begins with cross-case trajectory
statistics, makes one minimal generic change, and compares old and new versions on a
disjoint shadow batch. Any Official Pass regression triggers rollback; resource gains
support promotion only when success does not decrease.

The append-only trace now separates model requests, provider attempts, shell operations,
complete-program hashes, clean replay, Official outcomes, and infrastructure censoring.
The Dev-12 freeze, identity-only selection, paired order, and infrastructure amendment
are concrete control-plane examples for the later outer system, but remain
researcher-operated evidence rather than an Auto-EnvSolve result.

### 21. Deterministic-Dose Promotion Interface

The optional-ledger pilot adds a stricter outer-loop rule: a component cannot be promoted
when the treatment merely makes it available. One of four treatment episodes never
called the tool, so its `3/4` versus `2/4` direction is not a qualified mechanism result.
Auto-EnvSolve must require a versioned intervention schedule, per-episode dose-compliance
evidence, and a minimum complete-observation rate before comparing outcomes.

The successor transaction changes one dimension only: optional observation becomes
initial, periodic, and pre-replay observation at a frozen cadence. The outer optimizer
may later propose another cadence or representation, but it must preserve free Agent
operations, replay semantics, evaluator isolation, and the fixed shadow batch while that
proposal is judged. Analysis-pipeline corrections are separately versioned measurement
repairs and never receive algorithmic reward.

### 22. Ceiling-Batch and Heterogeneous-Efficiency Transaction

The target-state replay development expansion adds a negative outer-loop decision that
must be reproducible. A 4/4 versus 4/4 ceiling batch preserved success and produced one
feedback-conditioned network repair, but it supplied no effectiveness contrast. Aggregate
treatment resources fell sharply while paired medians did not improve because one pygeo
trajectory dominated the totals. Auto-EnvSolve must therefore reject both "run more random
cases" and "promote for aggregate efficiency" as next-version decisions.

Future version selection must inspect paired dispersion, mechanism activation, and failure
strata before choosing a shadow batch. Ceiling-heavy sampling triggers a switch to an
outcome-blind stratum of pre-existing strong-baseline Official failures. Compatibility
repair, acquisition-robustness repair, and first-replay certification remain separate
transition classes; no class can be converted into a permanent rule from one generating
repository.

### 23. Candidate-Retention Transaction from Bad-6

Bad-6 identifies a future outer-loop optimization unit that is simpler than adding
compatibility rules. In ajenti, both inner methods reached the public executable goal and
then failed to deliver while pursuing broader runtime completeness. Quacc B failed before
candidate formation, while HARK showed that replay works once a candidate exists. A future
Auto-EnvSolve proposal may therefore change only candidate retention and stopping behavior:
preserve the first goal-passing candidate, expose it to target replay, and keep optional
completeness exploration on a separate path.

The comparison record should retain first goal-pass time, preserved candidate, replay
outcome, later exploratory actions, final selected program, Official outcome, completeness
flags, and resources. Promotion remains success-first: path-quality or resource improvement
cannot compensate for an Official regression, and a successful candidate must not be
discarded because a later exploratory path failed. This is a generic harness transaction,
not a repository-specific package rule and not part of the first EnvSolve-Pro algorithm
until a new disjoint development batch validates it.

### 24. Negative Retention Transaction

The prospective retention study is a required rollback example for the outer loop. The
bundled treatment regressed from control `6/6` to `5/6`, increased common-success cost,
and never activated fallback. Auto-EnvSolve should therefore reject that version rather
than preserve it because the mechanism was plausible or passed unit tests.

The qibolab trace adds a sharper proposal unit: change only the transition from a trusted
full-goal Pass to cumulative-program delivery. Future outer-loop records should compare
`first_goal_pass`, `first_program_proposal`, `first_clean_replay`,
`goal_to_candidate_delay`, `goal_pass_without_candidate`, and `fallback_activated` across
versions. A proposal that merely renames prompt guidance as a trigger must not receive
mechanism credit; activation requires an observable controller transition and a submitted
program. This remains future outer-loop evidence, not part of the first paper's method.

### 25. Certified-Program and Wrapper-Outcome Transaction

The PlatformIO screen failure adds a distinct outer-loop transaction. The Agent's final
program passed both fresh clean replay and an Official counterfactual, while the shared
wrapper recorded Pass@1 failure because a temporary construction-workspace directory had
been removed. Auto-EnvSolve must compare `agent_program_valid`, `clean_replay_pass`,
`wrapper_admissible`, and `official_outcome` separately rather than proposing an
algorithm patch from one terminal label.

The proposal should establish which state is authoritative for delivery while retaining
the construction audit as diagnostic evidence. Promotion requires a real tampering
negative, a legitimate cleanup control, and a repository-disjoint shadow batch that did
not generate the proposal. Correcting a wrapper false negative is a measurement-version
change, never an inner deployment-policy gain.

### 26. Atomic-Handoff and Boundary-Adjudication Transactions

The consumed three-case handoff study provides one positive proposal transaction and one
measurement rollback example. The proposed inner change is narrowly scoped: after a
trusted complete-goal Pass, require cumulative-program delivery on the next request; if
fresh replay fails, restore free repair in the same session. An outer optimizer should
compare activation rate, goal-to-submission delay, replay sequence, same-session repair,
Official outcome, and resources against the preceding version. It must not infer package
rules from Quacc, Ajenti, or Hark.

Ajenti shows why measurement versions require separate attribution. The original episode
remains Fail, while a no-model replay of its unchanged candidate passes after correcting a
false-positive provenance boundary. Auto-EnvSolve should retain both records and mark the
episode `harness_boundary_censored`; it must neither reward the old boundary nor relabel
the adjudication as a new solver success. A future promotion rule should estimate algorithm
effects only from episodes valid under the measurement version being compared.

### 27. Current-Goal Rejection Transaction

The fixed three-pair current-goal replication is a compact rollback example for the outer
optimizer. The component was invoked in every treatment episode and returned a complete
Pass in all three, yet it did not shorten known-Pass-to-first-replay latency, did not
increase unambiguous Official success, and produced mixed resource changes. One treatment
also reached the benchmark goal without installing the project, showing that path quality
can move independently of the primary endpoint.

Auto-EnvSolve should therefore reject promotion even when aggregate requests and wall time
fall. Its comparison record must retain mechanism activation, first trusted Pass, first
manual Pass, first replay, strict Official outcome, acquisition censor status, and
deployment-completeness annotations. The accepted successor is the previous Minimal B
version, while the current-goal tool remains available only for diagnosis and future
orthogonal experiments.

### 28. Bad4 Non-Activation Rollback Transaction

The fixed Bad4 comparison is a direct outer-loop rejection example: `F+O+R` and `F+O`
both score `2/4`, and neither failed treatment invokes replay. Auto-EnvSolve must not
promote a version because a component exists, successful cases become cheaper, or traces
become more elaborate. If the defining transition is absent on the target failure
stratum, the version is retained as a baseline and the next proposal is redirected to
candidate formation.

Pysnmp also separates measurement repair from solver promotion. The Python 3.9 audit fix
may advance a measurement version after regression and exact-program replay, but it is not
an inner-policy gain. Future comparison records retain candidate formation, mechanism
activation, measurement censoring, Official outcome, and deployment completeness as
separate fields.

### 29. Early Mechanism-Activation Rejection

Incremental Program V1 gives the outer loop a cheaper rejection signal than waiting for a
full success batch. In three consumed episodes, the defining mutation tool appeared once
among 70 shell-like calls; two cases never invoked it, and HARK sent a real install through
the old shell path. Auto-EnvSolve should therefore test whether a proposal's defining
transition appears naturally before estimating its success effect. A version with absent
or very late activation is rolled back as an interface failure, while the underlying
hypothesis remains untested.

This diagnostic cannot promote a version and must not become a rigid universal threshold.
The proposal record retains expected transition, observed call opportunities, first
activation, bypass examples, provider errors, and the stop decision. The next proposal may
change one interface choice, but it may not infer package rules from these repositories or
attribute recovered network errors to the solver.

### 30. Immutable Evidence, Mutable Plan Transaction

Incremental Program V2 is a two-level outer-loop example. The proposed single-shell
annotation passes its early activation test: both episodes with an observed deployment
operation used `persist`, and HARK reached an automatic replay. The larger append-only
algorithm still fails its representation test because that replay invalidated an earlier
path choice and the current program could only accumulate compensating steps. An interface
may therefore qualify while the algorithm containing it is rolled back.

Future Auto-EnvSolve comparisons should keep execution events and replay counterexamples
immutable while treating the current deployment plan as a revisable hypothesis. Promotion
requires downstream evidence that replay feedback changes the certified plan, not merely
that a tool was called. The minimal successor transaction adds indexed replace/delete,
replays after each edit, and records the before-plan, counterexample, edit, after-plan, and
outcome. It does not optimize packages, prompts, checkpoints, or cross-case policy, and no
resource improvement may compensate for an Official regression.

### 31. Editable-Plan Qualification and Transactional-Edit Proposal

Incremental Program V3 supplies a positive mechanism transaction without supplying an
effectiveness result. A consumed HARK retry contains the complete replay-counterexample,
same-session plan edit, revised-program replay, final replay Pass, and Official Pass chain.
The outer system may therefore mark mutable plan state as mechanism-qualified, but it may
only promote that version into a disjoint effect test, not into the final inner algorithm.

The same trajectory exposes a compositional defect suitable for one minimal successor
proposal. Multiple numeric-index edits emitted in one model response were applied
sequentially, so early deletions shifted later targets and produced invalid calls. An outer
proposal may replace this with one transactional batch edit: interpret all edits against the
pre-edit plan snapshot, apply them atomically, and replay the resulting program once. The
proposal must compare edit errors, replay count, counterexample-to-valid-plan latency,
Official outcome, and path quality against V3. It should not add stable IDs, checkpoints,
package rules, or new gates unless later evidence demonstrates a separate need.

The final HARK program also shows why outer-loop reward cannot collapse to Official Pass.
It passed the benchmark while leaving an unused environment, omitting project installation,
and overriding a declared dependency constraint. Auto-EnvSolve should retain Official success
as the first lexicographic objective, then record clean reproducibility, completeness,
declaration fidelity, and resources as separate non-compensating axes. A path-quality gain
cannot excuse an Official regression, and an Official tie does not imply equivalent deployment.

The researcher-operated successor implements the proposal as V4 without rerunning its generating
HARK episode. This is the correct outer-loop split: consumed evidence proposes one generic change,
cross-platform deterministic tests establish its semantics, and a disjoint outcome-blind batch
estimates effect. Future Auto-EnvSolve versions should preserve this separation instead of using
proposal-generating trajectories as promotion evidence.

### 32. Interface-Parity Audit and Early Study Rejection

The first V4 Hard6 launch supplies an outer-loop rejection that precedes outcome comparison.
Minimal B received an explicit path-independent fresh-replay contract, while the incremental
prompt returned before that instruction. V4 then persisted construction-only absolute paths;
Conan repaired them after several edits and PyRollbar repeatedly misclassified the resulting
internal missing imports as network or dependency failures. Auto-EnvSolve must audit the
model-visible information, tools, evaluator access, and replay coordinate frame of both arms
before assigning algorithm credit.

When such an interface mismatch becomes causally established, the outer loop should stop the
affected batch, retain every raw trajectory, censor effect estimates, and propose the smallest
parity correction. It must keep the prospectively fixed case identities rather than selecting
new cases after seeing outcomes. Measurement/interface corrections and algorithm proposals remain
separate version transitions; only the corrected rerun can drive promotion or rollback.
