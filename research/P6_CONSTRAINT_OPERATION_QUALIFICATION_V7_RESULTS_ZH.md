# P6 约束操作资格实验 V7 结果

状态：按照预注册的共享机制缺陷规则，在 pair 3 后关闭。

## 有效性

Q7 outcome-blind 选择了 5 个 development identity，实际执行前 3 个 pair 的 6 个 run；6 个 run
全部 artifact-valid 且 scientifically eligible。没有 host suspension、原始预算违规、schedule 错配、
自动重试或在线 official evaluator 访问。共享机制缺陷确认后，pair 4 和 pair 5 不再执行，但 5 个已选
identity 全部永久标记为 development-consumed。

三个已执行 pair 都没有得到双方 Boolean official outcome，因此全部从 paired effectiveness 表中删失；
Q7 不产生 Pass@1 估计。

## 观察结果

| Pair | Pre-action 触发 | 初始约束 | Full 终止 | Ablation 终止 | Full 时间 | Ablation 时间 |
|---|---:|---:|---|---|---:|---:|
| `everyelection` | 否 | 0 | candidate limit | candidate limit | 416 秒 | 1,737 秒 |
| `rl4co` | 是 | 13 | candidate limit | candidate limit | 2,929 秒 | 3,139 秒 |
| `baybe` | 是 | 20 | candidate limit | candidate limit | 1,683 秒 | 2,469 秒 |

Treatment 机制确实在线触发，而不只是代码存在。两个 trigger pair 中，声明 evidence 在 proposal 1
前进入 typed state，初始 operation plan 分别包含 13 和 20 个 package requirement，guard 检查候选
是否覆盖这些 requirement。Ablation 运行同一 observer，但不接纳这些 evidence。

不过该机制没有产生成功部署。两个 trigger pair 的全部 candidate 都在形成完整 fresh metadata report
之前失败，因此 33 个初始 package requirement 没有任何一个被正观测关闭。在三个已执行 pair 的汇总中，
full 与 ablation 使用相同总 candidate、command 和 environment 数；full 的 aggregate token 与 wall-clock
更少。这些是在 official success 为零时的描述性资源观察，不能作为效果证据。

## 共享机制缺陷

Pair 3 暴露了决定性问题。Repository metadata 和 candidate feedback 已确定基础 Python 3.13 违反
`requires-python <3.13`。Full EnvSolve 找到了兼容的 pyenv runtime，并进一步暴露 protobuf 与
OpenTelemetry 的版本冲突；但 runtime incompatibility 始终没有成为 operation plan 中的 typed hard
constraint。最后一个 candidate 删除 pyenv，退回到已经确认无效的基础解释器。

同一个状态维度缺失也让 ablation 重复不可用的 apt runtime mutation。这是通用的状态表示与动作可行性
问题，不是 BayBE-specific rule：package presence constraint 既不能保持 runtime compatibility，也不能
证明 runtime acquisition action 是否可用。

按照预注册 adaptation policy，Q7 在该 pair 后关闭。Q7 期间不修改代码或 protocol，不重跑任何 case，
两个未执行的 selected pair 也不会返回 untouched pool。

## 下一版本

下一机制版本应保持最小：

1. 在 admission 前观测 fresh base-runtime identity。
2. 只有在可与该观测比较时才接纳 `requires-python`。
3. 把确定性 runtime mismatch feedback 转成 typed hard constraint。
4. 要求 cumulative candidate 持续保持兼容 runtime，并拒绝已经证明不可行的重复 acquisition action。

这些修改必须先用合成反例定义，再冻结并使用新选择的 untouched Q8 case 验证。Q7 只支持这项错误诊断，
不支持论文的 effectiveness claim。
