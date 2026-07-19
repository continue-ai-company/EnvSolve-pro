# P6 约束操作资格实验 V9

状态：在 Q9 选样、仓库检查或执行之前预注册。

## 目的

Q8 真实触发了 runtime-state v9，但因主要不变量失败而关闭：一条精确、确定性的 Python mismatch
仍停留在普通文本，没有约束下一次 proposal。Q9 是 v10 窄 runtime-diagnostic admission 修复的首个
outcome-blind development qualification。它不是效果实验，不能支持 held-out 或论文级性能 claim。

## 冻结对比

两种 condition 使用相同模型、seed、repository/base-runtime observer、fresh-container provider、
candidate language、Python deployment verifier v5、终局 official evaluator 与原始资源上限。

- `envsolve-operation` 接纳符合条件的 typed constraint，暴露 operation plan，并执行 operation guard。
- `envsolve-operation-ablation` 获得相同 raw observation 和 executed-candidate feedback，但不进行
  typed admission，也看不到 plan，不使用 guard。

Official evaluator 输出仍只在终局使用。两种 condition 都不能获得 Q8 trajectory、跨 case memory 或
repository-specific rule。

## 样本与调度

从剩余 156 个 untouched development case 中按 `SHA256(salt + NUL + case_id)` 升序选择 5 个
identity。选样只使用 identity metadata，不检查仓库，不按 package manager 分层，不预筛 runtime
trigger，也不补选。Pair 顺序与 pair 内方法顺序由独立 salted hash 固定。5 个 identity 一旦物化，
就永久标记为 development-consumed。

## 主要机制检验

只有至少一个 scientifically eligible 的 full run 同时满足以下条件，v10 才能通过资格验证：

1. 失败 candidate 后观测到精确的 subject-first diagnostic：`Current Python version (...) is not
   allowed by the project (...)`；
2. 后面至少还有一次 proposal 机会；
3. 下一次 proposal 前，该证据已经形成 hard runtime requirement/fact conflict；
4. conflict 被投影成 `runtime_configure` obligation，且下一条真实执行的 full candidate 覆盖它。

冻结的 PEP 440 语义门必须拒绝格式错误、信息不完整、带模糊措辞或 range-compatible 的近似文本，
不得创建 hard constraint。该边界在选样前由合成测试验证；真实 trajectory 出现此类文本时也必须
审计。Image identity、fresh-replay preservation、failed-prefix feasibility 和 covering-candidate
admission 保持为继承的安全不变量。

如果没有 eligible full run 触发新增 diagnostic family，Q9 只能报告未触发，v10 不算合格，也不得
补选 identity。任一已触发不变量违反都属于 shared mechanism defect，并在完成当前 pair 后关闭 Q9。
Official paired outcome 只是次要结果，只有 pair 双方都 eligible 且结果为 Boolean 时才报告。

## 资格与基础设施

每个 run 必须通过 artifact integrity、committed source、schedule identity、primitive budget、完整
heartbeat 与无 host suspension 检查。失败或删失 episode 不得覆盖。

只有 episode 开始前的仓库获取失败，且 model request、candidate、environment、evaluator execution
和 method information 全部为零时，才允许一次同 identity、受审计的重试。终局 evaluator 基础设施
失败可以对完全相同的冻结脚本执行一次 evaluator-only retry，且不得新增模型调用。其他基础设施失败
直接删失 pair，不得重试。

## Claim 边界

Q9 只能判断 runtime-diagnostic admission v10 是否适合继续 development。它不能证明部署效果、调整
冻结预算、查看 Canary/Official-Test，也不能加入 repository、package、tool、module 或 version rule。
Poetry declaration 与 command-language coverage 仍是独立错误假设。
