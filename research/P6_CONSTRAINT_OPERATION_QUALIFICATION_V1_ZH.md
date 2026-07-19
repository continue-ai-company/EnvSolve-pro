# P6 约束操作层资格实验 V1

状态：设计预注册；先于从剩余 untouched development pool 选样，也先于任何新仓库检查或模型请求。

## 1. 研究问题

与使用相同 EnvSolve 状态和 verifier、但自由生成操作的对照相比，把已接纳 hard conflict 转化为
类型化 operation obligation，能否改善修复行为？

这是因果机制资格实验，不是论文级效果 claim。实验不新增 parser、package mapping、仓库规则或
verifier 条件。

## 2. 对比方法

两组使用完全相同的 repository profile、typed fact、constraint、hypothesis、有界执行反馈、
two-layer verifier、candidate language、模型、seed、预算和 fresh-container policy。

1. `envsolve-operation-ablation` 接收 typed constraint state，但看不到 `OperationPlan`，完整程序也不
   经过 operation guard。
2. `envsolve-operation` 额外接收确定性的 `OperationPlan`，并在创建容器前由
   `constraint-operation-guard-v1` 检查候选。

Operation layer 是唯一预期 treatment difference。两组都保留 candidate validator 和所有
evidence-admission rule。

## 3. Outcome-blind 选样

- 总体：`experiments/cases/train_untouched_after_v3_qualification196.jsonl`，SHA256 为
  `337f72f00b3731fe7388628a01e45f09ac07a4b3f579bc2fbdbdeddfede352ce`。
- Salt：`envsolve-p6-operation-qualification-v1-2026-07-17`。
- 按 `SHA256(salt + "\0" + case_id)` 升序取前五个 case。
- 选样只能读取 case metadata；此前禁止检查仓库源码、既有结果、轨迹、package metadata 或
  evaluator 结果。
- 无论是否遭遇基础设施故障，选中 case 都永久视为 development-consumed，并从剩余池移除。

## 4. 预算与执行

主设置为 `K=5` 次 candidate attempt。Guard 拒绝会消耗一次 candidate 及其模型开销，但不消耗
environment 或 command。根据已冻结的可恢复输出控制流，模型调用上限为 `3K=15`。既有 development
token、美元和 wall-time 上限作为不参与选择的安全边界，两组完全相同，并报告所有实际消耗。

每个 method-case pair 使用独立 ledger、trajectory、script 和 container。Case 与 method 顺序在
执行前用 salt 冻结。Official evaluation 只在 episode 完成后至多调用一次，结果绝不进入在线状态。

## 5. 报告指标

每个 pair 报告：

- internal 与 official terminal outcome；
- 是否产生 hard conflict 和 operation requirement；
- guard accept/reject 次数和被拒候选类别；
- obligation-response rate 与 repeated-conflict rate；
- candidate、environment、command、模型调用、token、成本与 wall time；
- clean replay 结果以及全部 infrastructure Unknown。

没有触发 operation requirement 的 pair 既不能证明 guard 有效，也不能证明无效，应报告为
non-triggering observation。

## 6. 结果解释

只有实现边界通过 audit，且触发 episode 表明 operation obligation 在不使用禁用信息的条件下改变了
候选行为，机制才获得资格。五个 case 不能建立总体效果结论。负结果必须保留。选样后的任何代码修改
都需要新版本和新的 outcome-blind batch；选中 case 的结果不能转化为 repair rule。

