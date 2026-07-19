# P6 Q10 Candidate 失败分析

状态：对已消费 development trajectory 的 batch 后分析。本分析不改变算法，也不改写 evaluator 结果。

## 阶段分解

确定性分析器按照已记录的状态转移，对全部 50 个 proposed candidate 做互斥且完备的分类。分类只使用
event schema、exit code 和 structured verifier field，不使用 repository-specific 日志文本规则。

| Candidate 终止阶段 | EnvSolve | Ablation | 总计 |
| --- | ---: | ---: | ---: |
| Candidate-command failure | 10 | 13 | 23 |
| 固定 internal-check failure | 5 | 5 | 10 |
| Structured obligation 未解 | 5 | 3 | 8 |
| 共享 candidate-validation reject | 2 | 4 | 6 |
| EnvSolve operation-guard reject | 3 | 0 | 3 |

9 个 proposal 在创建 fresh environment 前被拒绝，41 个进入真实执行。在实际执行的 candidate 中，
23 个（56.1%）失败于 candidate command，10 个（24.4%）进入固定 internal check 后失败，8 个
（19.5%）完成固定 check 但仍有 structured obligation。40 个 candidate 后面仍有 proposal 机会。

Full EnvSolve 比 ablation 更常进入 structured verifier（5 对 3），candidate-command failure 更少
（10 对 13），但两种条件在每个 case 上都耗尽 5 个 candidate。这些只是 development 机制计数，
不是效果估计。

## 主要矛盾

当前直接瓶颈是 evaluator 前的校准。Candidate-command failure 出现在全部 5 个 repository，涵盖
runtime compatibility、不可用的 package/source mapping、native build 前置条件和依赖获取。这说明
自然语言执行反馈比当前 typed feasibility state 更丰富。但另有 10 个 candidate 被固定 internal
check 阻断，8 个被 official objective 的 structured 近似阻断；在没有终局校准前，放松任何一层
verifier 都可能只是掩盖真正的 Official failure。

其中一条 trajectory 展示了预期的 stateful 行为，也暴露了响应延迟：runtime mismatch 形成 hard
runtime operation obligation；无效 runtime mutation 被拒绝；后续 candidate 配置 Python 3.11，并将
runtime unresolved module 降为 0。但这一状态直到 candidate 5 才到达，已经没有预算修复剩余 static
obligation。该结果支持 stateful constraint propagation 的机制，同时说明 operation feasibility 与
搜索效率在冻结预算下仍然不足。

## 下一项可证伪实验

在修改 solver 或 verifier scope 前，对每条 Q10 run 只选择一份确定性脚本做无模型、episode 后校准：
选择最后一个拥有 `verification_recorded` event 的 candidate。选择只使用冻结 trajectory structure，
并在任何新的 Official result 前固定。每份脚本只在 fresh environment 中通过未修改的 EnvBench
evaluator replay 一次。

该校准区分两个假设：

1. 如果 terminal evaluation 在相同 obligation 上失败，主要目标是 action feasibility 与 candidate
   efficiency，internal scope 应保持冻结。
2. 如果 terminal evaluation 通过，或绕过了反复出现的 internal blocker，则 internal verifier 存在
   校准偏差；任何修改都必须先由通用合成反例定义最小 scope correction。

该校准只属于 development，不贡献榜单估计，不产生新模型调用，也不能重跑或替换 Q10 generation
trajectory。
