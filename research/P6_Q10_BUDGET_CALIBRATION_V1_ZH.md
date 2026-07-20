# P6 Q10 独立原始预算校准

状态：10 条预注册 run 全部执行后关闭。这是使用已消耗 development case 的诊断，不是效果实验。
结果见 `P6_Q10_BUDGET_CALIBRATION_V1_RESULTS_ZH.md`。

## 动机

Q10 为每条 run 设置 5 个模型 candidate、5 个 fresh environment 和 5 个 verifier command，但实现上
三者来自同一个数值。10 条 run 中有 9 个 proposal 在创建 environment 前被 validation 或 guard
拒绝，因此最多 50 个 fresh environment 实际只使用了 41 个。模型请求上限虽然是 15，但 episode
通常在约 5 次请求后就被 candidate limit 结束。

这给 terminal non-reach 提供了一个比“缺少新 solver 机制”更简单的解释：廉价的 validation/guard
reject 与昂贵的 fresh execution 消耗了同一个 cap。在增加算法结构前，必须先排除该 harness confound。

## 干预

复用已经消耗的 Q10 5 个 development identity，并保持 Q10 完全相同的 case 与 method 顺序；不重新
选样，也不 replacement。Solver、state、prompt、operation planner、guard、verifier、model、seed、
image 和 Official protocol 均不改变。

只改变原始预算向量：

| Primitive | Q10 | Calibration |
| --- | ---: | ---: |
| Candidate proposal | 5 | 15 |
| Fresh environment | 5 | 5 |
| Verifier command | 5 | 5 |
| Model request | 15 | 15 |

Token、wall-clock、单命令和 evaluator 上限保持不变。Candidate proposal 包括被 candidate validation
或 operation guard 拒绝的已解析脚本；只有通过两道 gate 后才计入 environment。

## 结果定义

主要问题是：是否有 run 在第 5 个 proposal 之后恢复原本未使用的 fresh-environment slot，并进入
internal 或 Official evaluation。实验报告全部原始资源使用和 terminal stage。由于历史 Q10 run 具有
随机性，且 identity 已经被消耗，差异只能用于诊断，不能作为因果性能估计。

若后续 proposal 进入 terminal evaluation，则 coupled cap 是实质性 harness bottleneck，此时不应新增
solver 机制。若后续 proposal 使用了恢复的 environment 但仍失败，则预算耦合确实有害但不足以解释
全部问题；只有这时，才能依据新 trajectory 用通用合成反例定义一项最小 operation-state revision。
本实验的任何结果都不能支持榜单或 held-out claim。

## 关闭结论

3 条 run 越过旧 proposal 上限，并在第 5 个 proposal 之后恢复 5 次 fresh execution；但 0 条 run
通过 internal verifier，0 条进入 Official evaluator。预注册决策分支为
`additional_environments_without_terminal_reach`：保留独立原始预算，同时在新发现的输出与 terminal
state 边界缺陷修复前，暂缓扩展 operation state。
