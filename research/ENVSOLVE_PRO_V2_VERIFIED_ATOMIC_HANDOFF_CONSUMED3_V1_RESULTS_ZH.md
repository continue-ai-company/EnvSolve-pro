# EnvSolve-Pro V2 验证式原子交接：Consumed-3 结果

## 研究问题

当可信完整目标确认构建环境已经就绪时，立即原子交付能否保住这个候选，并尽早把 fresh-state
失败返回给同一个 Agent session，使它有时间修复？

这三个 case 是因为历史已消费轨迹出现“目标已通过但迟迟没有交付”而选出的。因此本实验只做
机制资格验证，不是未见数据上的效果估计。

## 结果

三个 case 全部触发机制，第一次提交都紧跟在可信目标首次 Pass 后的下一次模型请求。

| Case | 首次目标 Pass | 首次提交 | Replay 序列 | 原始 Official | 归因 |
| --- | ---: | ---: | --- | --- | --- |
| Quacc | request 26 | request 27 | Unknown、Fail、Pass | Pass | treatment 直接结果 |
| Ajenti | request 96 | request 97 | Fail | Fail | 旧 harness 边界错误，删失 |
| Hark | request 16 | request 17 | Fail、Pass | Pass | treatment 直接结果 |

原始主指标是 `2/3` Official Pass。Ajenti 不会被事后改写成 Pass。另行预先写明流程、且不调用
模型的边界裁决，重放了 request 97 的原样程序：修正后的 clean replay 以零 missing import
通过，未改变的 Official evaluator 也通过。因此保留原运行的 Fail，但将它作为 harness
边界导致的失败从算法效果归因中删失。

## 机制证据

Quacc 说明为什么要尽早返回目标状态证据。第一个完整环境在 replay 构建时超时；第二个候选
过度使用 `--no-deps`，导致目标 import 失败。同一个 session 随后恢复完整的 CPU 兼容依赖，
只对少数可选包保留 no-deps，第三次 clean replay 与 Official 均通过。与独立的历史 atomic
rollout 相比，请求从 120 降至 60，Token 从 5.55M 降至 2.69M，结果从 Fail 变为 Pass。
这些只能作方向性描述，不能当作配对因果效应。

Hark 的第一次 replay 暴露了交付程序遗漏的 fresh-checkout 操作：Git 把 checkout 判为 dubious
ownership。Replay Fail 恢复自由工具选择后，Agent 在下一次请求主动加入 `safe.directory`
并重新提交，随后 replay 与 Official 均通过。与历史成功 rollout 相比，请求从 37 降至 18，
Token 从 0.58M 降至 0.20M。

Ajenti 暴露的是测量错误，而不是部署错误。Python 3.10 的分发元数据会漏掉没有
`top_level.txt` 的普通包，旧 provenance 检查也不识别由操作系统包管理器拥有的模块。因此
一个已经完成 bootstrap、完整目标为 Pass 的候选被误拒；Agent 随后丢掉工作环境并耗尽
session。修正后的边界识别 distribution 文件清单和固定路径系统包管理器的所有权，同时继续
拒绝手工制造的无归属 import provider。

## 决策

Consumed 机制已经通过资格验证：定时可信观测能发现可交付构建状态，原子交接消除了交付延迟，
replay 失败则形成可执行的 case-local 约束，而不替 Agent 决定修复动作。这支持一个简单的
三层算法：

1. **观测层：**定期执行完整可信目标，并从目标初始状态重放提交程序。
2. **约束层：**把目标残差和 replay 失败表示为当前 case 的可执行事实。
3. **操作层：**在一个连续 session 内让 Agent 自由检查和修复；harness 只在候选已通过可信目标
   时强制它立即交付。

下一步冻结这一组合机制，在结果未知、仓库不重叠的 bad-case batch 上与匹配的 `F+O` 对照做
前瞻比较。不增加包规则、checkpoint、跨 case 记忆或 harness 指定的修复动作。

机器可读结果：
`experiments/validations/envsolve_pro_v2_verified_atomic_handoff_consumed3_v1_result.json`。
