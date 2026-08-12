# EnvSolve-Pro：面向仓库部署的部分可观测状态化约束求解

状态：进行中的 ICLR 论文主稿，2026-08-11

## 摘要

自动部署一个陌生仓库，不只是生成安装命令。Agent 在不断变化的环境中观察执行结果，推断尚未满足的
兼容条件，并交付一段能够在干净环境中重建成功状态的程序。构建环境中的成功并不保证程序可重放；
事后 evaluator 又只能在 Agent 停止后暴露这一差异。因此，仓库部署是一个**部分可观测的状态化约束
求解问题**。

我们首先建立可审计的部署轨迹，并用 Observation--Constraint--Operation 三层因果框架分析多个部署
系统的失败。初步证据表明，主要矛盾不是缺少更多包规则，而是关键兼容事实只在干净重放中出现、执行
证据没有转化为下一步修复，以及硬约束会拒绝强 Agent 的合法方案。基于这些发现，我们提出
EnvSolve-Pro：Agent 保持一个连续 session，自由操作持久构建环境；它可在 session 内把完整部署程序
提交到独立干净环境，并收到保留原始证据的软反例约束，再继续修复同一程序。所有比较系统共享同一
实验完整性底座；该底座保证实验有效，但不属于部署算法。

我们将用 Official Pass@1 评估 EnvSolve-Pro，并通过同模型配对和外部 baseline 检验成功率、失败分布
迁移与成功优先的资源效率。当前方法和 Dev-12 配对实验已经预注册；前三个配对产生两条可审计的
feedback-conditioned repair，但双方 Official Pass@1 都是 2/3，因此只证明机制激活，不构成效果结论。

## 1. 问题定义

给定仓库、精确 revision 和基础镜像，Agent 通过交互操作形成构建状态 \(C\)，并返回部署程序
\(P\)。真正交付的环境不是 \(C\)，而是从干净初始状态 \(E_0\) 执行程序得到的状态：

\[
E_P = R(P, E_0).
\]

部署成功要求公开目标 \(G\) 在 \(E_P\) 中成立，同时程序没有干扰评测边界 \(I\)：

\[
G(E_P)=1 \land I(P,E_P)=1.
\]

### 为什么是部分可观测

Agent 不能一次看到完整兼容状态。依赖解析、构建隔离、ABI、硬件、网络、shell 状态和 checkout
所有权只会在特定操作后暴露。更重要的是，持久构建环境与最终干净环境不是同一个状态：失败命令可能
部分生效，交互过程可能留下隐式状态，最终程序也可能漏掉关键步骤。Agent 对“当前能工作”和“程序
能够重建”之间的差异只能通过执行继续观测。

预算不是问题定义的一部分。时间、token、网络、磁盘和内存是实验条件与结果指标；在相同安全 deadline
下应优先完成部署，再比较达到相同或更高成功率所需的资源。

## 2. 三层失败框架

我们把轨迹中的最早决定性原因分到三层，而不是按最终报错字符串归类。

### 2.1 观测层：发生了什么

观测包括命令结果、环境身份、候选程序执行、公开目标和完整性检查。失败发生在必要事实从未被看到、
干净环境暴露了不同事实，或部分与基础设施观测被误当成确定结论。

### 2.2 约束层：现在必须满足什么

约束是从证据推断出的兼容义务，例如运行时、版本、构建依赖、系统库、ABI、平台或状态传播要求。
失败发生在遗漏约束、错误合并冲突，或把狭窄榜单目标误当成完整部署语义。

### 2.3 操作层：怎样改变环境

操作是 Agent 为解除 active constraint 选择的环境变换。失败包括动作无效、顺序错误、成功状态不能
被最终程序重建，以及 harness 在执行前拒绝合法方案。跨层闭环失败单独标记：证据没有形成约束、约束
没有影响下一步操作，或修复没有在必须成立的状态中重新验证。

## 3. 方法

我们把部署机制与实验有效性分开。四种可组合的机制描述 deployer 如何解决兼容问题：

- **F，自由反馈搜索：** Agent 根据普通执行反馈自由选择操作；
- **C_h，硬约束部署：** 编码的兼容规则强制、拒绝或改写操作及候选程序；
- **C_s，软约束部署：** 将执行证据概括为可操作义务，同时保留原始证据并保持动作空间开放；
- **R，干净重放与恢复：** 在新 checkout 和基础环境中执行完整程序，把失败返回同一个活跃 session。

所有系统共享实验完整性底座 **E**：隔离 Official evaluator，保护仓库和目标身份，绑定精确提交脚本，
并保存内容寻址 artifact。E 不推断兼容性，也不选择动作，因此不是算法 treatment。连续 session 权限
同样在受控 arm 间保持一致。

EnvSolve-Pro 是最小组合 **F+C_s+R**：

算法为：

```text
P0 <- Agent 在持久构建环境中形成完整部署程序
for t = 0, 1, ...:
    Et <- 在独立干净环境中执行 Pt
    Vt <- 在公共 E 下运行公开目标
    if Vt 通过:
        认证 hash(Pt)，Agent 返回同一程序
    else:
        ct <- 从失败中提取软约束，并附带有界原始证据
        Pt+1 <- 同一 Agent session 自由修复完整程序
```

这里没有包规则库、候选图、跨 case 记忆、模型训练、物理 checkpoint 或 harness 自修改。最终程序必须
从启动时的当前仓库根目录推导路径，且只有通过重放的精确脚本 hash 可以提交。Official evaluator 始终
在 episode 结束后运行，其输出永远不进入循环。

## 4. 三项贡献

1. **因果失败研究。** 构建跨系统轨迹观测方法与 Observation--Constraint--Operation taxonomy，量化
   不同部署范式在哪里失败，而不是只报告总成功率。
2. **EnvSolve-Pro。** 提出一个最小的 verifier-guided repair 算法，将强 Agent 的开放搜索、软反例
   约束和同 session 干净重放组合起来，同时避免类别式硬规则压制模型能力。
3. **受控实证。** 在同模型配对、匹配系统 baseline 和独立 frontier reference 上检验 Official Pass@1、
   错误迁移、同模型增益与成功优先的资源 Pareto 效率，并将榜单成功与部署完整性作为两个评价轴。

## 5. 实验

### 5.1 研究问题

- **RQ1：** 不同部署范式的失败如何分布在三层框架中？
- **RQ2：** 在模型和评测权限相同时，F+C_s+R 是否优于 F？增益是否真实来自 replay 失败后的继续修复？
- **RQ3：** 在 DeepSeek V4 Pro 上，EnvSolve-Pro 与 Repo2Run、EnvBench Agent 和旧硬约束 EnvSolve
  相比如何，原生 Codex 给出的独立 frontier reference 位于哪里？
- **RQ4：** 在成功率相同或更高时，方法是否减少时间、token、网络、磁盘或内存开销？

### 5.2 数据协议

EnvBench 的 329 个 Python case 被额外划为 Dev 209、Canary 20 和 protected test 100，三者按仓库身份
互斥。历史已消费轨迹只用于 taxonomy discovery；按系统与主失败类别分层确定性抽取 20% 样本独立
复标，并报告原始一致性、Cohen's kappa 和 adjudication。当前 Dev-12 从排除已有终局证据后的 56 个 Dev case
中，仅按预先冻结的 salted hash 选择；选择不读取仓库内容、成败或错误类别。算法冻结后打开 Canary，
最终再运行 protected test 与官方完整协议。

### 5.3 比较方法

当前 Dev-12 配对共享 E、`deepseek/deepseek-v4-pro`、Cloudflare endpoint、镜像、架构、公开目标、
安全 deadline、连续 session 权限和 Official evaluator：

- **A：F**，同模型自由 Agent，没有 session 内 clean replay；
- **B：F+C_s+R**，即 EnvSolve-Pro。

Dev-12 按原预注册保持不变，只作为机制 pilot。完成后从冻结 reserve 中 outcome-independent 地选择新的
Dev-16，比较 F、F+R、F+C_s+R，以及作为代表性 F+C_h+R 系统的冻结旧 EnvSolve，共 64 个 episode。
F+R 对 F 隔离 replay，F+C_s+R 对 F+R 隔离软约束规范化。EnvSolve-Pro 对旧 EnvSolve 只能解释为
软约束系统和硬约束系统的系统级比较，因为两者除约束机制外还有实现差异。外部比较还包括 EnvBench
FreeAgent、Repo2Run 和原生 Codex，均保持原生语义。

### 5.4 指标

主指标是 Official Pass@1。机制指标包括首次 replay 失败率、feedback-conditioned repair、terminal
class 和成对错误类别迁移。资源指标包括 wall-clock、token、工具调用、replay 次数与时间，以及可直接
测量的网络、磁盘和峰值内存。基础设施事故单独删失，不用重跑覆盖算法失败。

## 6. 当前证据与可证伪条件

回顾性强 Agent census 的当前 50 个终局 episode 包含 28 个 Official Pass、11 个 Official Fail、5 个
Official 前硬边界失败和 6 个基础设施删失。重复机制包括干净 checkout 所有权漂移，以及类别式硬规则
拒绝本地配置、第三方布局修复或兼容产物；其中已有三个被拒程序在非计分 Official 反事实中通过。
另一方面，现有 advisory replay 与 Official 在 38 个可比较 episode 中只一致 22 个，说明 replay 必须
提高保真度并作为软证据，而不能成为新的硬门。

这些证据支持方法设计，但不证明效果。Dev-12 已运行八对，其中六对具备双臂可观测的 Official 结果，
两个 arm 在这些配对上均为 5/6。EnvSolve-Pro 已产生三条可审计的 feedback-conditioned repair 和三条
首次 replay 认证。最清楚的终止轨迹中，两臂使用近似依赖策略：EnvSolve-Pro 在 replay 后于第 15 次请求
提交，F 却对已满足目标反复检查到第 43 次；但前一条修复轨迹中 EnvSolve-Pro 的 token 与生成时间均多
约 61%，并且它还有两次未形成 replay 候选。因此当前证据支持修复与终止机制，不支持通过率或无条件效率
优势。剩余 Dev-12 和新的 Dev-16 必须检验可重复性；若不能，我们将收缩主张，而不是继续增加规则。

## 7. 局限

EnvBench Official 主要测量缺失导入，不能单独证明完整运行时部署。我们因此把 Official success 与
部署完整性分开报告，但不以自定义完整性指标替换排行榜指标。当前方法还不学习跨 case 经验，也不自动
搜索 harness 设计；这些能力不属于本文。
