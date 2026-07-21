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
| P1（完成） | 建立公平比较接口 | 开放程序、fresh execution、effect audit、adapter precondition | 6 条已消费轨迹均无表示层拒绝 |
| P2（完成） | 找出主要矛盾 | 跨方法 failure decomposition | 一个高频、可干预且非 harness 假象的瓶颈 |
| P3（进行中） | 设计最小三层算法 | certified/admissible 候选状态及消融 | 新机制有反例、测试和预注册预测 |
| P4 | 小规模成对验证 | 至少 5 个未见 Dev case 的 paired pilot | 出现成功率或 terminal repair 的正向信号 |
| P5 | 扩大 Dev 验证 | 多模型、多 case、Mac/Spark 一致性 | 效果跨 case 和模型保持，失败可解释 |
| P6 | 冻结与确认实验 | Canary、Official Test、论文主表 | 代码、prompt、baseline、指标全部冻结 |

P0 期间不得根据 EnvSolve v1 的既有 case 添加仓库特定规则。新的 parser、constraint 或 guard 必须来自
多个独立轨迹，或者来自任务定义本身的确定性不变量。

### 4.1 P0 审计结论

五个 case 的 P0 batch 已完成。20 个计划方法位置没有出现 official pass，但这不是 effectiveness 估计：
Codex 有 4 个位置因 executable drift 变成 Unknown，wrapper 也独立删失了原生轨迹。Repo2Run 与 raw
ReAct 各自在原生环境解决 2 个 case，冻结 EnvSolve 在 fresh container 中内部接受 2 个方案。其中 3 个
原生成功没有进入等价的官方执行，原因是 replay 丢失成功操作或其 ambient runtime；EnvSolve 的两次内部
接受也都暴露了 internal-versus-terminal contract mismatch。

因此 P0 的主要矛盾首先是方法学问题：强 native solver 可以构造工作环境，但封闭的 post-hoc command
parser 或不等价的 verification workspace 会抹掉成功。在 P2 把剩余失败归因给部署算法前，P1 必须先修复
这个接口。

P1 遵循一个最小原则：把模型的完整 candidate program 视为开放程序，在隔离的 fresh environment 中执行，
再根据可审计 effect 与 executable postcondition 判断安全性和正确性。command schema 仍可用于状态摘要与
causal replay，但 schema 未覆盖本身不能证明 candidate 无效。benchmark adapter 必须声明 workspace
precondition，使内部执行和 terminal execution 从等价的非 outcome 状态开始。

### 4.2 P1 审计结论

P1 已完成。6 条冻结 Raw ReAct/Repo2Run 轨迹全部可编译，没有 unsupported operation；5 次最终官方重放
全部到达 terminal evaluation，没有 representation rejection，但也没有 Official Pass。这个负向效果结果
是有信息量的：公平接口暴露出真实残余 Pyright 失败、原生测试与榜单目标不一致，以及 `build_output/`
引发的 package-discovery 冲突，而不是用 Unknown 把它们遮住。

冻结 EnvSolve 的 `importlib_metadata` 候选在 materialize adapter 声明的 `build_output/` 后，也在内部验证
中失败。因此 P1 按冻结预测解决了 P0 的测量矛盾，没有加入仓库特定 solver rule。详细证据单独保存在
`PRO_P1_FAIR_INTERFACE_RESULTS_V1_ZH.md`；这些已消费 case 不能再支撑下一阶段效果声明。

### 4.3 P2 冻结诊断设计

P2 从剩余 118 个 untouched Dev 中仅按元数据抽取 6 个 case，执行 24 个 salted position：Codex native、
Repo2Run、raw ReAct 和 P1 EnvSolve-pro scaffold。主分析单位是最早决定性修复机会，归因到 Observation、
Constraint、Operation 或 unresolved。只有同一可干预矛盾出现在至少 3 个仓库和 2 种方法中，才允许提出
新机制；抽样后整批 immutable，禁止修改 solver 或 wrapper。

### 4.4 P2 审计结论

24 个位置已全部完成。由于多数 Codex、Repo2Run 位置以及两个 raw ReAct 位置受到 baseline adapter 或
完整性审计删失，本批不能作为效果对比。EnvSolve-pro 与 raw ReAct 分别在不同仓库获得一次 Official
Pass，把它们写成可比较的 1/6 会违反实验有效性。

三个仓库出现了同一个确定性主矛盾：完整性有效的候选以零退出码完成内部执行，但任何残余内部约束
都会让 EnvSolve 丢弃候选，不进入终局评测。部分内部证据被当成了精确 terminal oracle。因此 P3 只
引入一个最小区分：`certified` 候选满足内部目标；`admissible` 候选完成安全重放，但仍有未解决内部
约束。系统保留最佳 admissible 候选，并可用 `uncertified` 状态输出；内部目标仍为 blocked，Official
evaluator 仍然 terminal-only。

第二个跨仓库模式是 runtime、dependency lock 与 platform compatibility。它被冻结为次级假设；在更小的
候选保留机制得到资格验证前，P3 不实现这套更大的结构。

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

先在已消费 case 上完成 certified/admissible 区分的重放资格验证，并修复无效的外部 baseline adapter，
但不改变 baseline 求解策略。随后冻结 P3 消融，抽取至少 5 个新的 outcome-blind Dev pair，对比开启与
关闭候选保留时的终局成功。该最小机制得到或未得到预测信号之前，不增加 runtime closure 机制。
