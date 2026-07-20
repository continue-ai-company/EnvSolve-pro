# P6 Negative Operation Feasibility V2

## Freeze 后反例

V1 的 Guard 已按 context 判断，但 treatment 的持久模型视图只暴露失败命令与 failure class。当来源
candidate 离开有界 recent-history window 后，模型可能把局部 operation failure 误读成全局禁令，
尽管 Guard v4 会正确允许 runtime 或 provider context 变化后的重试。

第二个 repository-free 反例把常见 dependency-network error 与 pip 末尾误导性的
`No matching distribution` 放在一起。Proxy、TLS、connect-timeout、name-resolution、retry
exhaustion、remote disconnect、connection reset 和 apt temporary resolution 并未全部在
operation admission 前分类，因此不完整 acquisition 可能被错误转成 target-unavailability state。

加入这些反例时，Q12 尚未选择任何 case。

## 最小修复

V2 只新增一个共享 provenance 函数。只有 verification 为负、candidate identity 一致、
`action_index` 指向 prefix 最后一项，并且失败命令、prefix 项与 typed operation command 全部一致时，
失败 prefix 才成立。Treatment model view 与 Guard 使用同一个 grounded prefix；malformed 或没有
位置证据的事实对两者都不可见。

Treatment 视图现在携带失败 operation 之前的命令，并明确 infeasibility 只约束 recorded provider
context 中的准确命令。Operation prompt 保留两条 escape route：改变 runtime/provider prefix，或使用
不同命令。Free-form ablation 仍看不到 operation plan 与 negative-operation view。

Verifier 在匹配 provider-target-unavailable grammar 前，先把上述 acquisition signature 分类为
infrastructure Unknown。Check profile v7 记录该语义变化。Operation fact identity、累积、准确命令
Guard、candidate language、primitive budget 与 Official access 均不变。

## 合成资格验证

Repository-free 测试覆盖持久 context 可见性、缺失 action index 时不硬化、重复命令位置消歧、
8 类带误导 target-unavailability 尾部的网络签名、context 变化后重试、替代 operation，以及
environment allocation 前拒绝。聚焦测试为 `110 passed` 加 52 个 subtest；排除 manifest 的回归为
`411 passed, 1 skipped` 加 69 个 subtest；显式启用的真实 Docker boundary 通过。

这些结果只验证语义。V1 与第一版 Q12 preregistration 保留为历史记录；Spark admission 或选 case
前必须生成新的 algorithm freeze、harness freeze 与 superseding preregistration。
