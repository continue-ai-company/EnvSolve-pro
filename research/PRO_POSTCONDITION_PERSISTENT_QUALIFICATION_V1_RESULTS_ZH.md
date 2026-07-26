# 后置条件状态复用资格实验 v1 结果

## 范围

该仓库不相交开发资格实验只检验一个机制：后置条件控制的 construction-state persistence 是否真实可执行、
完整性有效，并值得保留。它不是榜单结果或 final-test 结果。

- Case：5 个 EnvBench Python 开发仓库
- Condition：persistent explicit state、fresh explicit state、persistent raw history
- 模型：`deepseek/deepseek-v4-pro`
- Seed：1
- 主结果：Official Pass
- 在线反馈：只使用公开可执行目标；Official evaluator 仅终局运行

## 完整性

resolved schedule 的 15 个 episode 全部具有科学可用性且 artifact integrity 有效。原 position 5 在
Official evaluation 前被人工中断，保持原样并排除；预注册 replacement 只改变 run ID。最终分析通过
schedule identity、heartbeat、source cleanliness、budget ledger 和机制审计。

## 主要结果

| Condition | Official Pass | Candidates | Environments | Tokens | Generation wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Persistent explicit | 4/5 | 19 | 17 | 339,479 | 4,361 s |
| Fresh explicit | 4/5 | 21 | 15 | 358,742 | 3,955 s |
| Persistent raw | 4/5 | 27 | 26 | 483,988 | 9,064 s |

主对比 persistent explicit 与 fresh explicit 有 4 个双方都 Pass 的 block、1 个双方都 Fail 的 block；
次对比 persistent explicit 与 persistent raw 完全相同。没有 condition 产生 treatment-only Official Pass。

## 机制证据

persistent explicit 记录 6 次 reused-construction verification、4 次 clean replay Pass，其中 2 条成功
construction 谱系发生过复用。persistent raw 记录 4 次复用 verification 和 2 条 reuse-to-clean-pass
谱系。因此预注册 gate 返回 `retain-mechanism`：状态复用真实、可审计，且没有造成 Official Pass 损失。

该判定不等于效果结论。persistent explicit 比 fresh explicit 使用更少候选和 token，但 easy case 的
clean replay 开销使 wall time 更高；它比 persistent raw 使用明显更少资源，尤其在 TRTools 上，但五个
仓库与一个随机 seed 不足以支持总体效率声明。

## 失败分析

`openqasm/openqasm` 是唯一共同失败。三个 condition 都耗尽 12 个候选，并保留仍有 7 个官方 issue 的
程序。显式状态减少了轨迹漂移，persistent explicit 的 generation time 约为 persistent raw 的一半，
但仍未越过成功边界。

决定性缺口位于操作层：

- 提出操作前没有证明 tool、file、target、version 或 acquisition precondition；
- 等价 ANTLR 生成失败在没有新证据时重复；
- 部分候选通过写配置或直接物化 import artifact 优化诊断代理；
- effect boundary 拒绝了这些违反完整性的捷径。

## 决策

保留后置条件控制的状态复用，把它作为支持机制，而不是当前论文的效果 claim。下一版只增加最小的
可执行操作相关性合同：目标 constraint、前提探针、预期 finding delta、实际完整快照 delta，以及重复
失败操作族抑制。先用 synthetic 与仓库不相交证据资格验证，不得针对 OpenQASM 调参。

## 冻结证据

- Resolved schedule：
  `experiments/validations/pro_postcondition_persistent_qualification_v1_resolved_r1_schedule.json`
- Results：
  `experiments/validations/pro_postcondition_persistent_qualification_v1_results.json`
- Censored-attempt audit：
  `experiments/validations/pro_postcondition_persistent_qualification_v1_censored_position5_descriptive_audit.json`
- Gate decision：`retain-mechanism`
