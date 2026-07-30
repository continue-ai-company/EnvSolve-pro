# EnvSolve-Pro Stateful-Agent V2.4 Pilot-4 结果

## 状态

Pilot-4 是一组干净且具备科学统计资格的开发实验。冻结 schedule 中 12 个 episode 的 artifact
全部完整有效、运行身份一致，并到达 EnvBench 官方 evaluator。四个仓库身份从现在起全部标记为
已消费，不能再用于后续方法资格验证。

实验固定 `gpt-5.5`、公开可执行目标、只在终局运行的 Official evaluator、seed 和开放式累计
Bash 接口，对比：

1. 强单 session goal-aware Codex；
2. 同模型多 session raw repair V2.4；
3. EnvSolve-Pro structured stateful-agent V2.4。

原始执行的位置 3-6 曾被实验者中断或污染，在查看结果前已排除。冻结 amendment 为所有受影响位置
分配新 run ID 并完整重跑。正式分析使用源 schedule 的位置 1-2，以及 outcome-independent
amendment 的位置 3-12。

## 官方结果

| 条件 | Official Pass | 端到端耗时 (s) | 命令数 | Input token | Output token | Reasoning token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 强 goal-aware baseline | 4/4 | 2,688.3 | 78 | 2,337,478 | 31,379 | 14,230 |
| Raw repair V2.4 | 4/4 | 3,125.3 | 57 | 2,320,139 | 31,637 | 16,035 |
| Structured V2.4 | 4/4 | 3,233.0 | 78 | 3,867,529 | 36,766 | 18,916 |

| 仓库 | Strong | Raw | Structured | Structured 候选数 / 轮数 |
| --- | ---: | ---: | ---: | ---: |
| great-tables | Pass | Pass | Pass | 1 / 1 |
| pyperf | Pass | Pass | Pass | 1 / 1 |
| cbmonitor | Pass | Pass | Pass | 1 / 1 |
| flavio | Pass | Pass | Pass | 1 / 1 |

Official Pass 没有增益。相对 raw repair，structured V2.4 多使用 66.7% input token、
36.8% 容器命令和 3.4% 端到端时间；相对强单 session baseline，多使用 65.5% input token
和 20.3% 时间。这些只是四个 case 上的描述性资源差异，不是总体统计结论。

## 机制发现

V2.4 的状态化假设没有被真正触发。所有 raw 和 structured episode 都只提交一个候选、只运行一个
模型轮次就通过。没有失败候选产生新的 Observation，没有约束 frontier 跨 session 更新，也没有后续
Operation 可以利用结构化状态。因此，这批实验没有检验“失败后修复”。其中的资源差异来自首轮
轨迹，不能归因于没有被触发的状态机制。

三个较简单仓库说明：强 Agent 经常在跨 session 机制生效前就解决公开目标。在 `cbmonitor` 上，
首次 PyPI TLS 失败在同一 session 内恢复，并且没有被错误固化为部署约束，这是正确行为。

`flavio` 暴露了当前主要矛盾。成功部署需要同时协调：

- 旧 SciPy API 的语义兼容；
- 能承载旧 SciPy 的 Python 版本；
- NumPy 低于 1.24，因为该 SciPy 分支仍使用已删除的 NumPy alias；
- ARM 平台上 `rundec` 的 wheel 或源码构建可行性；
- 静态分析可见性，以及运行时解释器和编译扩展 ABI 的一致性。

Raw repair 与强 baseline 最终都提交了内部一致的 Python 3.8 环境。Structured V2.4 则尝试了更多
相互冲突的状态，包括会升级 NumPy 的 stub 包、多个 Pyright 与 Python 版本，以及一次破坏性环境
事务。它最终通过 `PYTHONPATH`，把 Python 3.9 的 `rundec` package-cache 内容注入 Python 3.8
环境。Official Pyright 确实通过，但 Python 3.8 能否加载该编译扩展没有得到证明。这是 benchmark
目标与真实运行一致性之间的缺口，不是 Official 计分错误，因此必须分别记录 Official Pass 和
runtime coherence。

## 决策

V2.4 冻结为可审计的 structured baseline，不晋升为当前算法。这批结果不支持榜单、效果或效率
claim。

下一版假设比继续增加语义规则更简单：

1. **观测层：** 在当前 Agent session 内，把命令结果转成紧凑且单调演化的 compatibility
   frontier。
2. **约束层：** 只接纳有因果证据支持的 package、platform、version 与 operation 事实，并把
   Official-goal 状态和 runtime coherence 分开。
3. **操作层：** 保持开放终端，但对高影响环境事务增加可行性检查、后置条件，并明确抑制已被证伪
   的动作。

这会把状态机制移动到强 Agent 真正发生失败与恢复的位置，而不是等待一个经常不会出现的第二候选。
Pilot-4 四个仓库此后只能用于回归与机制构造；资格实验必须使用 outcome-blind、
repository-disjoint 新 case，同时测量 Official Pass@1 与 failure-conditioned recovery。

## 证据

- 冻结分析 schedule：
  `experiments/schedules/pro_stateful_agent_v2_4_pilot4_mac_clean_retry2.json`
- 干净重跑 amendment：
  `experiments/validations/pro_stateful_agent_v2_4_pilot4_clean_retry2_amendment.json`
- 哈希审计结果：
  `experiments/validations/pro_stateful_agent_v2_4_pilot4_results.json`
- 已消费 CWD 因果复放：
  `experiments/validations/pro_stateful_agent_v2_4_cwd_causal_replay1.json`
