# P6 模型输出契约 V2

状态：合成边界已通过资格验证。这是 provider/client 兼容性证据，不是 repository deployment 证据。

## 触发原因

预注册的 consumed replay v1 先产生 3 个有效 JSON candidate，第 4 次响应则在 structured parsing
前达到 16,384-token completion limit。该 run 通过 audit，并以
`unexercised_model_length_exception` 关闭。

本轮修正两个通用 runtime 缺陷。带 provider usage 的 length-finished response 现在计为已完成且消耗
token 的响应，不再计为 request error；同一情况在 solver 中成为可恢复的 `candidate-policy-output`
failure，不再是意外 policy exception。Prompt、constraint、operation、verifier、evaluator 和
case-specific behavior 均未改变。

## Allocation

2026-07-20 的 OpenRouter 公开模型目录显示，`deepseek/deepseek-v4-pro` 只支持 `high` 和 `xhigh`
reasoning effort，默认值为 `high`，最高允许 384,000 completion tokens。OpenRouter reasoning 文档还
说明 reasoning 会消耗 completion allowance，且 allowance 必须为 final answer 留出容量。因此 v2 保留
最低可用 reasoning effort `high`，只把单次 completion ceiling 从 16,384 调整为 32,768。聚合上限
保持为 15 次请求、1,000,000 total tokens、5 个 environment、5 条 command、2 小时和相同固定成本
上限。

来源：[OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)、
[OpenRouter API parameters](https://openrouter.ai/docs/api/reference/parameters)，以及
`experiments/validations/p6_deepseek_v4_pro_capability_snapshot_20260720.json` 中保存的公开模型记录。

## 合成压力探针

生产 `StructuredModelDeploymentPolicy` 接收不含 repository 的合成状态，每次请求约 2,100 input
tokens。5 次请求使用冻结模型、`temperature=0`、`seed=0`、`high` reasoning、JSON-object mode 和
32,768-token ceiling。

5 次响应全部以 `finish_reason=stop` 结束，5 次全部解析为严格 policy candidate，request error 和
policy error 均为 0。探针在 304.3 秒内使用 10,403 input tokens 和 13,788 output tokens；单次 output
范围是 119 至 5,453 tokens。Candidate content 与 reasoning content 均未持久化。

这只验证合成 output boundary。选择新的 unseen development identity 前，还必须预注册一次同 identity
consumed replay。该 replay 不能支持效果、榜单或论文 test-set claim。
