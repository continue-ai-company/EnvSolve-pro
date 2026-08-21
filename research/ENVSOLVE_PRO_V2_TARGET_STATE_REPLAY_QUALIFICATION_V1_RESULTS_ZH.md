# EnvSolve-Pro V2 目标状态重放资格实验 V1

状态：开发期资格实验完成，包含一次公开披露的法证纠正

## 问题

把完整部署程序从目标初始状态反复执行，并把失败返回同一个活跃 Agent session，是否值得进入更大的开发集
实验？

四对 case 来自实验开始前已有的随机 Dev16 顺序，在下载源码和调用模型前固定。本实验只决定机制是否值得
扩大验证，不是 held-out 结果，也不估计榜单表现。

## 结果

| Pair | 仓库 | A：自由反馈 | B：自由反馈 + 目标重放 | 机制证据 |
|---|---|---:|---:|---|
| 1 | probatus | Fail | Pass | B 首次重放通过，没有反馈修复 |
| 2 | pika | Pass | Pass | B 首次重放通过 |
| 3 | importlib_metadata | Pass | Pass | B 经历 Fail、Fail、Pass，修复了完整程序 |
| 4 | cellrank | Fail | Fail | 替代 B 在形成候选前耗尽 120 次请求 |

采用预先规定的替代 episode 后，主结果是 A `2/4`、B `3/4`：2 对都通过、1 对只有 B 通过、没有只有
A 通过的 pair、1 对都失败。由于只有一个不一致 pair，精确 McNemar 为 `p=1.0`。排除受人为中断影响
的整个 cellrank pair 后，A 为 `2/3`、B 为 `3/3`。两张表都不足以估计真实效果。

## 机制实际做了什么

三个形成候选的 B episode 共完成 5 次重放，最终重放与 Official 在 3/3 上一致。probatus 和 pika 首次
重放即通过。`importlib_metadata` 是真正的因果机制案例：第一次重放暴露 build isolation 中缺少
setuptools，同时发现必须保留的 `build_output` 目录缺失；第二份程序通过可执行目标，但仍遗漏该目录；
第三份程序同时修复二者并通过 Official。

cellrank 暴露了相反边界：Agent 尚未形成候选时，重放帮不上忙。替代 B 使用 120 次请求和 448 万 Token
仍未提交。因此，在声称重放能提高期望成功率之前，必须继续做更大的固定实验。

## 因果解释

probatus 是 treatment 层面的 B-only Pass，但 B 独立选择了不同的虚拟环境路径，而且第一次重放就通过。
它可能只是随机轨迹差异，不能归因于“重放失败后修复”。`importlib_metadata` 才直接支持窄主张：目标状态
反例可以在同一 session 中改变并修复完整交付程序。

cellrank A 用 shell 成功掩盖了 PETSc/SLEPc 安装失败，导致 Official 中缺少 `petsc4py` 和 `slepc4py`，
属于操作层的状态到程序缺口。替代 B 更早失败在候选形成阶段，也属于操作层。

## 资源

四对主分析中，A 使用 200 次模型请求、540 万 Token 和 6,124 秒生成时间；B 使用 209 次请求、595 万
Token 和 10,685 秒。无条件资源结果没有改善。在两个双方都成功的仓库上，B 的请求、Token、命令和生成
时间更低，但这是按 joint success 选择后的描述性切片，不能当作效率因果效应。

Token 始终是结果指标，不是成功阈值；在共享的宽松安全上限内，成功优先。

## 法证纠正

原 cellrank B 因生命周期状态过期和一个 CLOSE-WAIT socket 被误判为 provider hang 而遭人工停止。随后
重读轨迹和容器证据发现，请求 58 已返回完整 `submit_and_replay` 调用，第一次干净重放仍在执行。因此原
episode 应标为研究者中断并排除，不能标成基础设施失败。替代 episode 在模型执行前固定，并保持 case、
arm、模型、provider、seed、镜像、prompt、evaluator 和限制不变；所有结论还必须同时报告排除整个
cellrank pair 的敏感性结果。

## 决策

预注册晋级条件被谨慎满足：B 没有降低配对成功数，产生一个 B-only Pass，并在另一个 case 上产生一次
真实的 Fail-Fail-Pass 修复。因此保持算法不变，进入更大的固定开发集 batch。这只批准扩大机制验证，
不证明 EnvSolve-Pro 已获得效果、效率、held-out 泛化或 SOTA。

机器可读结果位于
`experiments/validations/envsolve_pro_v2_target_state_replay_qualification_v1_result.json`。
