# P6 输出契约 Consumed Replay V1 结果

状态：以 unexercised 关闭。这是 consumed-development 机制证据，不是效果或榜单结果。

## 结果

唯一一条预注册 run 在 909.3 秒后结束，artifact audit 通过。它启动 4 次模型请求，完成 3 次响应，
解析出 3 个 candidate，在 fresh environment 中执行 1 个 candidate，并记录 1 次 internal verifier
失败；没有进入 Official evaluator。

前三次 completed response 都产生了严格 JSON candidate，没有出现 empty final。第 4 次响应在结构化
结果完成解析前达到 16,384-token completion limit。Provider exception 报告 2,878 个 prompt token、
16,384 个 completion token 和 16,386 个 reasoning token。当前 online ledger 把它记为 1 次 request
error，并遗漏了该响应的 token，因为 callback 把所有解析异常都当成传输失败。

轨迹没有持久化任何 reasoning content。本次没有发生 online budget terminal，因此 terminal 分类分支
没有被触发。预注册的实际输出资格要求至少 5 次 completed parsed response 且没有 request error，
所以本轮未触发资格条件。锁定结论是 `unexercised_model_length_exception`，既不是反驳，也不是通过。

## 边界缺陷

本次 replay 暴露两个通用输出边界问题：

1. Length-finished provider response 带有真实 usage，应计为已经完成并消耗 token 的响应，而不是
   request error。
2. Structured response 耗尽输出额度属于可恢复的 policy output failure，不应成为意外的
   `candidate-policy-exception`。

下一 revision 仅修正这两项记账与分类。之后必须在不依赖 repository identity 的条件下验证 reasoning
allocation，再做一次同 identity replay。不得增加 case-specific operation rule、读取 Official feedback、
更换 identity 或作效果 claim。

锁定的机器可读结果位于
`experiments/validations/p6_output_contract_replay_v1_results.json`。
