# P6 输出契约 Consumed Replay V2 结果

状态：以 `inconclusive_provider_exception_after_practical_trigger` 关闭。它仍是
consumed-development 机制证据，不是效果结果。

## 结果

唯一一条预注册 run 在 1,060.6 秒内形成 audit-valid trajectory。前 7 次模型响应全部解析为 candidate，
没有 length finish、empty final、policy-output failure 或 request error。4 个 candidate 进入 fresh
environment 并到达固定 internal verifier，但没有通过，也没有进入 Official evaluator。

第 8 次请求在 `model.invoke` 内发生 provider/API JSON decoding exception。因此 ledger 记录 8 次
request、7 次 completed response、1 次 request error、26,659 input tokens 和 34,618 output tokens。
轨迹没有持久化 reasoning content。

预注册的实际规则同时要求至少 5 个 parsed completed response，并且整条 run 没有 request error。
第一项已经超过门槛，但第二项失败。这不是 v14 反例：没有 empty final、length-accounting violation、
reasoning-content persistence 或 budget terminal 分类错误。它也不满足预注册的 unexercised 条款，因为
provider exception 发生在 7 个 parsed response 之后，而不是 5 个之前。严格结论因此是
`inconclusive_provider_exception_after_practical_trigger`。

冻结的通用分析器输出了 `unexercised_provider_exception`，原因是它没有让该标签依赖 trigger timing。
Raw analysis 保持原样；机器可读 closure 显式记录这个差异，并按预注册规则裁决。本轮不重跑、不替换。

## 下一边界

Output allocation 已得到连续 7 个响应的描述性支持，但 formal qualification 仍被阻止。下一项最小
revision 要把 transient provider-response acquisition failure 与 policy output 分开，在完整 attempt
记账下进行 bounded request-level recovery，并显式处理 future analysis timing。选择任何新的 unseen
development batch 前，必须在不引入新 repository identity 的条件下完成资格验证。
