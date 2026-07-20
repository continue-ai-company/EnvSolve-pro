# P6 Operation Pilot V1

## 目的

在投入更大的 Spark 预算前，本 pilot 检查冻结 EnvSolve v17 能否在 8 个 fresh development case 中
至少两次自然到达 Official evaluator，以及它相对同 backbone free-form operation baseline 是否出现
无法解释的 paired regression。

只有 Mac host 与 provider gate 通过后，才能从 Q11 后仍 untouched 的 141 个 identity 中按 salted
metadata-only hash 选择 8 个。无论结果如何，这 8 个 identity 都永久记为 consumed。选样前不检查
repository，pilot 不能支持论文效果 claim。

## 对比

两种方法共享模型、seed、原始执行反馈、repository/runtime observation、fresh environment、verifier
v7、Typed Replay IR v8、primitive limits 和只能 episode 后访问的 Official evaluator。EnvSolve 使用
持久 typed constraint、grounded negative-operation view 与 Guard v4；baseline 只能看到 raw history，
没有 operation plan、negative-operation view 或 guard。

## 决策门槛

只有至少 2 条 scientifically eligible EnvSolve run 得到 Boolean Official outcome、共享 invariant 全部
有效，并且不存在 baseline 到达或通过 Official 而同 case EnvSolve 未到达的未解释 regression，才允许
进入 bulk execution。若 EnvSolve 的 terminal reach 少于 2 条，必须停止 bulk batch，先做失败分析。
EnvSolve-only success 只是积极 development evidence，不是结果 claim。

若 pilot 后修改算法，8 个 identity 全部保持 consumed；新算法必须重新 freeze，并从剩余 133 个
identity 中重新预注册 bulk batch。

机器可读协议为 `experiments/validations/p6_operation_pilot_v1_preregistration.json`。
