# P6 Operation Replication V1

## 问题

第一轮冻结 pilot 在操作层面完全有效，但 EnvSolve 与同 backbone free-form ablation 的 terminal outcome
完全相同。本 replication 在代码、预算、模型、evaluator 和 treatment boundary 均不变化时，用 10 个
新的 development identity 检查零差异是否持续。

## 防过拟合边界

从 pilot 后仍 untouched 的 133 个 identity 中按 salted metadata-only hash 选样。不检查 repository，
不按失败类型预筛，不按 package manager 分层，也不复用 case。所有 selected identity 都变为 consumed。
Pilot trajectory 可以定义聚合测量，但不能产生 repository-specific rule，也不能修改 Algorithm v17 与
Harness v32。

## 对比与裁决

Paired contrast 与 primitive limits 和 pilot 完全相同。算法决策前必须跑完全部 10 个 pair。只有至少
出现一个 EnvSolve-only Boolean Official Pass 或 reach、没有 baseline-only Pass 或无法解释的 terminal
regression，并且 replication 至少有 6 个 eligible Boolean Official pair，才支持扩大不变系统的批量
实验。若仍没有正向 discordance，或者已有 grounded negative-operation fact 却仍然没有 guard rejection，
则先做聚合算法 review，不继续堆计算量。

这仍然只是 development evidence。Canary-20 与 Official-Test-100 保持 untouched，不允许榜单或论文
效果 claim。

机器可读协议为
`experiments/validations/p6_operation_replication_v1_preregistration.json`。
