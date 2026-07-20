# P6 Provider Acquisition Boundary V1

状态：合成资格验证通过，在线正常路径透传通过。这是 inference-boundary 证据，不是 deployment 证据。

## 触发原因

Consumed replay v2 连续产生 7 个 parsed model response，第 8 个 provider/API response 则在
`model.invoke` 内解码失败。冻结 run 不重跑、不 replacement，并以
`inconclusive_provider_exception_after_practical_trigger` 关闭。

该失败发生在 EnvSolve 获得 model message content 之前，因此属于 acquisition failure，不是 malformed
candidate output，也不是 repository constraint。把它归为 `candidate-policy-exception` 会过早终止，
同时错误标注责任层。

## 最小边界

EnvSolve 现在只重试 provider/client response boundary 抛出的 Python `JSONDecodeError`。它复用已有
`model_max_retries=2`，最多尝试 3 次；其他异常类型不会被这一层重试。

每个 attempt 都经过同一 online budget callback。失败 attempt 增加 `requests_started` 和
`request_errors`，计划的 parse retry 与成功 recovery 单独记录。恢复后的 response 进入完全不变的
structured policy。重试耗尽后产生 solver-owned `provider-acquisition-failure`，并记录准确 attempt
数量，绝不归为 candidate-policy failure。Model、prompt、constraint、operation、verifier、evaluator、
candidate、environment、token、cost 和 wall-clock limit 均不改变。

Output analyzer 现在区分 5-response trigger 前后的 provider failure，并单独暴露 recovered parse error。
冻结的 v2 raw decision 不会被覆盖。

## 资格验证

确定性的 repository-free fault probe 覆盖两条分支：

- 1 次 decode failure 后成功：使用 2 次 request、1 次 request error、1 次 parse retry、1 次 recovery，
  并产生 1 个 parsed candidate。
- 连续 3 次 decode failure：使用 3 次 request、3 次 request error、2 次 retry、0 recovery，并以
  `EpisodeProviderAcquisitionFailed(attempts=3)` 终止。

一次在线 repository-free 正常透传也返回 parsed JSON candidate，`finish_reason=stop`，retry/error 均为
0，使用 2,072 input tokens 和 2,065 output tokens。Candidate 与 reasoning content 均未持久化。
聚焦测试 65 项加端到端 probe test 全部通过；freeze 前全量回归为 `396 passed, 1 skipped`，唯一失败是
预期的旧 freeze 过期。

这些结果只验证 acquisition 记账、bounded recovery、terminal 分类和正常透传。生成新 freeze 后，
下一项允许面向效果的步骤是 outcome-blind unseen development qualification；不再重跑 consumed case。
