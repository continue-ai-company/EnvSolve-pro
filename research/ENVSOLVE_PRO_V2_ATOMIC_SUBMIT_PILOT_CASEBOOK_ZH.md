# EnvSolve-Pro V2 原子提交 Pilot Casebook

## 问题

如果不控制 Agent 的自由搜索，只把最终交付替换成一个原子动作：校验完整 bootstrap、
在新环境中重放，并把失败返回同一个 Agent session，能否提高部署成功率？

前瞻 pilot 使用 Dev pool 中仅有的两个从未执行过的 case。选择发生在结果之前，但不能
保证 matched `F+O` 对照一定有提升空间。两组统一使用
`deepseek/deepseek-v4-flash-0731`、DeepInfra、相同 case seed、相同初始 prompt 和相同
可见 action 签名；唯一差别是 `submit_bootstrap` 的执行语义。

## 结果

两个 treatment 程序都通过 clean replay 和 EnvBench Official；verticapy 对照也直接通过
Official。fontbakery 对照首次 Official 评测因 evaluator 读取超时被删失，完全相同的脚本在
Official-only retry 中通过；但该 retry 的 method 标签与源 run 不完全相同，因此只作为补充
证据，不进入严格自动 adjudication。

保守主表因此只有一对有效 pair 和一对删失 pair，没有 treatment-only success。从程序语义看
仍是 ceiling tie：四份生成程序最终都在不重新执行模型的条件下通过 Official。

| Case | 普通 `F+O` | 原子提交 | 原子重放路径 |
| --- | --- | --- | --- |
| fontbakery | 删失；同脚本 retry Pass | Pass | Pass |
| verticapy | Pass | Pass | Fail、Fail、Pass |

原子重放总体更贵：模型请求 126 对 88，Token 270 万对 199 万，生成时间 7,419 秒对
3,762 秒。主要开销来自 verticapy：57 对 28 次请求、132 万对 31 万 Token、5,753 对
911 秒生成时间。

## 机制证据

fontbakery 第一次 fresh replay 即通过。verticapy 给出了更有价值的链路：

1. replay 1 因下载包 hash mismatch 失败；
2. 同一 session 修改下载策略；
3. replay 2 暴露另一个包的 hash mismatch；
4. 同一 session 增加 retry 行为，replay 3 和 Official 均通过。

这证明原子交付能够暴露隐藏的目标状态失败，并保持修复推理连续性；但它没有证明成功率提升，
因为独立生成的普通对照程序也通过 Official。两个 treatment 的最终 clean replay 与 Official
完全一致。

## 决策

本轮不晋级 universal atomic replay，也不添加 package 或网络专用规则。实现保留为机制
treatment。下一组必须从已有 `F+O` Official failure 中机械选择并固定，检验在对照已知有
headroom 时 replay feedback 是否提高 Pass@1；同时把 replay 次数、生成时间、Token 和网络
流量作为独立成本报告。

机器可读审计汇总：
`experiments/validations/envsolve_pro_v2_atomic_submit_replay_v1_prospective2_summary.json`。
Spark 产物：
`/home/avdpro/EnvSolve-Pro-f52da5a/runs/envsolve-pro-v2-atomic-prospective2-v1`。
