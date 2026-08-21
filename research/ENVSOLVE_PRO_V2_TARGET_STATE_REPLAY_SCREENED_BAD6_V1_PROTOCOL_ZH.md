# EnvSolve-Pro V2 Screened Bad-6 实验协议

状态：已于 2026-08-21 在新源码获取和模型执行前预注册

## 问题

当一个独立的高能力 baseline 已经在 Official evaluation 中失败时，在匹配的 DeepSeek 自由 Agent 上加入
目标状态反例重放，能否提高 Official Pass@1，或者产生真正由 replay 反馈触发的修复？

这是失败富集的开发期压力测试。它的目的，是避免再跑一组大量 ceiling case，而不是估计 EnvBench 总体
成功率。

## 选样

独立筛选器是已有的 Codex CLI `gpt-5.5` bad-case census。它只负责找出历史 Official failure，不是新实验
的 control arm。

从 casebook 中全部 11 个 confirmed Official failure 出发，排除 3 个被记录为原因不明 package-index 行为
的 case，再排除 2 个已经运行过 F+C_s+R 的仓库，剩余 6 个全部纳入：

| Pair | 仓库 | 历史失败分层 |
|---|---|---|
| 1 | Quantum-Accelerators/quacc | 操作层：native/system dependency |
| 2 | ajenti/ajenti | 约束层：build isolation |
| 3 | claritychallenge/clarity | 观测/操作层：checkout ownership |
| 4 | andrew-codechimp/HA-Battery-Notes | 约束层：传递 build dependency |
| 5 | econ-ark/hark | 观测/操作层：checkout ownership |
| 6 | bradenm/micropy-cli | 约束/操作层：项目 import 未被合法实现 |

不按照预期 treatment 表现或修复难度排序。这些历史失败已经参与开发诊断，因此本批仍是开发证据，不是
held-out confirmation。

## 对比

- **A-F：** 一个只使用普通执行反馈的连续 DeepSeek session。
- **B-FCsR：** 相同接口，加上可反复调用的目标状态完整程序重放，失败返回同一个活跃 session。

两臂统一使用 `deepseek/deepseek-v4-flash-0731`、OpenRouter 上的 DeepInfra、Spark Linux aarch64、相同
镜像和 Official evaluator；每个 construction episode 使用私有缓存，目标 replay 不继承 construction
cache，并共享宽松的 success-first 上限。每对 seed 相同；3 对 A-first，3 对 B-first；两条顺序 lane 可
并发运行。

## 结果指标

主指标是 Official Pass@1，报告完整配对表和精确 McNemar。B 额外报告候选形成、replay 顺序、失败后的
程序变化、修复类型以及最终 replay/Official 一致性。每个终局失败按证据标注最早的观测、约束或操作层；
基础设施单独处理。

资源只做描述，不作为成功硬阈值。总量必须同时配对差值与中位数。部署完整性仍是独立评价轴。

## 解释边界

首次 replay 即通过的 B-only 结果可以是 treatment-level 证据，但不能把 replay 修复与随机搜索分开。
反馈修复必须满足：目标状态 replay 失败、同 session 的完整程序发生实质变化、后续 replay 和 Official 均
通过。网络鲁棒性修复和兼容性修复分开统计。

实验期间算法和 taxonomy 不变。不能根据观测 episode 新增 package 规则、网络规则、checkpoint、跨 case
记忆、硬操作规则或新安全 gate。结果只适用于这个经过筛选的开发分层。

机器可读记录：

- `experiments/validations/envsolve_pro_v2_target_state_replay_screened_bad6_v1_selection.json`
- `experiments/validations/envsolve_pro_v2_target_state_replay_screened_bad6_v1_preregistration.json`
- `experiments/schedules/envsolve_pro_v2_target_state_replay_screened_bad6_v1.json`
