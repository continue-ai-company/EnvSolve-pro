# P6 Constraint-Operation Qualification V12

## 研究问题

冻结的 EnvSolve v16 在新的 development repository 上，能否比 matched free-form
operation ablation 获得更高的自然 terminal reach？新增的 negative operation state 是否会被真实
触发，同时不错误剪枝替代方案？

V12 是 development qualification，不是 leaderboard evidence。它将从 Q11 后仍 untouched 的
141 个 identity 中产生 5 个新配对 case。选择过程必须 deterministic、metadata-only，并且只有
DGX Spark 通过预注册 host gate 后才能执行。

## 冻结对比

两种方法共享 repository 与 base-runtime observation、模型、primitive limits、原始执行反馈、
Typed Replay IR v8 action provenance 和 Python verifier v6。Treatment 能看到 constraint
operation plan 并使用 Guard v4；ablation 保持 free-form，不能消费 typed operation state，也没有
guard。

这是论文中的整体系统对比，不是 negative operation state 单组件的因果消融。V12 可以证明该机制
是否在完整系统中被使用；若要声称单组件因果效果，仍需后续专门的 component ablation。

## Spark 门禁

选 case 前，Spark 必须运行满足冻结哈希链的 clean revision，Harness v31 验证为 `valid=true`，
全量回归达到 `410 passed, 1 skipped`，真实 Docker integration 通过，EnvBench revision 与冻结值
一致，并完成不接触 case 的 provider probe。Host gate 失败不消耗 case；若任何 frozen file 改变，
必须先重新 freeze 并发布 superseding preregistration。

## 结果判定

主要系统结果只使用两侧都 scientifically eligible 且都有 Boolean Official outcome 的 pair。至少需要
2 个这样的 pair 才做 paired comparison；否则只报告 terminal-reach insufficiency 与 failure
decomposition。

Mechanism utilization 的触发条件是：treatment 先接纳 hard `operation/feasible=false`，之后又收到
相同命令且 relevant typed prefix context 相同的 proposal；Guard 必须在 environment allocation
之前拒绝。只有 admission 而没有 later proposal 不算 guard opportunity；零触发记为 unexercised，
不得替换 case 或搜索 repository。

## 完整性边界

Q1-Q11 identity 对 effectiveness 已全部消耗。Canary-20 与 Official-Test-100 继续不可查看。Official
evaluator feedback 只能在 episode 后使用，不启用 cross-case memory，选 case 后不得添加
repository-specific rule。中断和基础设施结果按冻结 censoring rule 处理，不覆盖已有 run。

机器可读预注册文件为
`experiments/validations/p6_operation_qualification_v12_preregistration.json`。
