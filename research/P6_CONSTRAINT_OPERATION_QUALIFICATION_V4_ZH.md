# P6 约束操作层资格实验 V4

状态：Q4 选样和执行之前的协议修订。

Q3 在第一组配对 case 后永久关闭。两个 episode 都是 audit-valid 的共同失败证据，official evaluator
claim 为 0。两种 treatment 共享的逐叶子 feedback truncation 无法限制 JSON collection 的 aggregate
size，导致两种方法都在耗尽 candidate budget 前终止于 64K context contract。全部五个 Q3 case
保持 development-consumed，剩余位置不得执行。

V4 只做一项 method-neutral 的 observation projection 修正。不可变 event state 继续完整保存，但模型
只接收受 aggregate budget 约束的充分统计量：未解决 conflict group、最近两份累积式候选、紧凑
verifier 摘要、有界 hypothesis 和 repository profile。Full EnvSolve 额外接收按 conflict domain
与允许 operation kind 分组的既有 operation 语义，并通过 `plan_id` 关联完整可审计计划；free-form
不接收 plan 或 operation instruction。确定性的逐字段 JSON budget 保证整体 projection contract，
包括合成高基数状态。

修正不新增仓库规则、package mapping、evidence parser、constraint、verifier、operation kind、guard
rule、模型、预算、指标或 official-evaluator signal。

Q4 从 `experiments/cases/train_untouched_after_operation_qualification_v3_181.jsonl` 中，使用 salt
`envsolve-p6-operation-qualification-v4-2026-07-17`，按 `SHA256(salt + NUL + case_id)` 升序
outcome-blind 选择五个新 case，并重复冻结的配对比较。除 source pool、salt、run ID、Q3 closure
和修正后的 mechanism freeze 外，V1 协议继续有效。任何 Q1、Q2 或 Q3 case 都不得复用。

