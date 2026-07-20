# P6 约束-操作资格实验 V11 结果

状态：因操作者中断，以 terminal reach 不足正式关闭；不得重跑或替换 case。

## 结果

Q11 保留了全部 10 个冻结 position。9 条 run 的 artifact 有效，8 条 scientifically eligible。
Position 8 在产生任何模型 usage、candidate、environment、command 或 evaluator 信息前，因 provider
acquisition 失败而终止。Position 10 在第一个 candidate 启动后被操作者停止，因此科学上不可用。
没有任何 run 得到 Boolean Official 结果。5 个 pair 全部被删失，未达到预注册的至少 2 个 eligible
Official pair，Q11 因而不能估计两种方法的效果差异。

Position 8 在形式上满足窄范围的同 identity 零信息重试条件，但对应 control 已经没有 Official
结果；重试无法恢复 eligible pair，也不会改变 Q11 结论。Position 10 没有预注册的中断重试权限。
两条原始 position 均保持不可变，5 个 identity 全部 consumed，仍有 141 个 development identity
保持 untouched。

## 失败分解

Episode 后分析只纳入 8 条 scientifically eligible 轨迹，并完整划分 43 个 candidate transition：
38 个 candidate 进入 fresh execution，5 个被共享 validator 拒绝，7 次执行结束时仍有 structured
obligation。38 次真实执行中有 31 次（81.6%）直接失败在 candidate command。

| 方法 | Runs | Candidates | Executed | Command failure | Validation reject | Structured obligations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 约束驱动 EnvSolve | 4 | 19 | 18 | 15 | 1 | 3 |
| Free-form ablation | 4 | 24 | 20 | 16 | 4 | 4 |

这些分方法统计只能作描述，既不是 paired Official outcome，也不是效果比较。已消费的 Q10 轨迹中，
41 次执行有 23 次 command failure；Q11 的 31/38 只能加强一个诊断：操作可行性是当前 development
阶段的主要瓶颈。两批实验不能作因果比较。

## 架构诊断

观测层已经记录完整 candidate 结果和准确的失败命令，但约束 normalizer 只接纳其中很小一部分，
例如 runtime mismatch、缺失 executable 和缺失 module。确定性的 package provider 拒绝、无效路径
和 build failure 仍然只是原始文本。操作 guard 会记住失败命令前缀，却不会在整个 episode 中保留
关于失败操作目标的 typed negative fact。

因此，当前三层架构存在一个明确缺口：**已经观测到的失败操作，往往没有转化为状态化的负操作
知识**。下一轮 proposal 只要改变周围命令，仍可能在新环境中重复同一个失败目标，而原始 module
或 capability requirement 依然没有解决。

## 下一条假设

下一 revision 只检验一个仓库无关的主张：把确定性失败的操作目标持久化为带上下文的 typed negative
feasibility fact，可以减少相同失败操作的重复。它不能推断底层 module 不可能满足，不能阻止不同
provider 或 operation kind，也不能把网络和基础设施故障硬化为约束。

该假设必须先通过 repository-free 的正反合成反例，之后才能冻结新的 algorithm/harness，并在新的
outcome-blind development batch 上资格验证。Q11 只负责生成问题，不能验证由它启发的 revision。
