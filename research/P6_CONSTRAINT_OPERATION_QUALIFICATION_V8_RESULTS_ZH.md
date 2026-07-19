# P6 约束操作资格实验 V8 结果

状态：按照预注册 runtime invariant 规则，在 pair 1 后关闭。

## 有效性

Q8 outcome-blind 选择了 5 个 development identity。Position 1 在 verification 前按 operator 要求
中断，以 scientifically ineligible/Unknown 保留且不得重跑。Position 2 是冻结的 full counterpart，
artifact-valid 且 scientifically eligible；其 heartbeat 完整，source 已提交且 clean，schedule identity
匹配，并且没有 primitive-budget 违规、host suspension、请求错误或在线 official evaluator 访问。

由于 ablation 不合格，pair 1 被删失。但 eligible full run 确实触发了主要 runtime 机制，并违反冻结
不变量，因此 Q8 在该 pair 后关闭。Positions 3--10 不再运行；5 个 selected identity 全部永久标记为
development-consumed。Q8 不产生 paired effectiveness estimate 或 official Pass@1 结果。

## 观察结果

| Pair | Ablation | Full | Runtime 触发 | 主要判定 | Official 结果 |
|---|---|---|---|---|---|
| `biopsykit` | interrupted / ineligible | candidate limit / eligible | 是 | invariant failure | censored / Unknown |

Full run 使用 5 次模型请求、37,815 tokens、5 个 proposed candidate、3 条 executed command、3 个
fresh environment 和 410.5 秒，从未调用 official evaluator。3 个 candidate environment 全部使用
read-only base-runtime probe 观测到的精确 image digest，因此 image-identity invariant 通过。

Probe 观测到 Python 3.13.2。Candidate 1 随后产生明确的 package-manager 诊断：当前 Python 版本不在
项目声明范围内。此后还有 4 次 proposal 机会，满足预注册 mechanism-trigger 条件。模型自己在下一
candidate 中选择了 Python 3.10，说明 free-form reasoning 能对这段文本作出反应。

但 typed state 没有反应。该 run 接纳的 repository runtime requirement 为 0，初始化后 constraint
update 为 0，没有创建 hard runtime conflict，也没有产生 `runtime_configure` obligation。因此
mismatch-to-conflict invariant 在 candidate 2 执行前已经失败；后续兼容 runtime 尝试不能追溯修复
这个不变量违规。

## 共享机制缺陷

决定性缺陷是 action-result admission grammar 过窄。形如 `Current Python version (...) is not allowed
by the project (...)` 的确定性通用诊断只停留在普通 execution evidence，没有成为 typed runtime
requirement/fact contradiction。结果是模型可能暂时选择兼容解释器，但 solver 无法在 fresh candidate
之间要求并保持这项修复。

该 repository 还使用了保守 pre-action observer 未接纳的 Poetry-specific runtime metadata；最后两个
proposal 也在 lock command 上重复触发 candidate-policy rejection。这些只作为次要 coverage 观察记录。
它们都不是确立主要失败所必需的证据，Q8 不会为它们继续叠加 post-hoc 修复。

按照冻结 adaptation policy，Q8 已关闭。任何 Q8 case 都不得重跑；剩余 selected case 不返回 untouched
pool；Q8 的任何结果都不支持论文级 effectiveness claim。

## 下一版本

下一机制版本应保持最小：

1. 定义与 package manager 无关的 runtime-mismatch diagnostic schema。
2. 只有 version 与 allowed range 都显式出现时才解析；near-miss diagnostic 仍保留为 provisional evidence。
3. 修改 live parser 前，先加入合成正例与对抗负例测试。
4. 复用现有 hard-conflict、operation planning、preservation 与 guard 链路，不增加 repository、package
   或 version rule。

Poetry declaration admission 与 candidate-policy command coverage 保持为独立 ablation candidate，只有
更广泛错误计数证明它们是独立瓶颈时才加入。修复后的机制必须重新冻结，并在新盲选的 untouched Q9
case 上资格验证。
