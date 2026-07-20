# P6 Q10 独立原始预算校准结果

状态：已关闭。本实验是 consumed development 诊断，不是效果或榜单结果。

## 结果

预定的 10 条 run 全部结束并通过 artifact audit。校准共产生 50 个 candidate proposal 和 41 次
fresh execution。3 条 run 越过历史的 5-proposal 上限：第 5 个 proposal 之后共产生 7 个 proposal，
其中 5 个实际进入 fresh execution。Full 在 2 条 run 中恢复 4 次执行，ablation 在 1 条 run 中恢复
1 次执行。0 条 run 通过 internal verifier，0 条进入 Official evaluator。

因此预注册决策为 `additional_environments_without_terminal_reach`：把廉价 proposal reject 与昂贵
environment cap 绑定在一起确实会机械性损失搜索机会，但解除绑定不足以产生可评测部署。

| 指标 | 合计 | Full | Ablation |
| --- | ---: | ---: | ---: |
| Audit-valid run | 10 | 5 | 5 |
| Candidate proposal | 50 | 29 | 21 |
| Fresh execution | 41 | 22 | 19 |
| Pre-environment reject | 9 | 7 | 2 |
| 旧上限之后的 proposal | 7 | 6 | 1 |
| 旧上限之后的 execution | 5 | 4 | 1 |
| Internal pass | 0 | 0 | 0 |
| Official evaluator reach | 0 | 0 | 0 |

历史 Q10 的聚合总量也恰好是 50 个 proposal 和 41 次 execution。这个相等不否定干预：新实现改变了
单条 trajectory 内执行机会的分配，但其他 run 的随机提前终止抵消了聚合层面的恢复量。历史差异只能
作描述性比较。

## 错误归因

新 trajectory 暴露出两个 solver 边界缺陷。一条 full run 连续收到 3 次 final content 为空的模型
响应并耗尽 policy-output failure allowance；该 run 总计使用 61,576 个 output token。另一条 run 因一次
provider-side JSON decode exception 结束。另外，7 次正常的 environment-budget 终止被记录成
`candidate-policy-exception`；这是 terminal state 分类错误，不是模型失败。

下一 revision 因而收窄为：

1. 在 policy-exception channel 之外，把 online-budget exhaustion 规范化成显式 budget terminal state。
2. 资格验证 provider-portable 的 structured-output contract 与 reasoning allocation，保证有界请求为
   final answer 留出容量。
3. 在使用合成反例和 consumed-development replay 修复这两个边界前，不增加 operation-state 机制。

锁定结果位于 `experiments/validations/p6_q10_budget_calibration_v1_results.json`。本轮没有使用
case-specific rule、Official feedback、Canary identity 或 Official-Test identity。
