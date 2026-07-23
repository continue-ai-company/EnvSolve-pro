# EnvSolve：部分可观测仓库部署的状态化约束求解

> 持续更新的 ICLR 论文稿。英文版：
> [`ENVSOLVE_ICLR_RESEARCH_PLAN.md`](ENVSOLVE_ICLR_RESEARCH_PLAN.md)。
> 工程演进与逐轮实验账本保留在详细研究计划中，不进入本文正文。

## 摘要

部署一个陌生仓库，本质上是在恢复一组隐藏的运行时、依赖、构建和平台条件。这些条件无法被直接
观测：执行只能暴露不完整且可能有歧义的症状，网络和基础设施故障甚至可能完全无法说明候选环境
是否正确。因此，相比自由生成 shell 命令，仓库部署更适合被建模为部分可观测的状态化约束求解。

本文提出 **EnvSolve**，一个三层部署 Agent。**观测层**将仓库声明和 fresh execution 转换为带来源
的证据；**约束层**只把依据充分的证据接纳到由事实、冲突、假设和未解决义务组成的持久状态中；
**操作层**把该状态转换为能够解除冲突的完整部署程序。每个候选都在 fresh environment 中执行，
只有内部执行反馈可以更新状态；官方 evaluator 仅在终局调用，绝不提供修复反馈。

我们在 EnvBench 上将 EnvSolve 与 Repo2Run、原生 Agent，以及使用同一 backbone 的 raw-history 和
reflection loop 比较。实验匹配模型访问、在线信息、官方 evaluator 权限和原始资源上限，测量最终
部署成功率、terminal reach、修复效率、失败重复率和 clean replay。确认性的 held-out 实验尚未完成，
因此本文当前不作效果或榜单声明。

## 1. 引言

从源码运行仓库是测试、程序分析、迁移、安全审计和大规模项目复现的前提，但部署常常在这些任务
开始前就失败。一个 missing import 可能来自缺失 distribution、不兼容的语言版本、平台分支，或者
错误的项目安装方式；一个失败的包管理命令也可能来自 ABI 冲突、缺失构建工具或临时 package-index
故障。相似日志可能对应不同原因，同一个原因也可能产生不同日志。

这使仓库部署成为对隐藏环境状态的推理问题。仓库并不提供完整、可执行的有效环境规格。Agent 可以
读取 metadata 和源码，但只有执行部署程序后才能知道它是否可行；即便如此，观测仍然不完整：安装
成功不代表所有源码可见 import 都能解析，带网络签名的 timeout 也不能证明候选环境本身有错。

多数基于语言模型的部署 Agent 使用对话式 loop：生成命令、执行、把日志追加到上下文，再让模型
重试。这个 loop 有用，但状态是隐式的。原始历史不会说明哪些观测是事实、哪些假设已被反驳、哪些
失败仍有歧义，也不会说明下一次从干净环境开始时必须保留哪些历史操作。自然语言 reflection 能压缩
历史，却仍把证据接纳和状态一致性交给自由文本生成。

EnvSolve 将部署推理解耦为三个显式层次：

1. **观测层：**发生了什么，执行暴露了什么证据？
2. **约束层：**现在知道什么，冲突在哪里，还有什么未解决？
3. **操作层：**怎样改变环境才能解除这些约束？

三层形成闭环。系统根据当前约束状态生成完整部署程序，在 fresh environment 中执行，再把结果转成
新证据。只有通过确定性接纳规则的证据才能改变 hard state。这样既保留强编码 Agent 构造具体方案的
能力，也防止有歧义或被基础设施删失的反馈悄悄变成部署规则。

本文有三项贡献：

1. **问题定义。** 将仓库部署建模为部分可观测的状态化约束求解，区分隐藏环境状态、可执行观测和
   终局任务评测。
2. **三层算法。** 提出 EnvSolve，通过观测层、约束层和操作层实现带 provenance 的证据接纳，以及
   反例驱动的完整、可复现部署程序生成。
3. **受控实证研究。** 设计防泄漏的 EnvBench 实验，在信息和原始资源匹配的条件下比较 EnvSolve、
   原生 baseline 与同 backbone loop，并分别分析成功率、terminal reach、效率和 clean replay。

EnvBench 是检验方法的 testbed，不是 EnvSolve 的定义。Fresh container、artifact audit 和冻结 schedule
是实验控制，用于保证测量有效，不作为独立算法贡献包装。

## 2. 问题定义

给定固定 revision 的仓库 `R`，令 `Z_R` 表示其隐藏的有效部署条件，包括语言 runtime、ABI、package、
构建工具、系统库、平台谓词和环境变量。部署程序 `P` 是一段可重放的环境操作序列。它可以配置 runtime
和安装依赖，但不能修改应用源码、伪造缺失模块或削弱 evaluator。

在第 `t` 轮，solver 在 fresh environment `E_t` 中执行候选 `P_t`，并得到观测

`O_t = V(R, P_t, E_t; Z_R, xi_t)`，

其中 `V` 是内部可执行 verifier，`xi_t` 表示网络可用性和 package-index 状态等干扰因素。`O_t` 通常
无法唯一确定原因：多个隐藏状态可以解释同一失败，基础设施问题也可能完全删失候选结果。

因此，solver 维护显式状态

`S_t = (F_t, C_t, H_t, U_t, X_t)`，

其中 `F_t` 是有依据的事实，`C_t` 是 hard constraint 与 contradiction，`H_t` 是未解决假设，`U_t`
是操作义务，`X_t` 是带 provenance 的不可变原始证据。状态转移为

`S_{t+1} = Update(S_t, Admit(O_t))`。

它刻意不等价于把 `O_t` 追加到 prompt。`Admit` 决定一个观测能否修改 hard state、只能保持 provisional，
还是应被标记为 Unknown。

不变的官方 evaluator `Q` 只评测最终部署程序。其输出在在线 episode 中不可见，也不能进入 `S_t`。
研究目标是提高终局部署成功率。对 EnvBench Python，成功严格定义为 bootstrap 退出码为 0，且
Pyright 的 `reportMissingImports` 数量为 0；其他 Pyright diagnostic 不计分，也不能影响约束、
候选排序或机制选择。资源上限属于实验设置，而不是任务定义：被比较方法获得匹配的模型请求与
token、候选环境、可执行命令和 wall-clock 上限。

### 2.1 为什么部分可观测很重要

部分可观测来自三个方面。第一，仓库声明可能不完整、带条件或已经过时；第二，执行暴露的是症状，
不是隐藏原因；第三，基础设施可能删失观测。把每条日志都当作 hard fact 会让 solver 过拟合偶然故障；
完全不保留反馈又会反复付出代价去重新发现同一冲突。EnvSolve 正是围绕这一矛盾设计。

## 3. EnvSolve

### 3.1 总览

EnvSolve 执行如下闭环：

```text
S0 <- ObserveRepositoryAndBaseRuntime(R)
while 尚未 internal Pass 且资源未耗尽:
    U_t <- PlanOperations(S_t)
    P_t <- ProposeCompleteProgram(R, S_t, U_t)
    if not Validate(P_t, U_t):
        S_t <- UpdateWithPolicyCounterexample(S_t, P_t)
        continue
    O_t <- ExecuteAndVerifyFresh(R, P_t)
    S_t <- Update(S_t, Admit(O_t))
return 找到的 internal-pass program
```

模型负责提出具体程序，确定性模块则控制什么能够进入状态、候选必须覆盖哪些义务，以及一次执行是否
足以支持下一步修复。

### 3.2 观测层：发生了什么？

观测层把异构的仓库与执行 artifact 转换成统一证据结构。首次 proposal 前，受限的只读 observer 提取
标准项目声明，并观测精确 base runtime。Episode 中，每个通过前置验证的候选都在新的 checkout 和
container 中运行。系统记录候选、环境 identity、image digest、命令、退出状态、时长、verifier check
和有界 terminal evidence。

观测被分为：

- **Pass：**预先声明的内部义务已满足；
- **Fail：**可复现证据反驳了候选假设；
- **Unknown：**结果被删失，或无法归因于候选。

例如，确定性的 runtime version mismatch 是有依据的 Fail；一般 build error 可能只能支持 hypothesis；
带明确网络或 provider 签名的 timeout 是 Unknown；没有基础设施签名的命令 timeout 可以说明候选在固定
上限下代价过高，但不能推出具体 package 原因。

观测层绝不读取在线官方 evaluator 反馈，从而避免 test leakage，并保证最终评测是真正的 terminal
operation。

### 3.3 约束层：缺什么，冲突在哪里？

约束层是持久化推理状态。它根据证据强度和 provenance 接纳观测，而不是根据文本是否“听起来合理”。

有依据的正向观测成为 fact，确定性不兼容成为 hard contradiction，有歧义的解释保留为 hypothesis，
Unknown 不会成为候选约束。每个状态项都指向支持它的 candidate、environment、verifier 与原始证据。

状态更新满足三个不变量：

1. **不无依据地硬化。** 没有新 grounded evidence，hypothesis 不能升级为 hard constraint。
2. **不意外遗忘。** 后续没有重新观测某个变量，不代表未解决义务已经满足。
3. **同域替换。** 只有关于同一 domain、subject 和 predicate 的更新证据才能 supersede 旧 fact。

这些不变量把执行历史变成紧凑的状态转移系统。模型看到的是未解决 conflict、相关 fact、近期候选结果
和有界证据，而不是无限增长的 transcript。

Python 依赖检查说明了结构化状态的必要性。Runtime semantics 询问某个 import 在当前平台是否执行；
static source resolution 询问源码可见模块能否被解析。两者相关但不等价，EnvSolve 分开记录它们，
而不是压缩成一个 import-success bit。

### 3.4 操作层：怎样改变环境？

操作层将未解决约束映射为环境动作。确定性 planner 把有支持的状态投影为类型化 `OperationPlan`，例如
配置兼容 runtime、安装已声明依赖、选择项目安装方式，或保留在上一 fresh environment 中支撑某个
fact 的操作。

语言模型把计划实例化为完整部署程序。执行前，类型化 validator 检查三件事：

- 程序只改变环境；
- 程序覆盖所有有依据的 operation obligation；
- 程序不会在任何修复生效前，原样重放一个已知失败前缀。

被拒绝的程序返回 policy counterexample，但不消耗 container。通过验证的程序始终从干净状态运行。
因此，操作层不是简单推荐下一条 shell 命令，而是在说明当前约束将如何被解除后，构造一份自包含候选。

### 3.5 闭环 Solver

三层职责分离，但通过可执行反馈形成闭环：

`观测 -> 约束更新 -> 操作计划 -> Fresh execution -> 新观测`。

这才是 EnvSolve 与普通 ReAct 部署的算法差异。Raw-history 和 reflection baseline 可以使用同样多的
轮次、看到同样的原始反馈；EnvSolve 的区别在于哪些反馈能够持久化、contradiction 如何跨 fresh
environment 保留，以及持久状态怎样约束下一份完整程序。

## 4. 实验设计

### 4.1 研究问题

- **RQ1：效果。** 在信息和原始资源匹配时，EnvSolve 能否提高 Official Pass@1？
- **RQ2：机制。** 效果是否来自显式约束状态、证据接纳和 constraint-to-operation planning？
- **RQ3：效率与鲁棒性。** EnvSolve 能否减少重复失败、提高 clean replay，同时不依赖更多尝试或
  evaluator 反馈？

### 4.2 Benchmark 与划分

主要 testbed 是 EnvBench 的 329 个 Python 仓库。开发只使用官方 train partition 中已声明的 case。
机制决策在分别冻结、outcome-blind 的 development batch 上资格验证。算法冻结后 Canary-20 只使用
一次；方法、预算、baseline 和分析冻结前，Official-Test-100 保持 untouched。EnConda-Bench 不属于
本文。

本研究中的 EnvSolve 不进行跨 case 学习或经验检索。第一篇论文只研究单 case 内的状态化求解，并
保留轨迹供后续工作使用，不加入未经验证的 memory claim。

### 4.3 Baseline 与公平性

我们比较：

- EnvBench 固定原生 baseline；
- Repo2Run；
- 同 backbone 的 raw-history loop；
- 同 backbone 的自然语言 reflection loop；
- 移除持久 typed state 的 EnvSolve；
- 完整 EnvSolve。

核心因果比较匹配模型与 seed、仓库 revision、base image、raw online observation、官方 evaluator
权限和全局原始资源上限。所有 loop baseline 的每个候选都从 fresh environment 开始。官方 evaluator
只在产生内部 terminal candidate 后调用，且不向任何方法返回修复反馈。

预算报告模型请求与 token、候选环境、命令和 wall-clock。美元成本只是带日期的附属换算，不是科学
匹配变量。

### 4.4 指标

主指标是 EnvBench Official Pass@1。次指标包括：

- 自然到达 terminal official evaluation 的 run 比例；
- 首次候选失败后的修复成功率；
- 重复失败率和 constraint-resolution rate；
- 在新环境中的 clean-replay 成功率；
- 模型、环境、命令、token 和 wall-clock 消耗；
- 被删失的 Unknown，且与 candidate Fail 分开报告。

确认性比较使用 paired outcome 与 confidence interval。只有两种方法都产生可审计 Boolean official
outcome 时，该 pair 才有效。如果 terminal reach 不足，batch 只能支持 failure decomposition，不能
估计方法效果。

### 4.5 消融

核心消融每次移除一个机制：

- 类型化持久约束状态；
- evidence admission 与 Unknown censoring；
- provenance-aware state replacement；
- constraint-to-operation planning 与 guard；
- 完整候选的 fresh replay。

我们还会比较 typed state 与自然语言 reflection，并在多个预注册资源上限下报告 success-resource
curve。

## 5. 当前证据与剩余实验

当前实现、审计路径和三层 loop 已足以进入冻结的 development qualification。聚合开发证据支持三点。
第一，候选生成并非唯一瓶颈：失败可以来自观测校准、状态转移，以及约束到操作的映射。第二，基础
设施与 provider 故障必须被删失，不能转化为修复约束。第三，到达 terminal evaluator 本身就是必要
的诊断结果；如果 terminal reach 不足，paired deployment effectiveness 就不可识别。

Repository-free 合成反例证明：经过验证的失败 operation 可以进入持久状态，在 context 匹配时拒绝
精确重试，同时保留替代 operation。随后，冻结的 8-pair development pilot 将完整系统与同 backbone
raw-history ablation 比较。16 条 run 全部可审计；两种方法都在 4 个 case 到达 Official，并通过其中
2 个，没有 discordant pair。3 条 EnvSolve run 产生了 negative-operation fact，但精确命令 guard 没有
拒绝任何后续 proposal。因此 pilot 证明了执行可行性并暴露 mechanism-utilization gap，却没有证明
效果优势。

下一步在新的 outcome-blind development 样本上复现完全不变的系统。这把抽样不确定性与代码适配
分开，避免 consumed pilot trajectory 同时承担诊断与验证。Replication 完成后，才决定冻结系统是否
进入更大的 ARM64 Linux 执行，或者某个新的操作层假设是否需要 repository-free 反例与新的 development
freeze。Canary-20 与 Official-Test-100 继续保持 untouched。

最终论文包含三张核心结果表：

1. 所有 baseline 的 Official Pass@1 与 paired effect estimate；
2. 组件消融与 terminal-reach failure decomposition；
3. success-resource 与 clean-replay 分析。

确认性实验完成前，所有效果单元格保持为空，本文不作榜单声明。

## 6. 相关工作

EnvSolve 连接面向软件工程的语言模型 Agent、自动环境构建、execution-guided synthesis，以及 Agent
reflection 或 memory。它的区别不是“存在执行 loop”，而是在 terminal-only evaluator 下显式分离
观测、约束接纳和环境操作。

与自由格式 reflection 相比，EnvSolve 限制哪些证据可以改变持久状态；与经典 counterexample-guided
synthesis 相比，它面对的是带噪声、部分可观测且可能被删失的执行，而不是完整符号反例；与现有
deployment Agent 相比，它在 backbone、信息和资源固定时隔离状态表示与转移规则的作用。引用将在
related-work audit 后统一补齐。

## 7. 局限性

EnvSolve 不能在不违反 environment-only 任务边界的前提下修复应用缺陷。内部 verifier 只是 terminal
deployability 的近似，可能不完整。Fresh environment 提高因果清晰度，但增加时间与计算。网络和
package-index 故障会产生删失结果。当前研究只覆盖 EnvBench 的 Python 仓库；其他语言、操作系统和
跨 case adaptation 需要独立证据。

## 8. 结论

仓库部署困难，是因为有效环境隐藏在仓库背后，而每次执行只提供部分且带噪声的证据。EnvSolve 以
三层架构处理这一问题：观测执行、维护显式约束状态，再生成能够解除剩余冲突的完整环境操作。这个
设计把自由试错变成可审计的状态化求解，同时保留强模型构造具体程序的能力。最终需要回答的实证问题
非常明确：在公平、资源匹配的条件下，这种结构能否提高终局部署成功率；冻结的 held-out 实验将专门
回答这个问题。
