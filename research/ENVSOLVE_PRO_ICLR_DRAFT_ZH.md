# EnvSolve-pro：面向仓库部署的部分可观测状态化约束求解

## 摘要

从源码运行一个陌生仓库，需要恢复仓库没有完整声明的 runtime、依赖、构建与平台条件。Agent 只能通过
仓库内容和有噪声的执行结果部分观测这些隐藏条件。现有部署 Agent 通常把原始日志追加到上下文后继续
生成命令；这种方式依赖模型在增长的历史中隐式维护状态，也难以区分候选错误、假设错误和基础设施
删失。

我们提出 EnvSolve-pro，将部署建模为部分可观测的状态化约束求解。系统由三层组成：观测层保留带来源
的执行证据；约束层将表面症状组织为可修正的因果约束前沿；操作层让强语言模型生成完整部署程序，并
用可执行反馈更新状态。前沿按观测通道维护当前 scope，连接表面失败与有执行依据的根条件，同时保留
未知与原始证据。它是模型的外部认知工具，而不是封闭动作语言：模型仍可提出 schema 外方案，只有
任务安全边界和被执行直接反驳的行为构成 hard guard。
由于内部检查本身也只是部分观测，EnvSolve 区分满足内部目标的 `certified` 候选与已经安全执行、但仍有
未解决约束的 `admissible` 候选。系统保留最佳 admissible 候选，而不把内部 verifier 当成 terminal oracle。

我们将在 EnvBench 上与 Repo2Run、原生强 Agent、同 backbone ReAct 和冻结的 EnvSolve v1 比较。主指标
是 Official Pass@1；token、调用、环境数与时间是效率指标。两组独立开发轨迹普查把 `11/16` 个失败
定位在约束闭包与可执行操作的接口。已消费轨迹上的离线机制分析进一步将 `93/94` 个表面模块义务归入
`37` 个可执行根因，最大症状放大为 `25:1`。这些结果只用于提出和资格验证方法；成功率结论将在方法
冻结后由新的 untouched case 给出。

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

**约束层**回答“现在缺什么、冲突在哪里”。它构造一个可修正的因果前沿：根据 fresh execution 的
`missing_name`、显式 runtime compatibility 和环境 identity，把多个表面失败连接到同一根条件；每条边
保留 scope、source role、path 与 trust。不同观测通道独立推进状态，因此“本轮未观测”不等于“已经
解决”；新的同类观测可以确认或移除旧根因。确定性证据可形成 hard fact，歧义解释保留为 hypothesis，
Unknown 不被硬化。模型同时看到有界原始证据，并可质疑任何 soft belief。

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
2. 提出兼容强模型的三层算法，用按观测通道更新的因果约束前沿压缩重复症状，同时保留 provenance、
   Unknown 和 schema 外操作能力。
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

诊断实验只验证测量与机制假设，不承担效果结论。开放程序、状态等价前置条件和候选保留先移除了
representation 与 terminal censoring。P5 随后在三个已消费机制 case 上配对比较 flat state 与 causal
frontier，测量根因出现、复发和闭合；只有预注册门槛通过后才消耗新的 outcome-blind Dev batch。最终
确认实验冻结代码、prompt、分析规则和 evaluator 边界，并按 repository identity 隔离开发与测试。
