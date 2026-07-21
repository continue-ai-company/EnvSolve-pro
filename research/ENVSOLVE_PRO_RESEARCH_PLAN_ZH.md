# EnvSolve-pro 研究计划

## 1. 研究目标

EnvSolve-pro 研究陌生仓库的自动环境部署。核心问题保持不变：部署不是自由命令试错，而是一个
**部分可观测的状态化约束求解过程**。系统仍采用三层闭环：

1. **观测层：发生了什么？** 保真记录仓库证据、执行结果、环境身份和不确定性。
2. **约束层：现在缺什么、冲突在哪里？** 维护带证据来源的事实、假设、冲突和未解决义务。
3. **操作层：怎样改变环境来解除冲突？** 由强模型提出完整部署方案，系统验证执行边界和状态转移。

EnvSolve-pro 从冻结的 EnvSolve v1 代码和历史继续开发。旧仓库
`hongleo-Lee/EnvSolve` 已在提交 `07a208f` 以标签
`envsolve-v1-baseline-freeze-2026-07-21` 封存，作为可运行 baseline；所有新改动只进入
`hongleo-Lee/EnvSolve-pro`。

## 2. 研究原则

### 2.1 成功优先

主目标是 Official Pass@1 和可重放部署成功率。Token、模型调用、容器、命令和 wall-clock 是效率
指标，不是问题定义。系统仅保留防止无限循环和失控执行的宽松安全上限。确认性实验另外报告
success-resource curves，不以美元价格作为核心变量。

### 2.2 结构增强而非替代模型推理

强模型始终可以访问有界原始观测。约束层是带 provenance 的外部状态，不是唯一上下文。确定性 hard
guard 只保护任务边界、安全边界和被执行证据直接反驳的精确行为；其余约束作为可质疑的 belief 或
advice。模型可以提出 schema 未覆盖的操作，系统执行后再决定是否扩展状态。

### 2.3 Baseline-first

在提出新算法改动前，先真实运行 Repo2Run、Codex/native agent 和同 backbone raw ReAct。阅读代码只能
解释实现，不能替代对完整轨迹的观察。外部 baseline 的容器策略、反馈 loop、停止原因和失败恢复必须
进入统一轨迹分析。

### 2.4 防止开发集过拟合

诊断 case 与验证 case 分离。每个算法假设先由跨仓库失败模式和 repository-free 反例支持，再在新的
outcome-blind Dev batch 上验证。已经看过结果的 case 只能用于诊断，不能再次承担确认性证据。
Canary 和 Official Test 在算法、baseline 与分析规则冻结前保持 untouched。

### 2.5 开发阶段平台并行

Mac 和 DGX Spark 都可执行 Dev case，以提高实验吞吐。平台、架构、镜像 digest、网络状态和 provider
必须记录在轨迹中。开发阶段不把 host OS 当作算法变量；同一 paired comparison 尽量在相同执行镜像和
平台上完成。跨平台一致性在机制稳定后单独验证。

## 3. v1 资产审计

原样继承的基础设施：

- benchmark-independent runner、EnvBench adapter 与 Official evaluator 隔离；
- fresh environment provider、artifact manifest、审计与 schedule coordinator；
- append-only event log、hash-chained state、evidence provenance；
- Repo2Run runner、raw agent runner、结果汇总和失败分析；
- 已有单元测试、集成测试与冻结协议。

保留但必须重新验证的算法组件：

- `EvidenceNormalizer` 的 schema 覆盖率和错误硬化率；
- 固定 confidence threshold 是否有统计或语义依据；
- `domain -> operation kind` 映射是否遗漏强模型可发现的方案；
- typed replay validator 是否误拒绝合法部署程序；
- operation guard 是否带来终局收益，而不仅是可审计性；
- transcript 压缩是否保留解决当前冲突所需的原始证据。

## 4. 实验路线

| 阶段 | 目标 | 主要产物 | 进入下一阶段的条件 |
|---|---|---|---|
| P0 | 亲自观察外部 baseline | Repo2Run、Codex/native、raw ReAct 的统一轨迹与错误分类 | 至少 5 个新 Dev case，每种方法均有可审计 run |
| P1 | 建立公平比较接口 | 统一 case、evaluator 权限、原始观测和资源报告 | baseline 行为未被 wrapper 改写 |
| P2 | 找出主要矛盾 | 跨方法 failure decomposition | 一个高频、可干预且非 harness 假象的瓶颈 |
| P3 | 设计最小三层算法 | Observation/Constraint/Operation 可插拔接口和机制消融 | 新机制有反例、测试和预注册预测 |
| P4 | 小规模成对验证 | 至少 5 个未见 Dev case 的 paired pilot | 出现成功率或 terminal repair 的正向信号 |
| P5 | 扩大 Dev 验证 | 多模型、多 case、Mac/Spark 一致性 | 效果跨 case 和模型保持，失败可解释 |
| P6 | 冻结与确认实验 | Canary、Official Test、论文主表 | 代码、prompt、baseline、指标全部冻结 |

P0 期间不得根据 EnvSolve v1 的既有 case 添加仓库特定规则。新的 parser、constraint 或 guard 必须来自
多个独立轨迹，或者来自任务定义本身的确定性不变量。

## 5. 核心消融

为了检验结构化约束是否限制强模型，固定 backbone 后依次比较：

1. 原生 raw-history ReAct；
2. ReAct + 结构化 Observation；
3. ReAct + Observation + advisory Constraint state；
4. 上述系统 + grounded hard guards；
5. EnvSolve v1 frozen baseline。

同时跨至少两个能力层级的模型复现实验。若模型越强，hard planner 的增益消失或转负，则收缩 hard
mechanism，把贡献定位在可验证状态、执行闭环与恢复能力，而不是限制模型的动作空间。

## 6. 指标与统计

主指标：Official Pass@1。关键次指标：terminal reach、首次失败后的修复成功率、clean replay、重复失败
率和基础设施删失率。资源指标包括输入/输出 token、请求次数、候选环境、执行命令与 wall-clock。

报告 paired effect、置信区间和 failure-stratified analysis。基础设施 Unknown 不计作算法失败，但必须报告
比例。Internal verifier 仅用于在线反馈；Official evaluator 始终 terminal-only。

## 7. 当前下一步

暂停扩大 EnvSolve v1 内部消融。先从未消费的 Dev pool 冻结一个小批次，分别运行真实 Repo2Run、原生
强 Agent、raw ReAct 和 EnvSolve v1，逐条审阅完整轨迹。P0 的输出不是新规则，而是经证据支持的主要
矛盾和 P3 的最小算法假设。
