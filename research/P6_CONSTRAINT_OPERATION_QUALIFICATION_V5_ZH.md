# P6 约束操作层资格实验 V5

状态：Q5 选样和执行之前的协议修订。

Q4 完成了全部五组 outcome-blind pair，十条轨迹全部 audit-valid。在四组非删失 pair 中，
full EnvSolve 得到一组 full-only official pass、一组 both-pass 和两组 both-fail，没有
ablation-only pass；另一组因 full condition 的网络超时而删失。四条 full episode 产生了
typed operation requirement。在两组非删失且触发的 pair 中，这些 requirement 改变了成功修复行为：
一组成为 full-only pass，另一组中 full 用 2 个 candidate 通过，ablation 用了 5 个。这些只是
development mechanism observation，不是总体效果 claim。

Q4 同时暴露了一个 method-neutral 的 candidate-language 缺口。候选可以创建 `.venv`，使用
`.venv/bin/python` 安装依赖，却在没有激活该环境时结束。追加的 verifier 随后使用 base interpreter，
反复报告一个已安装在未绑定环境中的工具缺失。由于该失败没有被接纳为可归因于候选的 module
conflict，operation layer 无法触发。

V5 向共享 candidate validator 增加一条通用环境绑定不变量：候选创建的每个 `.venv` 或 `venv`
都必须在创建之后、候选结束之前激活，且路径必须匹配。该不变量同时作用于 full 和 ablation，
并只用合成路径定义。它不新增仓库规则、package/provider mapping、evidence parser、constraint、verifier
signal、operation kind、evaluator access 或 treatment-only instruction。

Q5 从 `experiments/cases/train_untouched_after_operation_qualification_v4_176.jsonl` 中，使用 salt
`envsolve-p6-operation-qualification-v5-2026-07-17`，按 `SHA256(salt + NUL + case_id)` 升序 outcome-blind
选择五个新 case，并重复冻结的配对比较。任何 Q1-Q4 case 都不得复用。

对比方法在原始资源上共享固定上限：candidate、模型请求与 token、environment、command 和
wall-clock time。现有带日期的美元估计只作为非绑定的运营断路器和可审计派生字段，不属于任务定义、
方法匹配标准或科学结果。
