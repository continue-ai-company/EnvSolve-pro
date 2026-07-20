# P6 输出契约 Consumed Replay V2

状态：执行前已预注册。这是单条 run 的机制 replay，不是效果实验。

## Identity 与干预

V2 复用 replay v1 完全相同的 consumed Q10 identity、method 和 seed，不选择、检查或替换其他 case。
Algorithm v14 与 Harness v28 保持相同 prompt、constraint state、operation plan、guard、verifier、
聚合预算和 terminal-only Official access。相对 v1 唯一的 inference allocation 变化是已通过合成资格
验证的 32,768-token 单次 completion ceiling。

带 usage 的 length-finished response 必须计为 completed response，并成为 recoverable
`candidate-policy-output` failure。Reasoning content 永不持久化。

## 决策规则

实际资格要求至少 5 次 completed response 形成 parsed candidate，且整条 run 不出现 output failure、
empty-final diagnostic 或 request error。如果发生 length finish，其记账和分类必须正确，但实际输出
契约仍不算通过。任何自然 budget terminal 必须按准确 scope 记录为 `episode-budget-exhausted`。

若 5 个 parsed response 前出现 internal Pass、infrastructure Unknown 或 provider exception，则边界记为
unexercised，不得 replacement。任何 empty final、把带 usage 的 length response 记为 request error 或
unexpected policy exception、持久化 reasoning content，或 budget-as-policy-exception 转移，都会反驳
v14 并阻止 unseen qualification。

该 run 不能支持效果、榜单或论文 test-set claim。
