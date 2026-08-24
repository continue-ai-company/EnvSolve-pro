# EnvSolve-Pro：面向仓库部署的状态化约束求解

状态：ICLR 工作稿，2026-08-24；prospective 开发期 pilot 已否决 verifier-triggered handoff
作为提高成功率的核心机制

## 摘要

部署陌生仓库不只是生成命令。Agent 只能看到当前操作暴露出的部分兼容事实，操作又会改变环境，而且交互
工作区中的成功未必能从干净 checkout 中重现。我们将仓库部署定义为**部分可观测的状态化约束求解**。

我们首先记录端到端部署轨迹，并把最早决定性失败分为观测层、约束层和操作层。分析发现，一个反复出现的
问题是：Agent 能构造可用状态，却不能交付一段重建该状态的程序。EnvSolve-Pro 让能力强的 Agent 在一个
连续 session 中自由行动，测量完整公开目标，并从目标初始状态重放完整部署程序。重放反例作为 case-local
证据返回同一 session。方法不加入 package 规则库、checkpoint 搜索、跨 case 记忆或硬修复策略。

预注册的三 case 开发期 pilot 检验“可信构建 Pass 后强制程序化能否提高成功率”。结果不支持该假设：
Official 为 control `3/3`、treatment `2/3`；独立协议合规审计为 `2/3` 对 `1/3`，且没有
treatment-only Pass。因此我们否决 forced handoff 作为核心成功机制，只把它保留为成功率不下降后再检验
的效率 treatment。Official Pass@1 是主指标；时间、Token、流量、存储、部署完整性与协议合规分别报告。

## 1. 问题

给定仓库 revision (x)、基础环境 (E_0) 和公开可执行目标 (G)，Agent 与构建环境交互并返回部署程序
(P)。交付状态为

[
E_P = R(P, E_0),
]

其中 (R) 从目标初始状态执行完整程序。共享的完整性评测器判定 (G(E_P)=1) 时，部署成功。

问题是部分可观测的，因为依赖解析、构建隔离、Python 身份、系统库、ABI、硬件、网络和进程局部状态只会
在特定操作后出现。问题也是状态化的，因为每个操作都会改变后续观测。交互成功并不充分：失败命令可能
留下副作用，shell 状态可能只存在于当前进程，最终程序也可能遗漏探索阶段执行过的修复。

时间和请求上限是实验条件，不是问题定义。成功优先；资源在匹配的宽松安全上限下测量，只有保持成功后
才优化。

## 2. 因果失败框架

我们标注真正改变最终结果的最早失败，而不是最后一条报错。

### 2.1 观测层：发生了什么？

必要事实缺失、来自错误环境、发现太晚，或把局部事实当成完整事实，都属于观测失败。例如，用不同于提交
程序的 Python 做测试，或复用构建缓存却声称验证了干净部署。

### 2.2 约束层：现在必须满足什么？

执行证据没有转成成功所需的兼容条件，就属于约束失败。例如，混淆 import 名与 distribution 名、遗漏
构建依赖，或后续安装破坏了已经满足的 CPU/runtime 条件。

### 2.3 操作层：怎样改变状态？

所选操作不能满足 active condition、顺序错误，或没有进入最终程序，都属于操作失败。harness 的硬规则
也按同一因果原则分类：错误的准入要求属于约束失败；Agent 的状态变换违反正确要求才属于操作失败。

三个层次构成因果闭环：观测产生约束，约束指导操作，操作产生下一个状态和下一次观测。

## 3. EnvSolve-Pro

EnvSolve-Pro 组合自由反馈搜索、可信目标观测与目标状态反例重放。

### 观测层

Agent 获得普通构建反馈。Harness 按固定命令节奏在同一构建环境中测量完整公开目标。重放证据绑定仓库
revision、基础镜像和 fresh execution，观测完整程序，而不是某条命令或累积构建状态。

### 约束层

重放失败产生 case-local 软约束：当前完整程序与实际目标状态矛盾。原始证据始终可见，同一个 Agent 可以
修改或推翻解释。harness 不检索跨 case 规则，也不替 Agent 选择 package。

### 操作层

Agent 自由检查仓库并改变构建环境，可以随时把当前解法整理成完整程序并反复调用 clean replay。重放
失败把证据返回同一 session，但不规定下一步动作。只有从目标状态通过重放的同一份程序才能被交付。

```text
在构建环境中启动一个连续 Agent session

while 尚无通过重放的程序且宽松安全上限未耗尽:
    Agent 自由观测并改变构建环境
    定时测量完整公开目标
    if Agent 提出完整部署程序:
        获得完整部署程序 P
    else:
        continue
    y <- 从目标初始状态执行 P 和公开目标
    if y 通过:
        return P
    把 y 中第一个可执行反例返回同一 session

return failure
```

算法保存程序和执行证据，不保存容器 checkpoint；既不决定怎样修环境，也不在 construction Pass 后
强迫模型执行某个动作。修复 loop 仍在活跃推理 session 内，针对真正交付的完整程序，并从该程序实际
面对的初始状态执行。更强模型扩展的是操作层能力，不会被 harness 限制修复策略。Verifier-triggered
handoff 只作为已被否决的成功率 treatment，以及未来可能的成功条件效率 ablation 保留。

## 4. 三项贡献

1. **因果失败分析。** 提供可审计轨迹表示和观测层--约束层--操作层 taxonomy，比较不同部署思路最早的
   失败原因。
2. **最小部署算法。** 同 session 目标状态重放检验完整交付程序并返回可执行反例，不规定强 Agent 的
   修复策略；证据如何转成程序约束，是当前仍在开发的算法对象。
3. **受控实证。** 报告同模型因果比较、外部 baseline、强弱模型、Official 成功率、失败迁移和保持成功
   前提下的资源结果。

## 5. 实验设计

### 5.1 失败研究

我们标注 EnvBench Agent、Repo2Run、原生 coding Agent、旧硬约束 EnvSolve 和 EnvSolve-Pro 的科研
有效轨迹。基础设施失败单独删失。每条失败轨迹有一个带证据的主层级和若干机制标签；分层样本由第二位
标注者复核并报告一致性。已消费轨迹只用于发现 taxonomy，不能支持成功率比较。

### 5.2 同模型 handoff 实验

两组都使用连续自由 Agent session、相同的定时完整目标观测和可反复调用的干净重放。被检验的
treatment 只增加一个可执行转换：首次可信完整 Pass 后，下一次模型动作必须程序化并重放。触发前两组
工具和初始 prompt 完全相同。模型、基础镜像、仓库权限、构建环境、Official evaluator 和宽松安全上限
保持一致。Case 在查看 treatment 结果和打开仓库之前确定。第 6 节报告其负结果；该 treatment 不再是
本文核心算法。

主指标是 Official Pass@1。机制指标包括首次重放失败、反馈后程序变化、修复成功和 replay/Official
一致性。资源指标包括请求、Token、时间、网络流量、存储和首次认证时间；同时报告无条件结果和成功条件
下结果。

### 5.3 系统与模型比较

系统级 baseline 包括 EnvBench baseline、Repo2Run、冻结的旧 EnvSolve，以及作为独立能力上界参考的
原生 Codex。强弱 backbone 用于判断可执行反例是在增强模型，还是会被模型进步吞噬。开发数据只选择固定
机制和协议，held-out 数据估计效果；本文不训练模型参数。

Repo2Run 本身也是状态化 loop，而不是 one-shot baseline：它保留模型对话和构建容器，反复调用测试，
对部分失败的状态变换进行回退，并序列化成功命令历史。本文检验的边界更窄：Repo2Run 在累积构建状态
通过时终止，但不会从独立目标初态执行完整的序列化交付程序，再把反例返回仍然活跃的推理 session。

Official 成功与部署完整性分开。EnvBench 的 import-oriented 目标按官方定义报告；compatibility shim、
不可获得的硬件 runtime 和更广泛行为覆盖另行审计。

## 6. 当前证据

attempt 级重建目前包含 48 个 method--case row。第一轮完整轨迹裁决覆盖 38 条非成功记录中的 17 条：
观测 7 条、约束 3 条、操作 2 条、基础设施未知 3 条、协议截断 2 条。这些已消费数据上的临时计数不能
估计总体分布，但足以证明终止报错不是因果标签。在同一个 Conan case 上，原生 Codex 与 Repo2Run
都没有观测到一个条件源代码导入；causal-v3 则已经表示了这个精确导入，却把它映射为无效的未固定
版本安装。三者具有相同 Official 残余，但最早失败分别属于观测、观测和操作。

轨迹系统首先发现 replay 继承构建缓存，导致两份已认证程序在 Official 中失败。这是观测层错误，而非
缺少 package 规则。隔离目标状态后，replay/Official 恢复一致，并出现同 session 修复。

两个 outcome-independent 开发 batch 中，自由搜索为 `6/8`，目标状态重放为 `7/8`（exact McNemar
`p=1.0`）。失败富集 Bad-6 为 `2/6` 对 `4/6`，并产生 3 次 replay Fail-to-Pass 修复，但也反复出现一种
操作层失败：Agent 已达到公开目标，却没有交付候选。这些结果提出 handoff 假设，但没有证明普遍成功增益。

随后 6 对 prospective 实验用 prompt 引导提前程序化和 incumbent retention 解决候选不交付，结果从
`6/6` 退化到 `5/6`，共同成功样本上资源也更多。失败轨迹已经可信完整 Pass，却没有提出程序，因此
retention 无法激活。我们否决这套 bundled 方法，只保留一个缺失转换：状态充分后必须触发 replay。

在已消费 qibolab 上，verifier handoff 跑通完整机制链。Control 和 treatment 都通过 Official；treatment
在可信 Pass 后只触发一次 handoff，clean replay 因依赖冲突失败，同一 session 修复后下一次 replay 与
Official 均通过。它使用 66 对 84 次请求、2.59M 对 5.49M Token，但这些只是一对已消费样本的描述性值。
资格实验还发现触发前 prompt 不一致；Runner 0.6.1 已使两组在触发前拥有相同工具和 prompt，下一轮
prospective 比较因此从该公平接口开始。

固定实验覆盖 20-case 开发 screen 机械选出的全部 3 个失败。Official 上 control 为 `3/3`，handoff
为 `2/3`，唯一 discordant pair 支持 control。Marimo 两组都通过手工创建占位模块获得 Official Pass，
预注册 allowed-action 审计将两者都计为算法失败，因此协议合规成功为 `2/3` 对 `1/3`。两个评价轴都
没有 treatment-only Pass。PlatformIO 只提供一条成功条件下的效率信号：handoff 将 35 次请求和
1.03M Token 降到 16 次请求和 0.23M Token，不能据此挽救成功率假设。

Pilot 暴露出两个更早且重复出现的原因。即使解释器和已安装 distributions 相同，trusted goal 观测仍会
随 Agent 的持久 cwd 改变；clean replay 还暴露出最终程序没有保留必需 provider 操作后置条件的问题。
所以下一版最小方法只针对 project-root-invariant observation 和 evidence-to-program postconditions；
forced handoff 不再进入核心主张。

观测缺陷已面向未来修复：trusted goal 固定从项目根运行，同时保留当前激活解释器环境。另一个最小
完整性边界会报告“候选新增、位于 `site-packages`、公开名称且没有 installed-distribution owner”的
provider。它们是未来各组共享的协议修复，不能算作 EnvSolve-Pro 的算法增益。

## 7. 证伪条件与范围

Forced-handoff 的成功率主张已被 prospective 开发期 pilot 否决，不再继续。若独立同模型实验没有
Official 增益、重放失败不改变后续程序、匹配目标状态后 replay 仍与 Official 分离，或增益在强模型上
消失，剩余核心主张都会被削弱。若成功率提高但资源增长过大，我们只报告 tradeoff，不声称效率提升。

第一篇论文研究固定部署算法。harness 自优化属于 Auto-EnvSolve，策略学习属于 EnvSolve-RL；未来复用
本文轨迹，不会改变本论文的方法和结论边界。
