# Counterexample Loop v2 修订

状态：在任何真实 case 执行前，对 Counterexample Loop v1 作出的合成审计修订。

v1 合成审计发现，仅“成功规范化”不足以作为进入下一轮 repair 的门。错误 adapter 可能
从一次 verifier failure 生成彼此一致的 requirement 和 observation；这些 constraint
格式合法但已被满足。此时允许下一候选，只会让循环具有状态，而不会让反馈具有纠错语义。

v2 只增加一条不变量：失败的 executable verification 只有在新接纳的类型化证据留下至少
一个显式 constraint conflict 时，才能允许下一候选。已经规范化但不构成矛盾的 failure
视为 adapter contract violation，并以 blocked 终止。

本次修订没有观察真实 repository、held-out case、模型响应或 benchmark outcome。v1 的
其他事件顺序、freshness、fail-closed、预算和准入规则保持不变。
