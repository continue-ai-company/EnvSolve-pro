# EnvSolve-Pro Stateful-Agent V2.2 Dev-5 结果

## 证据地位

这是已消费开发集上的机制实验，不是 held-out 证据。这五个仓库及其结果可以用于错误分析和设计
V2.3，但不能再次用于声称效果提升。

三种方法使用同一个强模型、公开可执行目标、只在终局调用的官方 evaluator、fresh candidate replay
和相同资源设置：

1. 单 session 的强 goal-aware Codex baseline；
2. 同模型、多 session 的 raw-feedback loop；
3. EnvSolve-Pro stateful-agent V2.2。

## 汇总结果

| 条件 | Official Pass | Wall time（秒） | 命令数 | Input token | Output token | Reasoning token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 强 goal-aware baseline | 5/5 | 3,990.6 | 132 | 4,363,200 | 62,772 | 32,161 |
| Raw-feedback loop | 5/5 | 6,387.0 | 142 | 9,999,463 | 96,930 | 56,666 |
| Structured V2.2 | 4/5 | 6,386.6 | 119 | 8,059,643 | 81,164 | 46,402 |

相对 raw feedback，V2.2 少用 16.2% 的命令和 19.4% 的 input token，但 wall time 没有下降，并且少
通过一个 case。相对强单 session baseline，它多用 60.0% 的时间和 84.7% 的 input token。这个诊断
样本上，强 baseline 明显最好。

EnvBench 的 `errorCount` 不是计分字段。Official Pass 只要求 bootstrap 成功且
`reportMissingImports` 为零；其他 Pyright 错误只作为诊断信息。

## 逐例证据

| 仓库 | 强 baseline | Raw | V2.2 | 决定性观测 |
| --- | ---: | ---: | ---: | --- |
| aqtinstall | Pass | Pass | Pass | loop 没有增加成功价值，结构化反馈也没有显著减少尝试或时间。 |
| moat-mqtt | Pass | Pass | Fail | 一刀切的源码 provenance veto 错误拒绝了多个 sibling distribution 合法组成的 namespace。 |
| smart_open | Pass | Pass | Pass | 强 baseline 保留了有意失败的 import fixture；两个 stateful 条件只找到较弱的名称可见性方案。 |
| molecularnodes | Pass | Pass | Pass | 官方静态指标可以接受运行时不兼容的二进制，暴露 benchmark 与真实执行语义的差距。 |
| plotnine | Pass | Pass | Pass | 572 个 surface finding 实际只有 15 个依赖根，但原始报告仍制造了 2,557 个状态事件和约 630 KB 模型输入。 |

## 错误分析

V2.2 有三个通用错误。

第一，在强模型查看仓库之前就运行完整公开目标，即使首轮本来能成功也要付出诊断成本，并让模型被
surface symptom 锚定。第二，只在 derived view 中分组，却仍把完整报告送入模型，并把每个 surface
finding 转成两条 solver event。第三，把推断得到的 provenance 规则提升成 hard veto。
`moat-mqtt` 的误拒绝说明：一个看似合理的语义启发式不能比官方目标拥有更高权威。

保留下来的有效部分更少也更清晰：fresh-container feedback loop 确实可执行；root grouping 可以聚焦
模型；开放操作程序允许强模型发现固定 action schema 之外的解法。

## V2.3 决策

V2.3 只做最小修正：

- **观测层：** 首轮只让模型检查仓库并提出候选；候选失败后才产生可执行目标反馈。
- **约束层：** 完整 finding 保存在不可变审计档案中，solver 和模型只接收根义务、计数和少量代表
  样本。只有官方目标和共享实验合法性规则是 hard constraint；provenance 与语义解释只能作为 advice。
- **操作层：** 最强 Agent 继续使用开放终端和不受限的累计部署程序。

候选目标与完整性 audit 现在通过同一个 shell 环境解析 `python`。已经认证的终态候选不再携带错误的
repair-candidate assessment。V2.2 保持冻结，作为结构化 baseline。

V2.3 必须在 repository-disjoint 的新 case 上验证。本轮 Dev-5 只能用于回归测试与解释设计，不能估计
新方法成功率。
