# P6 负操作可行性 V1

状态：repository-free 合成机制资格验证已完成；development 效果资格验证待进行。

## 假设

当 provider 确定性拒绝某个操作目标时，把该失败持久化为 typed negative feasibility state，可以阻止
系统在 provider 上下文未变化时重复同一操作。该状态不能停用仓库原始 requirement，不能阻止其他
operation，也不能把被基础设施删失的反馈硬化为约束。

该假设由已消费的 Q11 轨迹生成；这些轨迹不能验证由它启发的 revision。

## 三层语义

**观测层。** 只有三项证据同时成立，verifier 才产生 `operation-observation`：插桩后的 candidate
定位了准确失败命令；共享 validator 将它识别为 Python 或 system package-install action；命令输出
含有精确的 provider-target-unavailable 签名。网络、timeout、artifact integrity、build、path 和未
类型化失败都不会产生负操作观测。

**约束层。** 该观测转化为 domain 为 `operation`、predicate 为 `feasible`、value 为 `false` 的
scoped fact。它保留 candidate 与 environment provenance，并在不同 candidate context 间累积。它
不是对 module、package 或 capability 的负事实，因此不能满足或停用原始仓库义务。

**操作层。** 完整方法在有界 operation view 中展示全部 active 负操作事实。分配 fresh environment
前，guard 只在相关 provider context 与失败 candidate 相同时拒绝同一命令。Python context 包括
runtime 选择、virtual-environment 绑定、安全 environment export 和之前的 Python package operation；
system context 包括 package-index update 与安全 environment export。上下文变化或不同命令仍然允许。

## 接纳矩阵

| 证据 | 负操作事实 | Guard 结果 |
| --- | --- | --- |
| Typed pip install + 精确 no-distribution 签名 | 是 | 相同命令与 Python context 被拒绝 |
| Typed system install + 精确 unavailable-package 签名 | 是 | 相同命令与 system context 被拒绝 |
| 网络/provider transport 签名 | 否，结果为 Unknown | 不做 hard rejection |
| 相同文本出现在 runtime action | 否 | 不做 hard rejection |
| Build failure、missing path 或普通非零退出 | 否 | 不做 hard rejection |
| Runtime context 改变后重试相同命令 | 保留旧事实 | 新 context 中允许重试 |
| 不同 provider 命令或 operation kind | 保留旧事实 | 允许替代操作 |

## 合成资格验证

Repository-free 测试覆盖完整状态转移：typed verifier admission、constraint normalization 与
provenance、跨 context 累积、只对 constraint-driven treatment 可见的有界模型投影、context-sensitive
guard，以及在 environment 分配前拒绝的端到端 loop。负例覆盖网络 Unknown、错误文本附着在错误
action kind、runtime 变化和替代操作。失败上下文从 verifier 记录的实际失败前缀重建，因此同一命令
在不同位置重复出现时不会被混淆；新候选中的每一次出现都会与这个有证据支撑的 typed context
比较。聚焦测试为 `107 passed` 加 44 个 subtest，真实 fresh-container Docker boundary 通过。
Freeze 前排除 manifest 自身的回归为 `408 passed, 1 skipped`；最终全量回归为
`410 passed, 1 skipped`。

## 声明边界

本结果只资格验证机制语义，不证明部署效果。规则中没有 package、module、repository、benchmark
split 或 evaluator outcome。Q11 保持关闭且不重跑。Algorithm v16 与 Harness v31 冻结后，下一项
效果实验必须从 141 个 untouched identity 中重新预注册、仅按 metadata 盲选新的 development batch。
