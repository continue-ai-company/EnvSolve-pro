# P6 输出契约 Consumed Replay V1

状态：执行前已预注册。这是单条 run 的机制 replay，不是效果实验。

## 为什么选择这条 Run

Q10 预算校准中只有一条 run 因连续 3 次模型 final content 为空而终止。这里复用这条已经 consumed 的
identity 和 method，不选择新 case，也不检查 Official 或 Canary 结果。

## 冻结干预

Algorithm v13 与 Harness v27 保持 v12 的 solver、constraint state、operation plan、guard、verifier、
prompt 和原始执行上限不变。唯一显式 inference 边界设置是 `reasoning_effort=high` 与
`response_format=json_object`。正常 online budget exhaustion 通过 solver-owned terminal type 传播，
不再进入通用 policy-exception channel。Reasoning 内容绝不持久化。

## 决策规则

实际输出资格要求至少 5 次 completed response 都形成 parsed candidate，并且没有 policy-output failure、
empty-final diagnostic 或 request error。如果 environment/command budget 结束 run，必须按正确 scope 记录为
`episode-budget-exhausted`，绝不能记录为 `candidate-policy-exception`。

若更早出现 internal Pass、infrastructure failure 或 provider failure，则未观测到的边界记为
unexercised，不允许 replacement。任何 empty-final failure、持久化 reasoning content 或
budget-as-policy-exception 转移都会反驳 v13，并阻止新的 unseen qualification。这条 consumed run 的
成功或失败都不能支持榜单或论文效果 claim。
