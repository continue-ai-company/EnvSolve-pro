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
