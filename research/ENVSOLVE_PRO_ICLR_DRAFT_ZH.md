# EnvSolve-pro：面向仓库部署的部分可观测状态化约束求解

## 摘要

从源码运行一个陌生仓库，需要恢复仓库没有完整声明的 runtime、依赖、构建与平台条件。Agent 只能通过
仓库内容和有噪声的执行结果部分观测这些隐藏条件。现有部署 Agent 通常把原始日志追加到上下文后继续
生成命令；这种方式依赖模型在增长的历史中隐式维护状态，也难以区分候选错误、假设错误和基础设施
删失。

我们提出 EnvSolve-pro，将部署建模为部分可观测的状态化约束求解。系统由三层组成：观测层保留带来源
的执行证据；约束层维护可修正的事实、假设、冲突与未解决义务；操作层让强语言模型生成完整部署程序，
并用可执行反馈更新状态。结构化状态作为模型的外部认知工具，而不是封闭的动作语言：原始证据始终
可见，只有任务安全边界和执行直接反驳的行为构成 hard guard。
由于内部检查本身也只是部分观测，EnvSolve 区分满足内部目标的 `certified` 候选与已经安全执行、但仍有
未解决约束的 `admissible` 候选。系统保留最佳 admissible 候选，而不把内部 verifier 当成 terminal oracle。

我们将在 EnvBench 上与 Repo2Run、原生强 Agent、同 backbone ReAct 和冻结的 EnvSolve v1 比较。主指标
是 Official Pass@1；token、调用、环境数与时间是效率指标。对已消费轨迹的诊断性资格验证发现，封闭
command parsing 会删失 baseline 的可执行行为，不等价 workspace 会隐藏真实部署冲突。改用开放程序、
fresh execution、audited effect 和 benchmark 声明的前置条件后，表示层拒绝被消除，底层失败被暴露。
后续诊断 batch 又发现内部反馈过度硬化是一个跨三个仓库的失败模式。这些研究用于提出方法，不估计
效果；真正效果仍需在 untouched case 上检验。

## 1. 问题

给定仓库 `R`，存在一个不可直接观测的有效环境集合 `Z_R`。在第 `t` 轮，Agent 选择部署程序 `P_t`，
在 fresh environment 中执行后得到部分观测 `O_t`。相同症状可能由不同隐藏条件导致，网络或 provider
故障也可能使观测不可归因。因此，部署的困难不只是生成 shell 命令，而是维护关于隐藏环境的、可被
执行证据修正的状态。

EnvSolve-pro 维护状态 `S_t=(X_t,F_t,H_t,C_t,U_t)`：原始证据、事实、假设、冲突和操作义务。状态更新
只使用仓库与内部执行反馈；Official evaluator 仅评测最终候选，不进入在线 loop。研究目标是最大化
最终部署成功率。资源限制属于实验协议，而不是问题定义。

## 2. 方法

**观测层**回答“发生了什么”。它记录仓库声明、环境 identity、完整候选、命令结果、verifier 输出和
基础设施信号，并保留 Pass、Fail 与 Unknown 的区别。

**约束层**回答“现在知道什么”。确定性证据可形成 hard fact；歧义解释保留为带置信度和 provenance
的 hypothesis；Unknown 不被硬化。模型可以查看结构化状态及相关原始证据，并质疑 soft belief。
内部验证用于缩小不确定性，但不定义终局正确性。

**操作层**回答“怎样改变环境”。强模型自由生成自包含部署程序。系统只强制环境修改边界、安全边界和
有直接执行反例的精确禁忌，其余 operation plan 是建议。candidate 是开放程序，不属于封闭 command
vocabulary。系统通过 fresh isolated execution 与 audited effect 判断有效性，再把反馈送回观测层形成闭环。
Benchmark adapter 声明 internal 与 terminal execution 之前都必须存在的非结果状态，避免 solver 在更容易的
隐藏前提下被验证。

跨轮次，EnvSolve 维护一个很小的候选前沿。`certified` 候选满足内部目标并提前停止；`admissible` 候选
已经完成安全、完整性有效的执行，且没有未知验证状态，但仍有残余约束。若搜索结束仍未完全认证，最佳
admissible 候选仍可进入终局评测，并被明确标记为 `uncertified`。由此保持 solver belief 与 benchmark
outcome 的区别。

## 3. 三项贡献

1. 将真实仓库部署形式化为部分可观测的状态化约束求解，明确区分隐藏环境、在线执行反馈与终局评测。
2. 提出兼容强模型的三层算法，把 provenance-aware 状态作为可修正的推理支架，同时保留模型发现
   schema 外解决方案的能力。
3. 建立真实外部 baseline 驱动的受控评测，联合检验最终成功率、强模型下的机制增益、失败恢复与
   success-resource trade-off。

## 4. 研究问题

- **RQ1 效果：** EnvSolve-pro 是否比 Repo2Run、原生强 Agent 和 raw ReAct 获得更高的 Official Pass@1？
- **RQ2 机制：** Observation、advisory Constraint state 和 grounded hard guard 各自贡献什么；结构化
  机制在更强模型上是互补、冗余还是有害？
- **RQ3 鲁棒性：** 方法是否提高首次失败后的修复与 clean replay，并跨 case、模型和执行平台保持？

## 5. 实验

开发阶段先在新的 Dev case 上逐条观察真实 baseline，再提出算法修改。核心消融从 raw ReAct 逐步加入
Observation、advisory Constraint 和 grounded guard，并把冻结 EnvSolve v1 作为独立 baseline。Mac 与
DGX Spark 可并行运行，但每个 paired comparison 记录并控制执行平台、镜像和网络删失。

主指标为 Official Pass@1。次指标包括 terminal reach、首次失败后的修复成功率、clean replay、重复失败
率与 Unknown 比例。Token、请求、候选环境、命令和 wall-clock 只用于效率与 Pareto 分析。所有方法共享
terminal-only Official evaluator 边界；Canary 和 Official Test 在方法冻结前保持 untouched。

已完成的 P0-P2 audit 仅用于诊断。Synthetic test 建立了 effect boundary；6 条已消费外部轨迹全部可表示，
5 次最终重放均在没有 representation rejection 的情况下到达 terminal evaluation，但没有 Official Pass。
状态对齐还通过暴露 evaluator 的 `build_output/` 冲突，推翻了旧 EnvSolve 的一次内部接受。这些结果完成了
测量接口资格验证。P2 又发现三个仓库中的完整安全候选仅因残余内部约束而被删失。在 3 对已消费 case 的
资格实验中，候选保留把 terminal evaluation 覆盖从 `1/3` 提高到 `2/3`，但两组 Official Pass 都是
`1/3`。因此它只被验证为 terminal censoring 修复，尚未证明成功率提升。下一次算法干预前，先用 8 个
outcome-blind Dev case 判断剩余主导阻塞来自操作可行性、观测、约束闭包，还是内部 verifier 与官方条件的
覆盖差异。
