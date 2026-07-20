# P6 模型输出契约 V1

Q10 预算校准暴露出一条 run 连续 3 次 final content 为空：响应消耗了 output token，却没有形成
candidate。这是 inference 边界失败，不是增加 repository constraint 的证据。

最小契约由 provider 配置，默认保持历史行为。当前 DeepSeek V4 Pro 资格配置把 reasoning effort 设为
`high`，并请求 `json_object` 输出。一次不含 repository 或 evaluator context 的在线合成探针返回了
严格包含 `script` 与 `rationale` 的对象，`finish_reason=stop`；150 个 output token 中有 124 个被报告为
reasoning token。

EnvSolve 现在只记录 final content 是否为空、finish reason、output token、reasoning token，以及是否
存在 reasoning content；不会持久化 reasoning 内容本身。Online budget exhaustion 单独表示为
`episode-budget-exhausted`，不再归类为 policy exception。

该探针只建立 API 兼容性。进入下一批 unseen development case 前，还必须通过合成测试、生成新的
algorithm/Harness freeze，并预注册一次不能支持效果 claim 的 consumed-development replay。
