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

## 结果

16 个预定 run 全部完成，artifact integrity audit 全部通过，并且都 scientifically eligible。两种方法
都在 8 个 case 中的 4 个自然得到 Boolean Official 结果，并都通过其中 2 个：`pyvespa` 与
`windpowerlib`。两者都在 `molecule` 和 `scikit-rf` 上 Official Fail；其余 4 个都在 Official 前
耗尽 online environment 或 command budget。没有 discordant pair，也没有观察到通过率优势。

EnvSolve 使用 34 次模型请求、31 个 fresh environment、351,825 tokens 和 7,310.9 秒 episode wall
time；free-form baseline 使用 36 次请求、31 个 environment、341,122 tokens 和 9,253.8 秒。这些小幅
描述性差异不能被解释成效率结论。

## 三层分析

观测层在 3 条 EnvSolve run 中接纳了 4 个唯一、经过验证的 negative-operation fact。约束层在 31 个
受 guard 检查的后续 proposal 中，有 18 个显示非空 operation plan；但后续 candidate 没有在相同
context 下精确重复失败命令，因此 Guard v4 没有拒绝任何 proposal。所有 plan 共展示 316 个
requirement，单个 proposal 最多 25 个；若干 trajectory 提示 standard-library 与 repository-internal
module 可能被投影为 package-install obligation。操作层两种方法都执行 31 个 candidate；EnvSolve 有
11 次 command failure，baseline 有 12 次。

由于 EnvSolve 产生 4 个 Boolean Official outcome、共享 invariant 均成立且没有 paired regression，
预注册的操作门槛通过。但从科学结论看，这个 pilot 只证明可执行性，效果差异为零。下一个实验保持
Algorithm v17 与 Harness v32 不变，在新的 outcome-blind 样本上重复 paired comparison；在此之前既
不启动大规模 Spark batch，也不修改算法。
