# EnvSolve-Pro Minimal B：固定 Bad4 结果

## 范围

这是四对 **开发期机制诊断**，不是未见测试集或刷榜证据。Case 在本轮执行前从已有 Dev 失败层中固定。
每一对使用相同的 DeepSeek V4 Flash 0731、provider 策略、公开目标、镜像、seed 和安全上限。对照组是
一个 goal-aware 连续 Agent session（`F+O`）；实验组增加 Agent 主动调用的干净目标状态重放，并要求
最终程序与某次通过的重放完全一致（`F+O+R`）。

Meerkat 对照组原始 episode 被人工中断，因此排除并使用预先批准的同臂 replacement。OpenQASM 实验组
第一次 Official 评测遇到 read timeout，只使用预先批准的原脚本 evaluation-only retry 替代 Official
结果。

## 主结果

| 仓库 | `F+O` | `F+O+R` | Replay 证据 |
| --- | ---: | ---: | --- |
| `hazyresearch/meerkat` | 未通过 | 未通过 | treatment 没有形成可重放候选 |
| `pysnmp/pysnmp` | 通过 | 通过 | 两次 Unknown，随后 Pass |
| `openqasm/openqasm` | 通过 | 通过 | 首次 replay Pass |
| `stopstalk/stopstalk-deployment` | 未通过 | 未通过 | treatment 没有形成可重放候选 |

两组 Official Pass 都是 `2/4`，没有 discordant pair，固定 batch 上的成功率增益严格为零。协议合规
口径结果相同。

## 机制发现

两个真实 noncompletion 都发生在 **replay 激活之前**。Meerkat 和 Stopstalk 的两组都耗尽 120 次模型
请求且没有提交，treatment 的 replay 调用数均为 0。可反复调用的 replay 能认证或修复一个完整候选，
但当 Agent 还无法把构建历史整理成合法程序时，它不起作用。

Pysnmp 暴露了 treatment 独有的 harness 缺陷。前两份程序都在公开目标上达到 missing imports 为 0，
但导入来源审计在仓库声明的 Python 3.9.7 环境中调用了 Python 3.10 才有的 API，因此返回 Unknown。
Agent 随后改用 Python 3.11，第三次 replay 和 Official 均通过。该兼容 bug 已在 `f923d7e` 修复，且没有
放宽审计。Pysnmp 的 Official Pass 有效，但其 replay 修复归因和资源路径受该 bug 混杂，最终 Python
版本也不如对照组的 Python 3.9 环境忠实。

OpenQASM 提供了更窄的收益：treatment 用 51 次模型请求和 124 万 Token 达到 Official Pass，对照组
为 106 次和 398 万 Token。但 treatment 只优化公开目标，没有 editable-install 本地项目；对照组构建了
更完整的环境。因此这是 Official 目标路径收益，不是同等部署完整性下的效率收益。

在两对共同成功 case 上，treatment 平均模型请求为 56.5 对 83，Token 为 138 万对 273 万，生成时间
为 1,896 秒对 2,004 秒。由于一对受到 harness bug 混杂，另一对部署完整性不同，这些描述性均值不能
作为效率主张。

## 决策

Minimal B 保留为有价值的 baseline，但不再作为最终 EnvSolve-Pro 算法。下一方法必须把可执行反馈前移
到 **候选形成**：在完整 bootstrap 出现之前，活跃 session 就能暴露并验证增量部署状态。方法仍应由
模型主导、只使用 case 内证据、不加入 package 特定规则，并把 Official 成功、部署完整性和资源作为
独立评价轴。只有在已消费轨迹上确定性验证状态转换，并在看到新结果前固定比较方案，才打开新 treatment。

机器可读证据：

- `experiments/schedules/envsolve_pro_v2_minimal_b_bad4_v1_effective.json`
- `experiments/validations/envsolve_pro_v2_minimal_b_bad4_v1_result.json`

