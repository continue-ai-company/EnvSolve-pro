# P5 因果前沿 V2 裁决

## 结论

V2 不能用于比较 flat 与 causal-frontier 的算法效果。冻结分析器在读取 LangGraph candidate 2 的模型可见
状态时因缺少 `causal_roots` 退出；独立事后审计确认，这不是 analyzer 偶然崩溃，而是模型输入合同真实
失效。

三个 causal episode 共持久化 16 次模型决策，其中 15 次通过 hash 与结构审计。唯一失效决策把 10,409
字符的完整 frontier 替换为整体截断包装，既没有 root list，也没有 summary。因此预注册规则下
`measurement_integrity_ok=false`、`effect_analysis_admissible=false`。

causal 表面 Official Pass 为 `1/3`，flat 为 `0/3`，但该数字只能解释为什么继续研究 causal state，不能
写成收益。离线重建也不能修复历史实验，因为模型当时没有看到重建后的状态。

## 最小后续

V3 只修复两个通用语义：root-first 的结构化有界投影，以及 `sys.version_info` tuple guard。先在相同三个
已消费 case 上运行完整性 canary；Official Pass 不参与 gate。测量有效后，才冻结 consumed-case 多 block
配对，并继续保持 fresh Dev untouched。

机器可读裁决见
`experiments/validations/pro_p5_causal_frontier_paired_v2_adjudication.json`。

